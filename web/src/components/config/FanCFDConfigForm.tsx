import {
  DndContext,
  PointerSensor,
  closestCenter,
  useSensor,
  useSensors,
  type DragEndEvent
} from "@dnd-kit/core";
import {
  SortableContext,
  useSortable,
  verticalListSortingStrategy
} from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import {
  ChevronDown,
  GripVertical,
  Plus,
  Sparkles,
  Trash2
} from "lucide-react";
import type { ReactNode } from "react";
import {
  FieldErrors,
  UseFormReturn,
  useFieldArray,
  useWatch
} from "react-hook-form";
import { migrateProfile, useFieldError } from "../../hooks/useConfigForm";
import {
  createDefaultProfile,
  type FanCFDConfig,
  type Profile,
  type ProfileType,
  type StageConfig
} from "../../types/config";

interface FanCFDConfigFormProps {
  form: UseFormReturn<FanCFDConfig>;
}

export default function FanCFDConfigForm({ form }: FanCFDConfigFormProps) {
  const { register, control, setValue, watch, formState } = form;
  const duct = useWatch({ control, name: "fan.duct" });

  return (
    <div className="config-form">
      <section className="form-section">
        <div className="section-heading">
          <h2>Fan</h2>
          <span>Geometry envelope</span>
        </div>
        <div className="field-grid four">
          <Field label="Name" path="fan.name" errors={formState.errors}>
            <input {...register("fan.name")} />
          </Field>
          <Field label="Max diameter (m)" path="fan.max_diameter_m" errors={formState.errors}>
            <input type="number" step="0.001" {...register("fan.max_diameter_m", { valueAsNumber: true })} />
          </Field>
          <Field label="Hub diameter (m)" path="fan.hub_diameter_m" errors={formState.errors}>
            <input type="number" step="0.001" {...register("fan.hub_diameter_m", { valueAsNumber: true })} />
          </Field>
          <Field label="RPM" path="fan.rpm" errors={formState.errors}>
            <input type="number" step="10" {...register("fan.rpm", { valueAsNumber: true })} />
          </Field>
        </div>

        <details className="collapsible" open={Boolean(duct)}>
          <summary>
            <ChevronDown size={16} />
            Duct
            <label className="switch" onClick={(event) => event.stopPropagation()}>
              <input
                type="checkbox"
                checked={Boolean(duct)}
                onChange={(event) => {
                  setValue(
                    "fan.duct",
                    event.target.checked
                      ? {
                          enabled: true,
                          inner_diameter_m: watch("fan.max_diameter_m"),
                          wall_thickness_m: 0.003,
                          total_length_m: 0.16,
                          inlet_clearance_m: 0.01,
                          outlet_clearance_m: 0.01
                        }
                      : null,
                    { shouldDirty: true, shouldValidate: true }
                  );
                }}
              />
              <span />
            </label>
          </summary>
          {duct && (
            <div className="field-grid five">
              <Field label="Inner diameter (m)" path="fan.duct.inner_diameter_m" errors={formState.errors}>
                <input type="number" step="0.001" {...register("fan.duct.inner_diameter_m", { valueAsNumber: true })} />
              </Field>
              <Field label="Wall thickness (m)" path="fan.duct.wall_thickness_m" errors={formState.errors}>
                <input type="number" step="0.001" {...register("fan.duct.wall_thickness_m", { valueAsNumber: true })} />
              </Field>
              <Field label="Total length (m)" path="fan.duct.total_length_m" errors={formState.errors}>
                <input type="number" step="0.001" {...register("fan.duct.total_length_m", { valueAsNumber: true })} />
              </Field>
              <Field label="Inlet clearance (m)" path="fan.duct.inlet_clearance_m" errors={formState.errors}>
                <input type="number" step="0.001" {...register("fan.duct.inlet_clearance_m", { valueAsNumber: true })} />
              </Field>
              <Field label="Outlet clearance (m)" path="fan.duct.outlet_clearance_m" errors={formState.errors}>
                <input type="number" step="0.001" {...register("fan.duct.outlet_clearance_m", { valueAsNumber: true })} />
              </Field>
            </div>
          )}
        </details>
      </section>

      <StagesList form={form} />

      <section className="form-section">
        <div className="section-heading">
          <h2>CFD</h2>
          <span>Solver, mesh, and boundary setup</span>
        </div>
        <div className="field-grid four">
          <Field label="Solver" path="cfd.solver" errors={formState.errors}>
            <input {...register("cfd.solver")} />
          </Field>
          <Field label="Rotation model" path="cfd.rotation_model" errors={formState.errors}>
            <input {...register("cfd.rotation_model")} />
          </Field>
          <Field label="Turbulence model" path="cfd.turbulence_model" errors={formState.errors}>
            <input {...register("cfd.turbulence_model")} />
          </Field>
          <Field label="Iterations" path="cfd.run.n_iterations" errors={formState.errors}>
            <input type="number" {...register("cfd.run.n_iterations", { valueAsNumber: true })} />
          </Field>
        </div>
        <div className="field-grid four">
          <Field label="Inlet velocity (m/s)" path="cfd.inlet.velocity_m_s" errors={formState.errors}>
            <input type="number" step="0.1" {...register("cfd.inlet.velocity_m_s", { valueAsNumber: true })} />
          </Field>
          <Field label="Outlet velocity (m/s)" path="cfd.outlet.velocity_m_s" errors={formState.errors}>
            <input type="number" step="0.1" {...register("cfd.outlet.velocity_m_s", { valueAsNumber: true })} />
          </Field>
          <Field label="Base cell size (m)" path="cfd.mesh.base_cell_size_m" errors={formState.errors}>
            <input type="number" step="0.001" {...register("cfd.mesh.base_cell_size_m", { valueAsNumber: true })} />
          </Field>
          <Field label="Refinement" path="cfd.mesh.refinement_levels" errors={formState.errors}>
            <input type="number" {...register("cfd.mesh.refinement_levels", { valueAsNumber: true })} />
          </Field>
        </div>
        <label className="check-row">
          <input type="checkbox" {...register("cfd.run.parallel")} />
          Parallel OpenFOAM run
        </label>
      </section>

      <section className="form-section">
        <div className="section-heading">
          <h2>Objective</h2>
          <span>Optimization target</span>
        </div>
        <div className="field-grid three">
          <Field label="Mode" path="objective.mode" errors={formState.errors}>
            <select {...register("objective.mode")}>
              <option value="single">Single</option>
              <option value="multi_objective">Multi objective</option>
            </select>
          </Field>
          <Field label="Maximize" path="objective.maximize" errors={formState.errors}>
            <select {...register("objective.maximize")}>
              <option value="efficiency">Efficiency</option>
              <option value="pressure_rise">Pressure rise</option>
              <option value="flow_rate">Flow rate</option>
            </select>
          </Field>
          <Field label="Min pressure rise (Pa)" path="objective.constraints.min_pressure_rise_pa" errors={formState.errors}>
            <input
              type="number"
              step="1"
              {...register("objective.constraints.min_pressure_rise_pa", { valueAsNumber: true })}
            />
          </Field>
        </div>
      </section>
    </div>
  );
}

