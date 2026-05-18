"""
fan_cfd.rendering.report
========================
Generate a self-contained HTML screen showing the fan assembly and CFD results.
"""

from __future__ import annotations

import html
import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import trimesh


def write_render_screen(
    run_dir: str | Path,
    output_path: str | Path | None = None,
    results_path: str | Path | None = None,
    assembly_path: str | Path | None = None,
    title: str | None = None,
) -> Path:
    """
    Write a static HTML render screen for a completed run directory.

    Parameters
    ----------
    run_dir:
        Base run directory containing ``geometry/full_assembly.stl`` and
        ``results/results.json`` by default.
    output_path:
        Destination HTML path. Defaults to ``<run_dir>/render/index.html``.
    results_path:
        Optional explicit results JSON path.
    assembly_path:
        Optional explicit STL path for the full assembly.
    title:
        Optional report title.
    """
    run_dir = Path(run_dir)
    output = Path(output_path) if output_path else run_dir / "render" / "index.html"
    results_file = Path(results_path) if results_path else run_dir / "results" / "results.json"
    assembly_file = (
        Path(assembly_path) if assembly_path else run_dir / "geometry" / "full_assembly.stl"
    )

    if not assembly_file.exists():
        raise FileNotFoundError(f"Full assembly STL not found: {assembly_file}")
    if not results_file.exists():
        raise FileNotFoundError(f"CFD results JSON not found: {results_file}")

    results = json.loads(results_file.read_text(encoding="utf-8"))
    report_title = title or _default_title(results, run_dir)
    assembly_svg = render_assembly_svg(assembly_file)
    page = _build_html(report_title, results, assembly_svg, assembly_file, results_file)

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(page, encoding="utf-8")
    return output


def render_assembly_svg(stl_path: str | Path, width: int = 940, height: int = 640) -> str:
    """Render an STL mesh to an isometric SVG preview."""
    mesh = _load_mesh(Path(stl_path))
    vertices = np.asarray(mesh.vertices, dtype=float)
    faces = np.asarray(mesh.faces, dtype=int)
    if len(vertices) == 0 or len(faces) == 0:
        raise ValueError(f"Assembly mesh is empty: {stl_path}")

    centered = vertices - mesh.bounds.mean(axis=0)
    view_dir = _normalize(np.array([0.82, -1.0, 0.52]))
    world_up = np.array([0.0, 0.0, 1.0])
    right = _normalize(np.cross(view_dir, world_up))
    up = _normalize(np.cross(right, view_dir))

    projected_x = centered @ right
    projected_y = centered @ up
    depth = centered @ view_dir

    pad = 42.0
    x_span = max(float(np.ptp(projected_x)), 1e-9)
    y_span = max(float(np.ptp(projected_y)), 1e-9)
    scale = min((width - 2 * pad) / x_span, (height - 2 * pad) / y_span)
    screen_x = (projected_x - projected_x.min()) * scale + pad
    screen_y = height - ((projected_y - projected_y.min()) * scale + pad)

    face_depth = depth[faces].mean(axis=1)
    order = np.argsort(face_depth)
    max_faces = 7000
    if len(order) > max_faces:
        step = int(math.ceil(len(order) / max_faces))
        order = order[::step]

    normals = np.asarray(mesh.face_normals, dtype=float)
    light = _normalize(np.array([-0.4, -0.7, 0.9]))
    face_shade = np.clip(normals @ light, -0.4, 1.0)

    polygons: list[str] = []
    for face_index in order:
        face = faces[face_index]
        points = " ".join(f"{screen_x[i]:.1f},{screen_y[i]:.1f}" for i in face)
        shade = 0.58 + 0.32 * float(face_shade[face_index])
        fill = _shade_hex("#62c7ba", shade)
        stroke = _shade_hex("#27665f", 0.78)
        polygons.append(
            f'<polygon points="{points}" fill="{fill}" stroke="{stroke}" '
            'stroke-width="0.35" stroke-opacity="0.55" />'
        )

    bounds = mesh.bounds
    size = bounds[1] - bounds[0]
    size_label = " x ".join(f"{v * 1000:.0f} mm" for v in size)
    return f"""\
<svg class="assembly-render" viewBox="0 0 {width} {height}" role="img"
     aria-label="Full fan assembly render">
  <defs>
    <linearGradient id="floorFade" x1="0" x2="1" y1="0" y2="1">
      <stop offset="0%" stop-color="#e9f3f1" />
      <stop offset="100%" stop-color="#cadbd8" />
    </linearGradient>
  </defs>
  <rect width="{width}" height="{height}" rx="0" fill="#f7faf9" />
  <path d="M 90 {height - 96} L {width - 120} {height - 72} L {width - 70} {height - 38} L 45 {height - 58} Z"
        fill="url(#floorFade)" opacity="0.7" />
  <g opacity="0.24" stroke="#8ba6a1" stroke-width="1">
    <path d="M 88 {height - 95} L {width - 120} {height - 72}" />
    <path d="M 205 {height - 91} L {width - 40} {height - 48}" />
    <path d="M 60 {height - 65} L {width - 108} {height - 42}" />
  </g>
  <g>
    {"".join(polygons)}
  </g>
  <text x="28" y="{height - 28}" class="svg-caption">Full assembly - {html.escape(size_label)}</text>
</svg>
"""


