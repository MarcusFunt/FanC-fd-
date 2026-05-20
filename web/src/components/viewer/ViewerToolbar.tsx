import { Box, Eye, RefreshCcw, Rows3 } from "lucide-react";
import type { StlFileItem } from "../../types/api";

interface ViewerToolbarProps {
  files: StlFileItem[];
  visible: Set<string>;
  mode: "solid" | "wireframe" | "xray";
  onToggleFile: (name: string) => void;
  onModeChange: (mode: "solid" | "wireframe" | "xray") => void;
  onResetCamera: () => void;
}

export default function ViewerToolbar({
  files,
  visible,
  mode,
  onToggleFile,
  onModeChange,
  onResetCamera
}: ViewerToolbarProps) {
  return (
    <aside className="viewer-toolbar">
      <div className="panel-header">
        <div>
          <h2>Geometry</h2>
          <p>{files.length} STL file(s)</p>
        </div>
        <button className="icon-button" type="button" onClick={onResetCamera} aria-label="Reset camera">
          <RefreshCcw size={17} />
        </button>
      </div>

      <div className="viewer-mode">
        <button className={mode === "solid" ? "selected" : ""} type="button" onClick={() => onModeChange("solid")}>
          <Box size={16} />
          Solid
        </button>
        <button className={mode === "wireframe" ? "selected" : ""} type="button" onClick={() => onModeChange("wireframe")}>
          <Rows3 size={16} />
          Wire
        </button>
        <button className={mode === "xray" ? "selected" : ""} type="button" onClick={() => onModeChange("xray")}>
          <Eye size={16} />
          X-ray
        </button>
      </div>

      <div className="stl-checks">
        {files.map((file) => (
          <label key={file.name} className="check-row">
            <input
              type="checkbox"
              checked={visible.has(file.name)}
              onChange={() => onToggleFile(file.name)}
            />
            <span>{file.name}</span>
          </label>
        ))}
        {files.length === 0 && <div className="empty-state">No STL files found for this run.</div>}
      </div>
    </aside>
  );
}