function StagesList({ form }: FanCFDConfigFormProps) {
  const { control } = form;
  const { fields, append, remove, move } = useFieldArray({
    control,
    name: "fan.stages"
  });
  const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 6 } }));

  const onDragEnd = (event: DragEndEvent) => {
    const { active, over } = event;
    if (!over || active.id === over.id) {
      return;
    }
    const oldIndex = fields.findIndex((field) => field.id === active.id);
    const newIndex = fields.findIndex((field) => field.id === over.id);
    if (oldIndex >= 0 && newIndex >= 0) {
      move(oldIndex, newIndex);
    }
  };

  return (
    <section className="form-section">
      <div className="section-heading row">
        <div>
          <h2>Stages</h2>
          <span>Rotor and stator stack</span>
        </div>
        <button
          type="button"
          className="button compact"
          onClick={() => append(createStage(fields.length))}
        >
          <Plus size={15} />
          Stage
        </button>
      </div>
      <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={onDragEnd}>
        <SortableContext items={fields.map((field) => field.id)} strategy={verticalListSortingStrategy}>
          <div className="stage-stack">
            {fields.map((field, index) => (
              <StageCard
                key={field.id}
                sortableId={field.id}
                index={index}
                form={form}
                onRemove={() => remove(index)}
                canRemove={fields.length > 1}
              />
            ))}
          </div>
        </SortableContext>
      </DndContext>
    </section>
  );
}

interface StageCardProps {
  sortableId: string;
  index: number;
  form: UseFormReturn<FanCFDConfig>;
  onRemove: () => void;
  canRemove: boolean;
}

