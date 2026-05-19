# parametric-fan-cfd

A parametric fan blade generator and OpenFOAM CFD optimization pipeline. Define your fan geometry in YAML, automatically generate 3D blade geometry, mesh it with snappyHexMesh, run steady-state RANS CFD using Multiple Reference Frames (MRF), and optionally optimize the blade geometry for efficiency, pressure rise, or flow rate.

---

## What it does

1. **Parametric geometry**: Define blade profiles (NACA 4-digit), chord and twist distributions, blade count, hub/tip radii, and duct geometry — all in a YAML config.
2. **Multi-stage support**: Arbitrary rotor/stator stage arrangements. Profiles can be inherited between stages with scaling.
3. **STL generation**: Lofted blade surfaces exported as STL files via trimesh (no CAD kernel required).
4. **OpenFOAM case builder**: Generates a complete, ready-to-run simpleFoam + kOmegaSST + MRF case.
5. **Automated run pipeline**: blockMesh → surfaceFeatureExtract → snappyHexMesh → checkMesh → simpleFoam.
6. **Postprocessing**: Extracts pressure rise, flow rate, torque, shaft power, and efficiency from function object output.
7. **Optimization**: Random search and differential evolution optimizers vary blade geometry parameters and re-run CFD to maximize an objective function.

---

## Required software

| Software | Version | Notes |
|----------|---------|-------|
| Python | ≥ 3.10 | |
| OpenFOAM | v8, v9, or v2206+ | Must be sourced (`source /opt/openfoam*/etc/bashrc`) |
| trimesh | ≥ 4.0 | Installed via pip |
| numpy | ≥ 1.24 | |
| scipy | ≥ 1.10 | |
| pydantic | ≥ 2.0 | |
| pyyaml | ≥ 6.0 | |
| pandas | ≥ 2.0 | For postprocessing |
| matplotlib | ≥ 3.7 | Optional, for plotting residuals |

---

## Installation

```bash
# Clone or download the project
git clone https://github.com/yourorg/parametric-fan-cfd.git
cd parametric-fan-cfd

# Create a virtual environment (recommended)
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Install in editable mode (makes CLI scripts available)
pip install -e .

# Source OpenFOAM (adjust path for your installation)
source /opt/openfoam2206/etc/bashrc
```

---

## Docker/OpenFOAM workflow

The easiest reproducible path is the Docker pipeline. It builds an Ubuntu
OpenFOAM 13 image, installs the Python dependencies, runs the test suite,
generates the default 50 mm three-stack geometry, builds the OpenFOAM case, and
writes the render screen.

```bash
python scripts/docker_pipeline.py
```

Run the full mesh and solver pipeline inside Docker:

```bash
python scripts/docker_pipeline.py --full-cfd
```

Run an interactive OpenFOAM-enabled shell:

```bash
python scripts/docker_pipeline.py --command bash
```

The same Docker validation runs in GitHub Actions via
`.github/workflows/docker-openfoam.yml`.

---

## Quick start

```bash
# 1. Generate geometry only (validate + STL export, no CFD)
python scripts/generate_geometry.py \
    --config configs/example_single_stage_rotor.yaml \
    --output-dir runs/my_first_fan/geometry

# 2. Run the full pipeline (geometry → mesh → solve → postprocess)
python scripts/run_case.py \
    --config configs/example_single_stage_rotor.yaml \
    --output-dir runs/my_first_fan

# 3. Re-run postprocessing on an existing case
python scripts/postprocess_case.py \
    --case runs/my_first_fan/openfoam \
    --config configs/example_single_stage_rotor.yaml

# 4. Generate an HTML render screen for the assembly + CFD results
python scripts/render_screen.py \
    --run-dir runs/my_first_fan

# 5. Run optimization (20 random trials)
python scripts/optimize.py \
    --config configs/example_single_stage_rotor.yaml \
    --n-trials 20 \
    --method random \
    --output-dir runs/optimization
```

After `run_case.py` completes, results are written to `runs/<fan_name>/results/results.json`.

---

## Config reference

All configs are YAML files validated by Pydantic v2. Every field is SI units unless noted.

### Top-level structure

```yaml
fan:      # Fan geometry (see below)
cfd:      # CFD settings
objective: # Optimization objective
```

### fan block