def _load_mesh(path: Path) -> trimesh.Trimesh:
    loaded = trimesh.load(path, force="mesh")
    if isinstance(loaded, trimesh.Scene):
        meshes = [g for g in loaded.geometry.values() if isinstance(g, trimesh.Trimesh)]
        if not meshes:
            raise ValueError(f"No mesh geometry found in {path}")
        return trimesh.util.concatenate(meshes)
    if not isinstance(loaded, trimesh.Trimesh):
        raise ValueError(f"Unsupported mesh type for {path}: {type(loaded)!r}")
    return loaded


def _build_html(
    title: str,
    results: dict[str, Any],
    assembly_svg: str,
    assembly_path: Path,
    results_path: Path,
) -> str:
    metrics = [
        ("Pressure Rise", _fmt_number(results.get("pressure_rise_pa"), "Pa", 2)),
        ("Flow Rate", _fmt_number(results.get("flow_rate_m3_s"), "m^3/s", 4)),
        ("Torque", _fmt_number(results.get("torque_nm"), "N m", 5)),
        ("Shaft Power", _fmt_number(results.get("shaft_power_w"), "W", 2)),
        ("Efficiency", _fmt_percent(results.get("efficiency"))),
    ]
    mesh = results.get("mesh") or {}
    convergence = results.get("convergence") or {}
    residuals = convergence.get("final_residuals") or {}
    mesh_ok = bool(mesh.get("ok"))
    converged = bool(convergence.get("converged"))
    status_class = "ok" if mesh_ok and converged else "warn"
    status_text = "Ready" if mesh_ok and converged else "Review"

    metric_cards = "\n".join(
        f"""\
        <section class="metric-card">
          <span>{html.escape(label)}</span>
          <strong>{html.escape(value)}</strong>
        </section>"""
        for label, value in metrics
    )
    residual_rows = "\n".join(
        f"<tr><td>{html.escape(str(name))}</td><td>{_fmt_scientific(value)}</td></tr>"
        for name, value in sorted(residuals.items())
    ) or '<tr><td colspan="2">No residual data</td></tr>'

    mesh_rows = "\n".join(
        [
            _quality_row("Cells", _fmt_int(mesh.get("n_cells")), None),
            _quality_row("Max non-ortho", _fmt_number(mesh.get("max_non_ortho"), "deg", 2), 65),
            _quality_row("Max skewness", _fmt_number(mesh.get("max_skewness"), "", 2), 4),
        ]
    )

    escaped_title = html.escape(title)
    escaped_assembly = html.escape(str(assembly_path))
    escaped_results = html.escape(str(results_path))

    return f"""\
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{escaped_title}</title>
  <style>
    :root {{
      color-scheme: light;
      --bg: #eef3f1;
      --surface: #ffffff;
      --surface-2: #f7faf9;
      --text: #17221f;
      --muted: #667671;
      --line: #d9e3e0;
      --accent: #167d71;
      --accent-2: #2f9d8f;
      --warn: #9a6a13;
      --ok: #167d49;
      --shadow: 0 18px 52px rgba(20, 38, 34, 0.12);
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background: var(--bg);
      color: var(--text);
    }}
    main {{
      min-height: 100vh;
      display: grid;
      grid-template-columns: minmax(0, 1.35fr) minmax(360px, 0.65fr);
      gap: 0;
    }}
    .viewer {{
      min-height: 100vh;
      padding: 28px;
      display: grid;
      grid-template-rows: auto minmax(0, 1fr);
      gap: 22px;
    }}
    .topbar {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 18px;
    }}
    h1 {{
      margin: 0;
      font-size: 24px;
      line-height: 1.16;
      font-weight: 720;
      letter-spacing: 0;
    }}
    .source {{
      color: var(--muted);
      font-size: 12px;
      line-height: 1.5;
      overflow-wrap: anywhere;
    }}
    .status {{
      flex: 0 0 auto;
      border: 1px solid var(--line);
      background: var(--surface);
      padding: 8px 12px;
      font-size: 13px;
      font-weight: 680;
    }}
    .status.ok {{ color: var(--ok); }}
    .status.warn {{ color: var(--warn); }}
    .render-frame {{
      min-height: 0;
      background: var(--surface-2);
      border: 1px solid var(--line);
      box-shadow: var(--shadow);
      overflow: hidden;
    }}
    .assembly-render {{
      width: 100%;
      height: 100%;
      min-height: 560px;
      display: block;
    }}
    .svg-caption {{
      font: 12px Inter, ui-sans-serif, system-ui, sans-serif;
      fill: #53645f;
      letter-spacing: 0;
    }}
    .results {{
      min-height: 100vh;
      border-left: 1px solid var(--line);
      background: var(--surface);
      padding: 28px;
      display: grid;
      align-content: start;
      gap: 22px;
    }}
    .section-title {{
      margin: 0 0 12px;
      font-size: 13px;
      font-weight: 760;
      text-transform: uppercase;
      color: var(--muted);
      letter-spacing: 0;
    }}
    .metrics {{
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 10px;
    }}
    .metric-card {{
      border: 1px solid var(--line);
      background: var(--surface-2);
      padding: 14px;
      min-height: 86px;
      display: flex;
      flex-direction: column;
      justify-content: space-between;
    }}
    .metric-card span {{
      color: var(--muted);
      font-size: 12px;
      font-weight: 650;
    }}
    .metric-card strong {{
      font-size: 22px;
      line-height: 1.1;
      font-weight: 760;
    }}
    .panel {{
      border: 1px solid var(--line);
      background: #fff;
      padding: 16px;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 13px;
    }}
    td {{
      padding: 9px 0;
      border-top: 1px solid var(--line);
      vertical-align: top;
    }}
    tr:first-child td {{ border-top: 0; }}
    td:last-child {{
      text-align: right;
      font-weight: 680;
      color: var(--text);
    }}
    .quality-note {{
      color: var(--muted);
      font-size: 12px;
      line-height: 1.45;
      margin: 12px 0 0;
    }}
    .footer-note {{
      color: var(--muted);
      font-size: 12px;
      line-height: 1.5;
      overflow-wrap: anywhere;
    }}
    @media (max-width: 980px) {{
      main {{ grid-template-columns: 1fr; }}
      .viewer {{ min-height: auto; }}
      .results {{
        min-height: auto;
        border-left: 0;
        border-top: 1px solid var(--line);
      }}
      .assembly-render {{ min-height: 420px; }}
    }}
    @media (max-width: 560px) {{
      .viewer, .results {{ padding: 18px; }}
      .topbar {{ align-items: flex-start; flex-direction: column; }}
      .metrics {{ grid-template-columns: 1fr; }}
      .metric-card strong {{ font-size: 20px; }}
    }}
  </style>
</head>
<body>
  <main>
    <section class="viewer">
      <div class="topbar">
        <div>
          <h1>{escaped_title}</h1>
          <div class="source">Assembly: {escaped_assembly}</div>
        </div>
        <div class="status {status_class}">{status_text}</div>
      </div>
      <div class="render-frame">
        {assembly_svg}
      </div>
    </section>
    <aside class="results">
      <section>
        <h2 class="section-title">CFD Results</h2>
        <div class="metrics">
          {metric_cards}
        </div>
      </section>
      <section class="panel">
        <h2 class="section-title">Mesh Quality</h2>
        <table>{mesh_rows}</table>
        <p class="quality-note">Mesh status: {_status_word(mesh_ok)}. Quality limits are shown where a common smoke-test threshold applies.</p>
      </section>
      <section class="panel">
        <h2 class="section-title">Convergence</h2>
        <table>
          <tr><td>Status</td><td>{_status_word(converged)}</td></tr>
          <tr><td>Iterations</td><td>{_fmt_int(convergence.get("n_iterations"))}</td></tr>
          {residual_rows}
        </table>
      </section>
      <div class="footer-note">Results source: {escaped_results}</div>
    </aside>
  </main>
</body>
</html>
"""