function StageCard({ sortableId, index, form, onRemove, canRemove }: StageCardProps) {
  const { attributes, listeners, setNodeRef, transform, transition } = useSortable({ id: sortableId });
  const { register, formState } = form;
  const style = {
    transform: CSS.Transform.toString(transform),
    transition
  };
  const stages = form.watch("fan.stages");
  const stageNames = stages.map((stage) => stage.name).filter(Boolean);

  return (
    <article ref={setNodeRef} style={style} className="stage-card">
      <div className="stage-card-header">
        <button className="drag-handle" type="button" {...attributes} {...listeners} aria-label="Reorder stage">
          <GripVertical size={16} />
        </button>
        <div className="stage-title">
          <strong>{form.watch(`fan.stages.${index}.name`) || `stage_${index + 1}`}</strong>
          <span>{form.watch(`fan.stages.${index}.type`)}</span>
        </div>
        <button
          className="icon-button danger"
          type="button"
          onClick={onRemove}
          disabled={!canRemove}
          aria-label="Remove stage"
        >
          <Trash2 size={16} />
        </button>
      </div>

      <div className="field-grid five">
        <Field label="Name" path={`fan.stages.${index}.name`} errors={formState.errors}>
          <input {...register(`fan.stages.${index}.name`)} />
        </Field>
        <Field label="Type" path={`fan.stages.${index}.type`} errors={formState.errors}>
          <select {...register(`fan.stages.${index}.type`)}>
            <option value="rotor">Rotor</option>
            <option value="stator">Stator</option>
          </select>
        </Field>
        <Field label="Axial position (m)" path={`fan.stages.${index}.axial_position_m`} errors={formState.errors}>
          <input type="number" step="0.001" {...register(`fan.stages.${index}.axial_position_m`, { valueAsNumber: true })} />
        </Field>
        <Field label="Blade count" path={`fan.stages.${index}.blade_count`} errors={formState.errors}>
          <input type="number" {...register(`fan.stages.${index}.blade_count`, { valueAsNumber: true })} />
        </Field>
        <Field label="RPM" path={`fan.stages.${index}.rpm`} errors={formState.errors}>
          <input
            type="number"
            {...register(`fan.stages.${index}.rpm`, {
              setValueAs: (value) => (value === "" ? null : Number(value))
            })}
          />
        </Field>
      </div>

      <div className="blade-panel">
        <div className="field-grid three">
          <Field label="Airfoil" path={`fan.stages.${index}.blade.airfoil`} errors={formState.errors}>
            <input {...register(`fan.stages.${index}.blade.airfoil`)} />
          </Field>
          <Field label="Radial sections" path={`fan.stages.${index}.blade.radial_sections`} errors={formState.errors}>
            <input type="number" {...register(`fan.stages.${index}.blade.radial_sections`, { valueAsNumber: true })} />
          </Field>
          <Field label="Thickness scale" path={`fan.stages.${index}.blade.thickness_scale`} errors={formState.errors}>
            <input type="number" step="0.05" {...register(`fan.stages.${index}.blade.thickness_scale`, { valueAsNumber: true })} />
          </Field>
        </div>
        <div className="profile-grid">
          <ProfileEditor
            label="Chord"
            path={`fan.stages.${index}.blade.chord_profile`}
            stageNames={stageNames}
            form={form}
          />
          <ProfileEditor
            label="Twist"
            path={`fan.stages.${index}.blade.twist_profile_deg`}
            stageNames={stageNames}
            form={form}
          />
          <ProfileEditor
            label="Rake"
            path={`fan.stages.${index}.blade.rake_profile`}
            stageNames={stageNames}
            form={form}
            nullable
          />
          <ProfileEditor
            label="Skew"
            path={`fan.stages.${index}.blade.skew_profile`}
            stageNames={stageNames}
            form={form}
            nullable
          />
        </div>
      </div>
    </article>
  );
}

interface ProfileEditorProps {
  label: string;
  path: string;
  form: UseFormReturn<FanCFDConfig>;
  stageNames: string[];
  nullable?: boolean;
}