```yaml
fan:
  name: my_fan             # used for run directory names
  max_diameter_m: 0.120    # outer tip diameter
  hub_diameter_m: 0.030    # hub (shaft) diameter
  rpm: 5000.0              # global default RPM (rotors inherit this if not set)

  duct:                    # optional; omit for open rotor
    enabled: true
    inner_diameter_m: 0.122
    wall_thickness_m: 0.003
    total_length_m: 0.080
    inlet_clearance_m: 0.010
    outlet_clearance_m: 0.010

  stages:                  # list of rotor and stator stages
    - name: rotor_1
      type: rotor          # or "stator"
      axial_position_m: 0.015
      blade_count: 5
      rpm: 5000.0          # optional; falls back to fan.rpm
      rotation_direction: counterclockwise   # or "clockwise"
      blade:
        airfoil: naca4412  # NACA 4-digit code
        radial_sections: 9 # cross-sections from hub to tip (3–50)
        chord_profile:     # see Profile types below
          type: linear
          points:
            - [0.0, 0.030]  # [r_normalized, chord_m]
            - [1.0, 0.020]
        twist_profile_deg:
          type: linear
          points:
            - [0.0, 42.0]
            - [1.0, 18.0]
        thickness_scale: 1.0   # multiplier on NACA thickness
        rake_profile: null     # optional axial rake distribution
        skew_profile: null     # optional angular skew distribution
```

### Profile types

| type | Required fields | Description |
|------|----------------|-------------|
| `constant` | `value` | Same value at all radii |
| `linear` | `points: [[0.0, v0], [1.0, v1]]` | Linear interpolation root → tip |
| `control_points` | `points: [[r, v], ...]` | Cubic spline through N≥2 points |
| `inherit` | `from_stage`, `scale` | Copy another stage's profile, multiplied by scale |

### cfd block

```yaml
cfd:
  solver: simpleFoam
  rotation_model: MRF
  turbulence_model: kOmegaSST

  inlet:
    patch_name: inlet
    velocity_m_s: 5.0
    turbulence_intensity: 0.05    # fraction (5%)
    hydraulic_diameter_m: 0.12

  outlet:
    patch_name: outlet
    velocity_m_s: 5.0

  fluid:
    nu_m2_s: 1.5e-5   # kinematic viscosity (air at 20°C)
    rho_kg_m3: 1.225

  mesh:
    base_cell_size_m: 0.005
    refinement_levels: 3          # snappyHexMesh surface refinement levels
    boundary_layers: 5
    boundary_layer_expansion: 1.2
    domain_length_factor: 5.0     # domain radius = fan_radius * this
    n_processors: 4

  run:
    n_iterations: 500
    write_interval: 100
    convergence_residual: 1.0e-4
    parallel: false
    n_procs: 4
    purge_write: 1
```

### objective block

```yaml
objective:
  mode: single             # or "multi_objective"
  maximize: efficiency     # "efficiency" | "pressure_rise" | "flow_rate"
  constraints:
    min_pressure_rise_pa: 10.0    # prefix min_ or max_
  weights:                        # for multi_objective mode
    efficiency: 0.6
    pressure_rise: 0.4
```

---

## Multi-stage configuration guide

Stages are defined in axial order. The loader validates that:
- Stage names are unique
- No two stages share the same axial position
- Blade tips fit inside the duct
- All stages are within the duct's axial extent
- Minimum 2 mm axial clearance between consecutive stages

### Inherited profiles

Stage 2 can inherit its chord or twist profile from Stage 1, optionally scaled:

```yaml
stages:
  - name: rotor_1
    ...
    blade:
      chord_profile:
        type: linear
        points: [[0.0, 0.040], [1.0, 0.024]]

  - name: rotor_2
    ...
    blade:
      chord_profile:
        type: inherit
        from_stage: rotor_1
        scale: 0.9     # 10% smaller chord at all radii
      twist_profile_deg:
        type: inherit
        from_stage: rotor_1
        scale: 1.0     # same twist angles
```

### Counter-rotating stages

Set `rotation_direction: clockwise` on rotor_2 to get a counter-rotating stage. The MRF omega sign is applied automatically.

---

## Running optimization

The optimizer varies blade parameters (blade count, chord, twist) and re-runs CFD for each trial. Results are saved per-trial in `runs/<fan>/optimization/trial_XXXX/`.

```bash
# Random search (20 trials)
python scripts/optimize.py \
    --config configs/example_single_stage_rotor.yaml \
    --n-trials 20 \
    --method random

# Differential evolution (50 trials)
python scripts/optimize.py \
    --config configs/example_rotor_stator.yaml \
    --n-trials 50 \
    --method differential_evolution
```

The leaderboard CSV is written to `runs/<fan>/optimization/leaderboard.csv` and updated after every trial.

**Note**: Each trial runs the full geometry + mesh + solve pipeline, so optimization is slow. On a 4-core workstation with a 120 mm fan, expect 15–30 minutes per trial. Use `--n-trials 5` for a quick smoke test.

