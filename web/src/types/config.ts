export type ProfileType = "constant" | "linear" | "control_points" | "inherit";
export type StageType = "rotor" | "stator";

export interface Profile {
  type: ProfileType;
  points?: Array<[number, number]> | null;
  value?: number | null;
  from_stage?: string | null;
  scale?: number;
}

export interface BladeConfig {
  airfoil: string;
  radial_sections: number;
  chord_profile: Profile;
  twist_profile_deg: Profile;
  thickness_scale: number;
  rake_profile?: Profile | null;
  skew_profile?: Profile | null;
}

export interface StageConfig {
  name: string;
  type: StageType;
  axial_position_m: number;
  blade_count: number;
  blade: BladeConfig;
  rpm?: number | null;
  rotation_direction?: "clockwise" | "counterclockwise" | null;
}

export interface DuctConfig {
  enabled: boolean;
  inner_diameter_m: number;
  wall_thickness_m: number;
  total_length_m: number;
  inlet_clearance_m: number;
  outlet_clearance_m: number;
}

export interface FanConfig {
  name: string;
  max_diameter_m: number;
  hub_diameter_m: number;
  rpm: number;
  duct?: DuctConfig | null;
  stages: StageConfig[];
}

export interface BoundaryConfig {
  patch_name: string;
  velocity_m_s: number;
  turbulence_intensity: number;
  hydraulic_diameter_m: number;
}

export interface FluidConfig {
  nu_m2_s: number;
  rho_kg_m3: number;
}

export interface MeshConfig {
  base_cell_size_m: number;
  refinement_levels: number;
  boundary_layers: number;
  boundary_layer_expansion: number;
  domain_length_factor: number;
  n_processors: number;
}

export interface RunConfig {
  n_iterations: number;
  write_interval: number;
  convergence_residual: number;
  parallel: boolean;
  n_procs: number;
  purge_write: number;
}

export interface CFDConfig {
  solver: string;
  rotation_model: string;
  turbulence_model: string;
  inlet: BoundaryConfig;
  outlet: BoundaryConfig;
  fluid: FluidConfig;
  mesh: MeshConfig;
  run: RunConfig;
}

export interface ObjectiveConfig {
  mode: "single" | "multi_objective";
  maximize: string;
  constraints: Record<string, number>;
  weights: Record<string, number>;
}

export interface FanCFDConfig {
  fan: FanConfig;
  cfd: CFDConfig;
  objective: ObjectiveConfig;
}

export const createDefaultProfile = (value: number): Profile => ({
  type: "constant",
  value,
  points: null,
  from_stage: null,
  scale: 1
});

export const createDefaultConfig = (): FanCFDConfig => ({
  fan: {
    name: "new_fan",
    max_diameter_m: 0.12,
    hub_diameter_m: 0.03,
    rpm: 5000,
    duct: null,
    stages: [
      {
        name: "rotor_1",
        type: "rotor",
        axial_position_m: 0,
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
      }
    ]
  },
  cfd: {
    solver: "simpleFoam",
    rotation_model: "MRF",
    turbulence_model: "kOmegaSST",
    inlet: {
      patch_name: "inlet",
      velocity_m_s: 5,
      turbulence_intensity: 0.05,
      hydraulic_diameter_m: 0.12
    },
    outlet: {
      patch_name: "outlet",
      velocity_m_s: 5,
      turbulence_intensity: 0.05,
      hydraulic_diameter_m: 0.12
    },
    fluid: {
      nu_m2_s: 1.5e-5,
      rho_kg_m3: 1.225
    },
    mesh: {
      base_cell_size_m: 0.005,
      refinement_levels: 3,
      boundary_layers: 5,
      boundary_layer_expansion: 1.2,
      domain_length_factor: 5,
      n_processors: 4
    },
    run: {
      n_iterations: 500,
      write_interval: 100,
      convergence_residual: 1e-4,
      parallel: false,
      n_procs: 4,
      purge_write: 1
    }
  },
  objective: {
    mode: "single",
    maximize: "efficiency",
    constraints: {
      min_pressure_rise_pa: 10
    },
    weights: {}
  }
});

interface JetenginePresetStage {
  name: string;
  type: StageType;
  axialPosition: number;
  bladeCount: number;
  airfoil: string;
  chord: number;
  twistRootDeg: number;
  twistTipDeg: number;
  thicknessScale: number;
}

