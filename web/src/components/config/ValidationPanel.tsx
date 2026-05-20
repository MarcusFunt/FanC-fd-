import { AlertTriangle, CheckCircle2 } from "lucide-react";
import type { ValidationResponse } from "../../types/api";

interface ValidationPanelProps {
  validation: ValidationResponse | null;
}

export default function ValidationPanel({ validation }: ValidationPanelProps) {
  if (!validation) {
    return (
      <aside className="validation-panel idle">
        <CheckCircle2 size={18} />
        <span>Validation has not run yet.</span>
      </aside>
    );
  }

  if (validation.valid) {
    return (
      <aside className="validation-panel valid">
        <CheckCircle2 size={18} />
        <span>Config validates against FanCFDConfig.</span>
      </aside>
    );
  }

  return (
    <aside className="validation-panel invalid">
      <div className="validation-heading">
        <AlertTriangle size={18} />
        <span>{validation.errors.length} validation issue(s)</span>
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