---

## Understanding results

`results.json` structure:

```json
{
  "flow_rate_m3_s": 0.0348,      // volumetric flow rate
  "pressure_rise_pa": 47.2,       // static pressure rise (outlet - inlet)
  "torque_nm": 0.00834,           // total shaft torque (all rotors)
  "shaft_power_w": 4.37,          // torque × omega
  "efficiency": 0.376,            // ΔP × Q / P_shaft (hydraulic efficiency)
  "mesh": {
    "n_cells": 120340,
    "max_non_ortho": 41.2,        // <65° is generally acceptable
    "max_skewness": 1.74,         // <4 is acceptable
    "ok": true
  },
  "convergence": {
    "converged": true,
    "n_iterations": 500,
    "final_residuals": { "Ux": 1.2e-05, "p": 2.8e-06, ... }
  }
}
```

**Mesh quality targets**: max_non_ortho < 65°, max_skewness < 4. Values above these suggest the mesh may need refinement or a smaller base_cell_size_m.

**Efficiency interpretation**: Values of 0.3–0.6 are typical for small axial fans at design point with a simple MRF model. Real-world fans achieve 0.6–0.85 with more careful blade design and finer meshes.

---

## Limitations

1. **Steady-state MRF only**: The MRF approach is an approximation for rotating machinery. It neglects rotor-stator interaction and is only accurate when the gap between rotor and stator is reasonably large (>10% of the blade pitch). For transient effects, use pimpleFoam with AMI (Arbitrarily Moving Interface) — not implemented here.

2. **Mesh convergence**: The default mesh parameters are conservative. For publishable results, perform a mesh independence study by halving base_cell_size_m and comparing results.

3. **Turbulence model**: kOmegaSST is recommended for turbomachinery but is still an approximation. Transitional effects (common at low Reynolds numbers) are not captured.

4. **Turbomolecular pumps**: The `example_turbomolecular_style.yaml` config generates geometry only. At TMP operating pressures (10⁻³–10⁻⁷ Pa), the Knudsen number Kn >> 1, and continuum Navier-Stokes equations are invalid. Use DSMC codes (dsmcFoam+, SPARTA) for that regime.

5. **No AMI/sliding mesh**: Counter-rotating stages are modelled with separate MRF zones assuming steady interaction. Transient AMI would be more accurate for counter-rotating pairs.

6. **Postprocessing requires function objects**: Pressure rise and flow rate extraction depends on OpenFOAM function object output. If the solver fails before writing function object data, results will be NaN.

---

## Extending the codebase

### New geometry backend

Add a new geometry module under `fan_cfd/geometry/` and implement the interface used by `stage_geometry.generate_stage_geometry()`. The function must return a list of `trimesh.Trimesh` objects (one per blade).

### New optimizer

Subclass `FanOptimizer` and implement `suggest_next(history) -> FanCFDConfig`. Register it in `scripts/optimize.py`'s `OPTIMIZERS` dict.

### New solver backend

Subclass `SolverBackend` in `fan_cfd/optimization/optimizer.py` and implement `run(case_dir, config)`. The `RarefiedFlowBackend` stub is already there as an example.

### New airfoil family

Add a function to `fan_cfd/geometry/blade_profiles.py` following the same signature as `naca4digit_upper_lower()`. Update `_make_section_3d()` in `stage_geometry.py` to dispatch to your new function based on `airfoil_code`.

---

## Troubleshooting

**`blockMesh` fails with "Command not found"**
OpenFOAM is not sourced. Run: `source /opt/openfoam*/etc/bashrc` and try again.

**`snappyHexMesh` runs but produces 0 cells**
The `locationInMesh` point is outside the geometry. Check that `domain_length_factor` is large enough and that the fan geometry STL files are positioned correctly (check STL files in a viewer like Paraview or Meshlab).

**Solver diverges immediately**
- Reduce inlet velocity (`velocity_m_s`)
- Increase relaxation under-relaxation (reduce 0.7 to 0.5 in fvSolution)
- Run more blockMesh iterations or coarsen the base mesh

**Efficiency is NaN**
No function object output was found. This happens when the solver fails before writing postProcessing/ data. Check `log.simpleFoam` in the case directory.

**Geometry generation fails with trimesh errors**
Ensure trimesh ≥ 4.0 is installed: `pip install "trimesh>=4.0"`. The boolean operations (duct generation) may fail on some platforms; the code falls back gracefully to a solid cylinder.

**Tests fail with ImportError**
Run `pip install -e .` from the project root to install the package in editable mode.
