import { AlertTriangle, CheckCircle2 } from "lucide-react";
import type { ValidationResponse } from "../../types/api";

interface ValidationPanelProps {
  validation: ValidationResponse | null;
}

export default function ValidationPanel({ validation }: ValidationPanelProps) {
  if (!validation) {
    return (
      <aside className="validation-panel idle">
        <div className="validation-heading">
          <CheckCircle2 size={18} />
          <strong>Readiness</strong>
        </div>
        <span>Auto-validation will run as the configuration changes.</span>
      </aside>
    );
  }

  if (validation.valid) {
    return (
      <aside className="validation-panel valid">
        <div className="validation-heading">
          <CheckCircle2 size={18} />
          <strong>Ready to launch</strong>
        </div>
        <span>Config validates against FanCFDConfig.</span>
      </aside>
    );
  }

  return (
    <aside className="validation-panel invalid">
      <div className="validation-heading">
        <AlertTriangle size={18} />
        <strong>{validation.errors.length} validation issue(s)</strong>
      </div>
      <div className="validation-list">
        {validation.errors.map((error, index) => (
          <a key={`${error.path}-${index}`} href={`#field-${error.path.replaceAll(".", "-")}`}>
            <strong>{error.path || "root"}</strong>
            <span>{error.msg}</span>
          </a>
        ))}
      </div>
    </aside>
  );
}
