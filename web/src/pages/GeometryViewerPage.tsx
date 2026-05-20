import { useQuery } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import { useParams } from "react-router-dom";
import { jobsApi, resultsApi } from "../api/client";
import GeometryScene from "../components/viewer/GeometryScene";
import ViewerToolbar from "../components/viewer/ViewerToolbar";

export default function GeometryViewerPage() {
  const params = useParams();
  const [mode, setMode] = useState<"solid" | "wireframe" | "xray">("solid");
  const [visible, setVisible] = useState<Set<string>>(new Set());
  const [resetKey, setResetKey] = useState(0);

  const jobsQuery = useQuery({
    queryKey: ["jobs"],
    queryFn: jobsApi.list,
    enabled: params.runId === "latest"
  });
  const runId = useMemo(() => {
    if (params.runId && params.runId !== "latest") {
      return params.runId;
    }
    return jobsQuery.data?.[0]?.run_id;
  }, [jobsQuery.data, params.runId]);

  const stlQuery = useQuery({
    queryKey: ["stl-files", runId],
    queryFn: () => resultsApi.stlFiles(runId!),
    enabled: Boolean(runId)
  });

  useEffect(() => {
    if (stlQuery.data) {
      setVisible(new Set(stlQuery.data.map((file) => file.name)));
    }
  }, [stlQuery.data]);

  return (
    <div className="viewer-page">
      <ViewerToolbar
        files={stlQuery.data ?? []}
        visible={visible}
        mode={mode}
        onToggleFile={(name) =>
          setVisible((current) => {
            const next = new Set(current);
            if (next.has(name)) {
              next.delete(name);
            } else {
              next.add(name);
            }
            return next;
          })
        }
        onModeChange={setMode}
        onResetCamera={() => setResetKey((value) => value + 1)}
      />
      <section className="viewer-stage">
        <header className="page-header compact">
          <div>
            <h1>{runId ?? "Geometry viewer"}</h1>
            <p>STL files are served from the FastAPI runs mount.</p>
          </div>
        </header>
        {runId ? (
          <GeometryScene
            files={stlQuery.data ?? []}
            visible={visible}
            mode={mode}
            resetKey={resetKey}
          />
        ) : (
          <div className="empty-state wide">Launch or select a geometry job to inspect STL files.</div>
        )}
      </section>
    </div>
  );
}