def _quality_row(label: str, value: str, limit: float | None) -> str:
    suffix = f" <span class=\"source\">limit {limit:g}</span>" if limit is not None else ""
    return f"<tr><td>{html.escape(label)}</td><td>{html.escape(value)}{suffix}</td></tr>"


def _default_title(results: dict[str, Any], run_dir: Path) -> str:
    name = results.get("config_name") or run_dir.name
    return f"{name} render"


def _fmt_number(value: Any, unit: str, digits: int) -> str:
    if value is None:
        return "n/a"
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return "n/a"
    if math.isnan(numeric):
        return "n/a"
    suffix = f" {unit}" if unit else ""
    return f"{numeric:.{digits}f}{suffix}"


def _fmt_percent(value: Any) -> str:
    if value is None:
        return "n/a"
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return "n/a"
    if math.isnan(numeric):
        return "n/a"
    return f"{numeric * 100:.1f}%"


def _fmt_int(value: Any) -> str:
    if value is None:
        return "n/a"
    try:
        return f"{int(value):,}"
    except (TypeError, ValueError):
        return "n/a"


def _fmt_scientific(value: Any) -> str:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return "n/a"
    if math.isnan(numeric):
        return "n/a"
    return f"{numeric:.3e}"


def _status_word(ok: bool) -> str:
    return "OK" if ok else "Review"


def _normalize(v: np.ndarray) -> np.ndarray:
    norm = float(np.linalg.norm(v))
    if norm == 0.0:
        return v
    return v / norm


def _shade_hex(hex_color: str, factor: float) -> str:
    factor = max(0.0, min(1.25, factor))
    hex_color = hex_color.lstrip("#")
    r = int(hex_color[0:2], 16)
    g = int(hex_color[2:4], 16)
    b = int(hex_color[4:6], 16)
    r = max(0, min(255, int(r * factor)))
    g = max(0, min(255, int(g * factor)))
    b = max(0, min(255, int(b * factor)))
    return f"#{r:02x}{g:02x}{b:02x}"