function ProfileEditor({ label, path, form, stageNames, nullable }: ProfileEditorProps) {
  const profile = form.watch(path as never) as unknown as Profile | null | undefined;
  const activeProfile = profile ?? createDefaultProfile(0);
  const points = activeProfile.points ?? [];
  const stageFallback = stageNames[0];

  if (nullable && !profile) {
    return (
      <div className="profile-editor disabled-profile">
        <div className="profile-header">
          <strong>{label}</strong>
          <button
            type="button"
            className="button compact"
            onClick={() => form.setValue(path as never, createDefaultProfile(0) as never, { shouldDirty: true })}
          >
            <Plus size={14} />
            Enable
          </button>
        </div>
      </div>
    );
  }

  const updatePoint = (index: number, coord: 0 | 1, value: number) => {
    const next = points.map((point, pointIndex) =>
      pointIndex === index ? ([coord === 0 ? value : point[0], coord === 1 ? value : point[1]] as [number, number]) : point
    );
    form.setValue(`${path}.points` as never, next as never, { shouldDirty: true, shouldValidate: true });
  };

  return (
    <div className="profile-editor" id={`field-${path.replaceAll(".", "-")}`}>
      <div className="profile-header">
        <strong>{label}</strong>
        {nullable && (
          <button
            type="button"
            className="icon-button"
            onClick={() => form.setValue(path as never, null as never, { shouldDirty: true })}
            aria-label={`Disable ${label}`}
          >
            <Trash2 size={14} />
          </button>
        )}
      </div>
      <div className="profile-controls">
        <select
          value={activeProfile.type}
          onChange={(event) => {
            form.setValue(
              path as never,
              migrateProfile(activeProfile, event.target.value as ProfileType, stageFallback) as never,
              { shouldDirty: true, shouldValidate: true }
            );
          }}
        >
          <option value="constant">Constant</option>
          <option value="linear">Linear</option>
          <option value="control_points">Control points</option>
          <option value="inherit">Inherit</option>
        </select>

        {activeProfile.type === "constant" && (
          <input
            type="number"
            step="0.001"
            value={activeProfile.value ?? 0}
            onChange={(event) =>
              form.setValue(`${path}.value` as never, Number(event.target.value) as never, {
                shouldDirty: true,
                shouldValidate: true
              })
            }
          />
        )}

        {activeProfile.type === "inherit" && (
          <div className="inherit-row">
            <select
              value={activeProfile.from_stage ?? ""}
              onChange={(event) =>
                form.setValue(`${path}.from_stage` as never, event.target.value as never, {
                  shouldDirty: true,
                  shouldValidate: true
                })
              }
            >
              {stageNames.map((stageName) => (
                <option key={stageName} value={stageName}>
                  {stageName}
                </option>
              ))}
            </select>
            <input
              type="number"
              step="0.05"
              value={activeProfile.scale ?? 1}
              onChange={(event) =>
                form.setValue(`${path}.scale` as never, Number(event.target.value) as never, {
                  shouldDirty: true,
                  shouldValidate: true
                })
              }
            />
          </div>
        )}
      </div>

      {(activeProfile.type === "linear" || activeProfile.type === "control_points") && (
        <>
          <ProfileSparkline points={points} />
          <div className="points-table">
            {points.map((point, pointIndex) => (
              <div key={pointIndex} className="points-row">
                <input
                  type="number"
                  step="0.05"
                  value={point[0]}
                  onChange={(event) => updatePoint(pointIndex, 0, Number(event.target.value))}
                />
                <input
                  type="number"
                  step="0.001"
                  value={point[1]}
                  onChange={(event) => updatePoint(pointIndex, 1, Number(event.target.value))}
                />
              </div>
            ))}
          </div>
          {activeProfile.type === "control_points" && (
            <button
              type="button"
              className="button compact ghost"
              onClick={() =>
                form.setValue(
                  `${path}.points` as never,
                  [...points, [1, points.at(-1)?.[1] ?? 0]] as never,
                  { shouldDirty: true, shouldValidate: true }
                )
              }
            >
              <Sparkles size={14} />
              Point
            </button>
          )}
        </>
      )}
    </div>
  );
}

function ProfileSparkline({ points }: { points: Array<[number, number]> }) {
  if (points.length < 2) {
    return <div className="sparkline empty" />;
  }
  const values = points.map((point) => point[1]);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min || 1;
  const d = points
    .map((point, index) => {
      const x = Math.max(0, Math.min(1, point[0])) * 100;
      const y = 34 - ((point[1] - min) / range) * 28;
      return `${index === 0 ? "M" : "L"} ${x.toFixed(2)} ${y.toFixed(2)}`;
    })
    .join(" ");

  return (
    <svg className="sparkline" viewBox="0 0 100 40" aria-hidden="true">
      <path d={d} />
    </svg>
  );
}

function Field({
  label,
  path,
  errors,
  children
}: {
  label: string;
  path: string;
  errors: FieldErrors<FanCFDConfig>;
  children: ReactNode;
}) {
  const error = useFieldError(errors, path);
  return (
    <label className={`field ${error?.message ? "has-error" : ""}`} id={`field-${path.replaceAll(".", "-")}`}>
      <span>{label}</span>
      {children}
      {error?.message && <em>{error.message}</em>}
    </label>
  );
}

function createStage(index: number): StageConfig {
  return {
    name: `rotor_${index + 1}`,
    type: "rotor",
    axial_position_m: Number((index * 0.04).toFixed(3)),
    blade_count: 5,
    rpm: 5000,
    rotation_direction: "counterclockwise",
    blade: {
      airfoil: "naca4412",
      radial_sections: 9,
      chord_profile: {
        type: "linear",
        points: [
          [0, 0.03],
          [1, 0.02]
        ],
        value: null,
        from_stage: null,
        scale: 1
      },
      twist_profile_deg: {
        type: "linear",
        points: [
          [0, 42],
          [1, 18]
        ],
        value: null,
        from_stage: null,
        scale: 1
      },
      thickness_scale: 1,
      rake_profile: null,
      skew_profile: null
    }
  };
}
