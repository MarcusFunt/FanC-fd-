import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, FilePlus2, Play, Save, Sparkles, Trash2 } from "lucide-react";
import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { configsApi } from "../api/client";
import FanCFDConfigForm from "../components/config/FanCFDConfigForm";
import LaunchJobModal from "../components/config/LaunchJobModal";
import ValidationPanel from "../components/config/ValidationPanel";
import YamlEditor from "../components/config/YamlEditor";
import { useConfigForm } from "../hooks/useConfigForm";
import { useConfigStore } from "../store/configStore";
import { createJetengineInspiredConfig } from "../types/config";

export default function ConfigBuilderPage() {
  const { configId } = useParams();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const editor = useConfigForm();
  const { resetWithConfig } = editor;
  const [launchOpen, setLaunchOpen] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const activeConfigId = useConfigStore((state) => state.activeConfigId);
  const setActiveConfig = useConfigStore((state) => state.setActiveConfig);

  const configsQuery = useQuery({
    queryKey: ["configs"],
    queryFn: configsApi.list
  });

  const detailQuery = useQuery({
    queryKey: ["configs", configId],
    queryFn: () => configsApi.get(configId!),
    enabled: Boolean(configId)
  });

  useEffect(() => {
    if (detailQuery.data?.data) {
      resetWithConfig(detailQuery.data.data);
      setActiveConfig(detailQuery.data);
    }
  }, [detailQuery.data, resetWithConfig, setActiveConfig]);

  const saveMutation = useMutation({
    mutationFn: async () => {
      const validation = await editor.validate();
      if (!validation.valid) {
        throw new Error("Resolve validation issues before saving.");
      }
      const payload =
        editor.activeTab === "yaml"
          ? { yaml_text: editor.yamlText }
          : { data: editor.form.getValues() };
      return configId
        ? configsApi.update(configId, payload)
        : configsApi.save({ id: editor.form.getValues("fan.name"), ...payload });
    },
    onSuccess: async (saved) => {
      setSaveError(null);
      setActiveConfig(saved);
      await queryClient.invalidateQueries({ queryKey: ["configs"] });
      navigate(`/config/${saved.id}`, { replace: true });
    },
    onError: (error) => {
      setSaveError(error instanceof Error ? error.message : "Save failed.");
    }
  });

  const removeConfig = async (id: string) => {
    await configsApi.remove(id);
    await queryClient.invalidateQueries({ queryKey: ["configs"] });
    if (configId === id) {
      setActiveConfig(null);
      navigate("/config");
    }
  };

  const loadJetenginePreset = () => {
    resetWithConfig(createJetengineInspiredConfig());
    setActiveConfig(null);
    setSaveError(null);
    if (configId) {
      navigate("/config", { replace: true });
    }
  };

  return (
    <div className="workspace config-workspace">
      <aside className="list-panel config-sidebar">
        <div className="panel-header">
          <div>
            <h2>Configs</h2>
            <p>{configsQuery.data?.length ?? 0} saved YAML files</p>
          </div>
          <Link className="icon-button" to="/config" aria-label="New config">
            <FilePlus2 size={17} />
          </Link>
        </div>
        <div className="config-list">
          {configsQuery.data?.map((config) => (
            <Link
              key={config.id}
              className={`config-row ${config.id === configId ? "selected" : ""}`}
              to={`/config/${config.id}`}
            >
              <div>
                <strong>{config.fan_name ?? config.id}</strong>
                <span>{config.stages ?? 0} stage(s)</span>
              </div>
              <button
                type="button"
                className="icon-button danger"
                aria-label={`Delete ${config.id}`}
                onClick={(event) => {
                  event.preventDefault();
                  void removeConfig(config.id);
                }}
              >
                <Trash2 size={15} />
              </button>
            </Link>
          ))}
        </div>
      </aside>

      <section className="editor-panel">
        <header className="page-header">
          <div>
            <h1>{configId ? detailQuery.data?.fan_name ?? configId : "New configuration"}</h1>
            <p>Build the fan model, validate against Pydantic, then launch CLI-backed jobs.</p>
          </div>
          <div className="header-actions">
            <button
              className="button"
              type="button"
              onClick={loadJetenginePreset}
              title="Load the jetengine-inspired axial compressor preset"
            >
              <Sparkles size={16} />
              Jetengine
            </button>
            <button className="button" type="button" onClick={() => editor.validate()}>
              <Check size={16} />
              Validate
            </button>
            <button
              className="button"
              type="button"
              onClick={() => saveMutation.mutate()}
              disabled={saveMutation.isPending}
            >
              <Save size={16} />
              {saveMutation.isPending ? "Saving" : "Save"}
            </button>
            <button className="button primary" type="button" onClick={() => setLaunchOpen(true)}>
              <Play size={16} />
              Launch
            </button>
          </div>
        </header>

        <div className="editor-tabs">
          <button
            type="button"
            className={editor.activeTab === "form" ? "selected" : ""}
            onClick={() => editor.setActiveTab("form")}
          >
            Form
          </button>
          <button
            type="button"
            className={editor.activeTab === "yaml" ? "selected" : ""}
            onClick={() => editor.setActiveTab("yaml")}
          >
            YAML
          </button>
          {editor.activeTab === "yaml" && (
            <button type="button" className="button compact ghost" onClick={editor.syncYamlToForm}>
              Apply YAML
            </button>
          )}
        </div>

        {saveError && <div className="inline-error">{saveError}</div>}

        <div className="editor-content">
          {editor.activeTab === "form" ? (
            <FanCFDConfigForm form={editor.form} />
          ) : (
            <YamlEditor value={editor.yamlText} onChange={editor.setYamlText} />
          )}
        </div>
      </section>

      <ValidationPanel validation={editor.validation} />
      <LaunchJobModal
        configId={activeConfigId ?? configId ?? null}
        open={launchOpen}
        onClose={() => setLaunchOpen(false)}
      />
    </div>
  );
}
