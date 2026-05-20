import { create } from "zustand";
import type { ConfigDetail, ValidationResponse } from "../types/api";

interface ConfigStore {
  activeConfigId: string | null;
  activeConfig: ConfigDetail | null;
  draftYaml: string;
  validation: ValidationResponse | null;
  setActiveConfig: (config: ConfigDetail | null) => void;
  setDraftYaml: (yaml: string) => void;
  setValidation: (validation: ValidationResponse | null) => void;
}

export const useConfigStore = create<ConfigStore>((set) => ({
  activeConfigId: null,
  activeConfig: null,
  draftYaml: "",
  validation: null,
  setActiveConfig: (config) =>
    set({
      activeConfig: config,
      activeConfigId: config?.id ?? null,
      draftYaml: config?.yaml_text ?? ""
    }),
  setDraftYaml: (draftYaml) => set({ draftYaml }),
  setValidation: (validation) => set({ validation })
}));

