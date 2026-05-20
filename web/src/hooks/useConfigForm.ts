import { useCallback, useEffect, useMemo, useState } from "react";
import { FieldErrors, FieldPath, useForm, useWatch } from "react-hook-form";
import yaml from "js-yaml";
import { configsApi } from "../api/client";
import type { ValidationResponse } from "../types/api";
import {
  createDefaultConfig,
  type FanCFDConfig,
  type Profile,
  type ProfileType
} from "../types/config";

export type ConfigEditorTab = "form" | "yaml";

export function useConfigForm() {
  const form = useForm<FanCFDConfig>({
    defaultValues: createDefaultConfig(),
    mode: "onChange"
  });
  const watched = useWatch({ control: form.control });
  const [activeTab, setActiveTab] = useState<ConfigEditorTab>("form");
  const [yamlText, setYamlText] = useState(() =>
    yaml.dump(createDefaultConfig(), { sortKeys: false })
  );
  const [validation, setValidation] = useState<ValidationResponse | null>(null);

  useEffect(() => {
    if (activeTab !== "form") {
      return;
    }
    setYamlText(yaml.dump(watched, { sortKeys: false }));
  }, [activeTab, watched]);

  const resetWithConfig = useCallback(
    (config: FanCFDConfig) => {
      form.reset(config);
      setYamlText(yaml.dump(config, { sortKeys: false }));
      setValidation(null);
    },
    [form]
  );

  const syncYamlToForm = useCallback(() => {
    try {
      const parsed = yaml.load(yamlText);
      if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
        throw new Error("YAML root must be a config object.");
      }
      form.clearErrors();
      form.reset(parsed as FanCFDConfig);
      setValidation(null);
      setActiveTab("form");
    } catch (error) {
      setValidation({
        valid: false,
        data: null,
        errors: [
          {
            loc: [],
            path: "",
            msg: error instanceof Error ? error.message : "Invalid YAML.",
            type: "yaml_parse_error"
          }
        ]
      });
    }
  }, [form, yamlText]);

  const validate = useCallback(async () => {
    form.clearErrors();
    const payload =
      activeTab === "yaml" ? { yaml_text: yamlText } : { data: form.getValues() };
    const response = await configsApi.validate(payload);
    setValidation(response);

    if (!response.valid) {
      response.errors.forEach((error) => {
        if (error.path) {
          form.setError(error.path as FieldPath<FanCFDConfig>, {
            type: error.type ?? "server",
            message: error.msg
          });
        }
      });
    }
    return response;
  }, [activeTab, form, yamlText]);

  useEffect(() => {
    if (activeTab !== "form") {
      return;
    }
    const handle = window.setTimeout(() => {
      void validate().catch(() => undefined);
    }, 500);
    return () => window.clearTimeout(handle);
  }, [activeTab, validate]);

  return {
    form,
    activeTab,
    setActiveTab,
    yamlText,
    setYamlText,
    validation,
    setValidation,
    resetWithConfig,
    syncYamlToForm,
    validate
  };
}

export function migrateProfile(
  profile: Profile | null | undefined,
  nextType: ProfileType,
  fallbackStage?: string
): Profile {
  const current = profile ?? { type: "constant", value: 0, scale: 1 };
  const value = profileValue(current);

  if (nextType === "constant") {
    return {
      type: "constant",
      value,
      points: null,
      from_stage: null,
      scale: current.scale ?? 1
    };
  }

  if (nextType === "linear") {
    const points =
      current.type === "control_points" && current.points && current.points.length >= 2
        ? [current.points[0], current.points[current.points.length - 1]]
        : [
            [0, value],
            [1, value]
          ];
    return {
      type: "linear",
      points: points as Array<[number, number]>,
      value: null,
      from_stage: null,
      scale: current.scale ?? 1
    };
  }

  if (nextType === "control_points") {
    const points =
      current.type === "linear" && current.points?.length === 2
        ? [
            current.points[0],
            [0.5, (current.points[0][1] + current.points[1][1]) / 2],
            current.points[1]
          ]
        : [
            [0, value],
            [0.5, value],
            [1, value]
          ];
    return {
      type: "control_points",
      points: points as Array<[number, number]>,
      value: null,
      from_stage: null,
      scale: current.scale ?? 1
    };
  }

  return {
    type: "inherit",
    points: null,
    value: null,
    from_stage: fallbackStage ?? "",
    scale: 1
  };
}

export function profileValue(profile: Profile): number {
  if (typeof profile.value === "number") {
    return profile.value;
  }
  if (profile.points?.length) {
    return profile.points[0][1];
  }
  return 0;
}

export function useFieldError(
  errors: FieldErrors<FanCFDConfig>,
  path: string
) {
  return useMemo(() => {
    return path.split(".").reduce<unknown>((acc, key) => {
      if (acc && typeof acc === "object") {
        return (acc as Record<string, unknown>)[key];
      }
      return undefined;
    }, errors) as { message?: string } | undefined;
  }, [errors, path]);
}