const jetenginePresetStages: JetenginePresetStage[] = [
  {
    name: "rotor_1",
    type: "rotor",
    axialPosition: 0.02,
    bladeCount: 24,
    airfoil: "naca2412",
    chord: 0.016258,
    twistRootDeg: -7.531,
    twistTipDeg: -54.33,
    thicknessScale: 1.35
  },
  {
    name: "stator_1",
    type: "stator",
    axialPosition: 0.044258,
    bladeCount: 24,
    airfoil: "naca0012",
    chord: 0.016258,
    twistRootDeg: 31.987,
    twistTipDeg: 20.547,
    thicknessScale: 1.15
  },
  {
    name: "rotor_2",
    type: "rotor",
    axialPosition: 0.068515,
    bladeCount: 25,
    airfoil: "naca2412",
    chord: 0.015756,
    twistRootDeg: -7.531,
    twistTipDeg: -54.33,
    thicknessScale: 1.35
  },
  {
    name: "stator_2",
    type: "stator",
    axialPosition: 0.092271,
    bladeCount: 25,
    airfoil: "naca0012",
    chord: 0.015756,
    twistRootDeg: 31.987,
    twistTipDeg: 20.547,
    thicknessScale: 1.15
  },
  {
    name: "rotor_3",
    type: "rotor",
    axialPosition: 0.116027,
    bladeCount: 25,
    airfoil: "naca2412",
    chord: 0.015283,
    twistRootDeg: -7.531,
    twistTipDeg: -54.33,
    thicknessScale: 1.35
  },
  {
    name: "stator_3",
    type: "stator",
    axialPosition: 0.139309,
    bladeCount: 25,
    airfoil: "naca0012",
    chord: 0.015283,
    twistRootDeg: 31.987,
    twistTipDeg: 20.547,
    thicknessScale: 1.15
  },
  {
    name: "rotor_4",
    type: "rotor",
    axialPosition: 0.162592,
    bladeCount: 26,
    airfoil: "naca2412",
    chord: 0.014826,
    twistRootDeg: -7.531,
    twistTipDeg: -54.33,
    thicknessScale: 1.35
  },
  {
    name: "stator_4",
    type: "stator",
    axialPosition: 0.185418,
    bladeCount: 26,
    airfoil: "naca0012",
    chord: 0.014826,
    twistRootDeg: 31.987,
    twistTipDeg: 20.547,
    thicknessScale: 1.15
  },
  {
    name: "rotor_5",
    type: "rotor",
    axialPosition: 0.208244,
    bladeCount: 27,
    airfoil: "naca2412",
    chord: 0.014391,
    twistRootDeg: -7.531,
    twistTipDeg: -54.33,
    thicknessScale: 1.35
  },
  {
    name: "stator_5",
    type: "stator",
    axialPosition: 0.230635,
    bladeCount: 27,
    airfoil: "naca0012",
    chord: 0.014391,
    twistRootDeg: 31.987,
    twistTipDeg: 20.547,
    thicknessScale: 1.15
  },
  {
    name: "rotor_6",
    type: "rotor",
    axialPosition: 0.253027,
    bladeCount: 28,
    airfoil: "naca2412",
    chord: 0.013977,
    twistRootDeg: -7.531,
    twistTipDeg: -54.33,
    thicknessScale: 1.35
  },
  {
    name: "stator_6",
    type: "stator",
    axialPosition: 0.275004,
    bladeCount: 28,
    airfoil: "naca0012",
    chord: 0.013977,
    twistRootDeg: 31.987,
    twistTipDeg: 20.547,
    thicknessScale: 1.15
  }
];

const createConstantProfile = (value: number): Profile => ({
  type: "constant",
  value,
  points: null,
  from_stage: null,
  scale: 1
});

const createLinearProfile = (rootValue: number, tipValue: number): Profile => ({
  type: "linear",
  points: [
    [0, rootValue],
    [1, tipValue]
  ],
  value: null,
  from_stage: null,
  scale: 1
});

export const createJetengineInspiredConfig = (): FanCFDConfig => ({
  fan: {
    name: "jetengine_inspired_axial_compressor",
    max_diameter_m: 0.164536,
    hub_diameter_m: 0.082268,
    rpm: 15000,
    duct: {
      enabled: true,
      inner_diameter_m: 0.166536,
      wall_thickness_m: 0.004,
      total_length_m: 0.31,
      inlet_clearance_m: 0.02,
      outlet_clearance_m: 0.02
    },
    stages: jetenginePresetStages.map((stage): StageConfig => ({
      name: stage.name,
      type: stage.type,
      axial_position_m: stage.axialPosition,
      blade_count: stage.bladeCount,
      rpm: stage.type === "rotor" ? 15000 : null,
      rotation_direction: stage.type === "rotor" ? "counterclockwise" : null,
      blade: {
        airfoil: stage.airfoil,
        radial_sections: 13,
        chord_profile: createConstantProfile(stage.chord),
        twist_profile_deg: createLinearProfile(stage.twistRootDeg, stage.twistTipDeg),
        thickness_scale: stage.thicknessScale,
        rake_profile: null,
        skew_profile: null
      }
    }))
  },
  cfd: {
    solver: "simpleFoam",
    rotation_model: "MRF",
    turbulence_model: "kOmegaSST",
    inlet: {
      patch_name: "inlet",
      velocity_m_s: 70,
      turbulence_intensity: 0.05,
      hydraulic_diameter_m: 0.084268
    },
    outlet: {
      patch_name: "outlet",
      velocity_m_s: 70,
      turbulence_intensity: 0.05,
      hydraulic_diameter_m: 0.084268
    },
    fluid: {
      nu_m2_s: 1.5e-5,
      rho_kg_m3: 1.204
    },
    mesh: {
      base_cell_size_m: 0.004,
      refinement_levels: 4,
      boundary_layers: 6,
      boundary_layer_expansion: 1.2,
      domain_length_factor: 3,
      n_processors: 8
    },
    run: {
      n_iterations: 1200,
      write_interval: 100,
      convergence_residual: 1e-4,
      parallel: false,
      n_procs: 8,
      purge_write: 1
    }
  },
  objective: {
    mode: "multi_objective",
    maximize: "pressure_rise",
    constraints: {
      min_pressure_rise_pa: 50000,
      min_flow_rate_m3_s: 1
    },
    weights: {
      pressure_rise: 0.65,
      efficiency: 0.35
    }
  }
});
