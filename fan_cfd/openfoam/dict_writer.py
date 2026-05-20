"""
fan_cfd.openfoam.dict_writer
=============================
Functions that generate OpenFOAM dictionary file content as strings.

All functions return a multi-line string suitable for direct file writing.
Token substitution uses Python f-strings; placeholder-style tokens in
the templates (``{{...}}``) are replaced by the case builder.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from fan_cfd.utils.names import openfoam_identifier

if TYPE_CHECKING:
    from fan_cfd.config import CFDConfig, FanConfig, FluidConfig


# ---------------------------------------------------------------------------
# Header helper
# ---------------------------------------------------------------------------


def write_foam_header(class_name: str, object_name: str, location: str = "") -> str:
    """Return a standard OpenFOAM FoamFile header block."""
    loc_line = f'\n    location    "{location}";' if location else ""
    return f"""\
/*--------------------------------*- C++ -*----------------------------------*\\
| =========                 |                                                 |
| \\\\      /  F ield         | OpenFOAM: The Open Source CFD Toolbox           |
|  \\\\    /   O peration     | Version:  v2206                                 |
|   \\\\  /    A nd           | Web:      www.OpenFOAM.com                      |
|    \\\\/     M anipulation  |                                                 |
\\*---------------------------------------------------------------------------*/
FoamFile
{{
    version     2.0;
    format      ascii;
    class       {class_name};{loc_line}
    object      {object_name};
}}
// * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * //
"""


# ---------------------------------------------------------------------------
# blockMeshDict
# ---------------------------------------------------------------------------


def write_block_mesh_dict(config: "CFDConfig", fan: "FanConfig") -> str:
    """
    Write a simple rectangular blockMeshDict bounding box.

    The domain is a cylinder-like box large enough to contain the fan.
    SnappyHexMesh will carve the actual geometry.
    """
    r = fan.tip_radius_m
    domain_r = r * config.mesh.domain_length_factor
    domain_z_min = -domain_r
    domain_z_max = domain_r * 2.5  # longer downstream
    cs = config.mesh.base_cell_size_m

    # Number of cells along each dimension
    nx = max(4, int(domain_r * 2 / cs))
    ny = nx
    nz = max(4, int((domain_z_max - domain_z_min) / cs))

    return write_foam_header("dictionary", "blockMeshDict", "system") + f"""
scale   1;

vertices
(
    ({-domain_r:.6f} {-domain_r:.6f} {domain_z_min:.6f})   // 0
    ( {domain_r:.6f} {-domain_r:.6f} {domain_z_min:.6f})   // 1
    ( {domain_r:.6f}  {domain_r:.6f} {domain_z_min:.6f})   // 2
    ({-domain_r:.6f}  {domain_r:.6f} {domain_z_min:.6f})   // 3
    ({-domain_r:.6f} {-domain_r:.6f} {domain_z_max:.6f})   // 4
    ( {domain_r:.6f} {-domain_r:.6f} {domain_z_max:.6f})   // 5
    ( {domain_r:.6f}  {domain_r:.6f} {domain_z_max:.6f})   // 6
    ({-domain_r:.6f}  {domain_r:.6f} {domain_z_max:.6f})   // 7
);

blocks
(
    hex (0 1 2 3 4 5 6 7) ({nx} {ny} {nz}) simpleGrading (1 1 1)
);

edges
(
);

boundary
(
    inlet
    {{
        type patch;
        faces
        (
            (0 3 2 1)
        );
    }}
    outlet
    {{
        type patch;
        faces
        (
            (4 5 6 7)
        );
    }}
    sides
    {{
        type patch;
        faces
        (
            (0 1 5 4)
            (1 2 6 5)
            (2 3 7 6)
            (3 0 4 7)
        );
    }}
);

// ************************************************************************* //
"""


# ---------------------------------------------------------------------------
# snappyHexMeshDict
# ---------------------------------------------------------------------------


def write_snappy_hex_mesh_dict(
    config: "CFDConfig",
    fan: "FanConfig",
    stl_files: list[str],
) -> str:
    """
    Write snappyHexMeshDict for castellated mesh + snapping + layer addition.
    """
    cs = config.mesh.base_cell_size_m
    ref_lvl = config.mesh.refinement_levels
    n_layers = config.mesh.boundary_layers

    # Build geometry section from STL files (skip combined meshes)
    skip_keys = {"full_assembly", "all_rotors", "all_stators"}
    geom_entries: list[str] = []
    refinement_entries: list[str] = []

    for stl_name in stl_files:
        base = stl_name.replace(".stl", "")
        if base in skip_keys:
            continue
        geom_entries.append(
            f"""    {base}
    {{
        type triSurfaceMesh;
        file "{base}.stl";
        name {base};
    }}"""
        )
        refinement_entries.append(
            f"""    {base}
    {{
        level ({ref_lvl} {ref_lvl + 1});
        patchInfo
        {{
            type wall;
        }}
    }}"""
        )

    geom_block = "\n".join(geom_entries)
    refine_block = "\n    ".join(refinement_entries)

    # Point inside the flow domain (upstream of blade)
    inside_x = 0.0
    inside_y = (fan.hub_radius_m + fan.tip_radius_m) / 2.0
    inside_z = -cs * 3
    layer_patch_pattern = _wall_patch_pattern(fan)

    add_layers = "true" if n_layers > 0 else "false"

    return write_foam_header("dictionary", "snappyHexMeshDict", "system") + f"""
castellatedMesh true;
snap            true;
addLayers       {add_layers};

geometry
{{
{geom_block}
}}

castellatedMeshControls
{{
    maxLocalCells       1000000;
    maxGlobalCells      5000000;
    minRefinementCells  10;
    maxLoadUnbalance    0.10;
    nCellsBetweenLevels 2;

    features
    (
    );

    refinementSurfaces
    {{
    {refine_block}
    }}

    resolveFeatureAngle 30;

    refinementRegions
    {{
    }}

    locationInMesh ({inside_x:.6f} {inside_y:.6f} {inside_z:.6f});

    allowFreeStandingZoneFaces true;
}}

snapControls
{{
    nSmoothPatch        3;
    tolerance           2.0;
    nSolveIter          30;
    nRelaxIter          5;
    nFeatureSnapIter    10;
    implicitFeatureSnap false;
    explicitFeatureSnap false;
    multiRegionFeatureSnap false;
}}

addLayersControls
{{
    relativeSizes       true;
    layers
    {{
        "{layer_patch_pattern}"
        {{
            nSurfaceLayers {n_layers};
        }}
    }}
    expansionRatio          {config.mesh.boundary_layer_expansion:.2f};
    finalLayerThickness     0.3;
    minThickness            0.1;
    nGrow                   0;
    featureAngle            60;
    slipFeatureAngle        30;
    nRelaxIter              3;
    nSmoothSurfaceNormals   1;
    nSmoothNormals          3;
    nSmoothThickness        10;
    maxFaceThicknessRatio   0.5;
    maxThicknessToMedialRatio 0.3;
    minMedialAxisAngle      90;
    nBufferCellsNoExtrude   0;
    nLayerIter              50;
}}

meshQualityControls
{{
    maxNonOrtho         65;
    maxBoundarySkewness 20;
    maxInternalSkewness 4;
    maxConcave          80;
    minVol              1e-13;
    minTetQuality       1e-15;
    minArea             -1;
    minTwist            0.02;
    minDeterminant      0.001;
    minFaceWeight       0.05;
    minVolRatio         0.01;
    minTriangleTwist    -1;
    nSmoothScale        4;
    errorReduction      0.75;
}}

writeFlags
(
    scalarLevels
);

mergeTolerance 1e-6;

// ************************************************************************* //
"""


# ---------------------------------------------------------------------------
# controlDict
# ---------------------------------------------------------------------------


def write_control_dict(config: "CFDConfig") -> str:
    run_cfg = config.run
    return write_foam_header("dictionary", "controlDict", "system") + f"""
application     {config.solver};

startFrom       startTime;

startTime       0;

stopAt          endTime;

endTime         {run_cfg.n_iterations};

deltaT          1;

writeControl    timeStep;

writeInterval   {run_cfg.write_interval};

purgeWrite      {run_cfg.purge_write};

writeFormat     ascii;

writePrecision  8;

writeCompression off;

timeFormat      general;

timePrecision   6;

runTimeModifiable true;

functions
{{
    #include "functionObjects"
}}

// ************************************************************************* //
"""


# ---------------------------------------------------------------------------
# fvSchemes
# ---------------------------------------------------------------------------


def write_fv_schemes() -> str:
    return write_foam_header("dictionary", "fvSchemes", "system") + """
ddtSchemes
{
    default         steadyState;
}

gradSchemes
{
    default         Gauss linear;
    grad(U)         cellLimited Gauss linear 1;
}

divSchemes
{
    default                     none;
    div(phi,U)                  bounded Gauss linearUpwindV grad(U);
    div(phi,k)                  bounded Gauss upwind;
    div(phi,omega)              bounded Gauss upwind;
    div((nuEff*dev(T(grad(U)))) ) Gauss linear;
    div(phi,nut)                bounded Gauss upwind;
}

laplacianSchemes
{
    default         Gauss linear corrected;
}

interpolationSchemes
{
    default         linear;
}

snGradSchemes
{
    default         corrected;
}

fluxRequired
{
    default         no;
    p               ;
}

wallDist
{
    method          meshWave;
}

// ************************************************************************* //
"""


# ---------------------------------------------------------------------------
# fvSolution
# ---------------------------------------------------------------------------


def write_fv_solution() -> str:
    return write_foam_header("dictionary", "fvSolution", "system") + """
solvers
{
    p
    {
        solver          GAMG;
        smoother        GaussSeidel;
        tolerance       1e-6;
        relTol          0.01;
    }

    "(U|k|omega|nut)"
    {
        solver          smoothSolver;
        smoother        symGaussSeidel;
        tolerance       1e-6;
        relTol          0.01;
    }
}

SIMPLE
{
    nNonOrthogonalCorrectors 2;
    pRefCell        0;
    pRefValue       0;

    residualControl
    {
        p               1e-4;
        U               1e-4;
        "(k|omega)"     1e-4;
    }
}

relaxationFactors
{
    fields
    {
        p               0.3;
    }
    equations
    {
        U               0.7;
        k               0.7;
        omega           0.7;
        nut             0.7;
    }
}

// ************************************************************************* //
"""


# ---------------------------------------------------------------------------
# Transport properties
# ---------------------------------------------------------------------------


def write_transport_properties(fluid: "FluidConfig") -> str:
    return write_foam_header("dictionary", "transportProperties", "constant") + f"""
transportModel  Newtonian;

nu              nu [ 0 2 -1 0 0 0 0 ] {fluid.nu_m2_s:.6e};

// ************************************************************************* //
"""


# ---------------------------------------------------------------------------
# Turbulence properties
# ---------------------------------------------------------------------------


def write_turbulence_properties(model: str = "kOmegaSST") -> str:
    return write_foam_header("dictionary", "turbulenceProperties", "constant") + f"""
simulationType  RAS;

RAS
{{
    RASModel        {model};
    turbulence      on;
    printCoeffs     on;
}}

// ************************************************************************* //
"""


# ---------------------------------------------------------------------------
# Boundary conditions
# ---------------------------------------------------------------------------


def _compute_k(u: float, intensity: float) -> float:
    """Turbulent kinetic energy from velocity and intensity."""
    return 1.5 * (u * intensity) ** 2


def _compute_omega(k: float, nu: float, hydraulic_diameter: float) -> float:
    """Specific dissipation from k, viscosity, hydraulic diameter."""
    Cmu = 0.09
    mixing_length = 0.07 * hydraulic_diameter
    eps = Cmu ** 0.75 * k ** 1.5 / mixing_length
    return eps / (Cmu * k) if k > 0 else 1.0


def _wall_patch_pattern(fan: "FanConfig | None" = None) -> str:
    patches = ["hub", "duct", "hub_wall", "duct_wall", "rotor.*", "stator.*"]
    if fan is not None:
        patches.extend(openfoam_identifier(stage.name, "stage") for stage in fan.stages)

    unique_patches = list(dict.fromkeys(patches))
    return "(" + "|".join(unique_patches) + ")"


def write_boundary_condition_U(config: "CFDConfig", fan: "FanConfig | None" = None) -> str:
    u_in = config.inlet.velocity_m_s
    wall_patch_pattern = _wall_patch_pattern(fan)
    return write_foam_header("volVectorField", "U") + f"""
dimensions      [0 1 -1 0 0 0 0];

internalField   uniform (0 0 {u_in:.4f});

boundaryField
{{
    inlet
    {{
        type            fixedValue;
        value           uniform (0 0 {u_in:.4f});
    }}

    outlet
    {{
        type            zeroGradient;
    }}

    sides
    {{
        type            slip;
    }}

    "{wall_patch_pattern}"
    {{
        type            noSlip;
    }}
}}

// ************************************************************************* //
"""


def write_boundary_condition_p(config: "CFDConfig", fan: "FanConfig | None" = None) -> str:
    wall_patch_pattern = _wall_patch_pattern(fan)
    return write_foam_header("volScalarField", "p") + f"""
dimensions      [0 2 -2 0 0 0 0];

internalField   uniform 0;

boundaryField
{{
    inlet
    {{
        type            zeroGradient;
    }}

    outlet
    {{
        type            fixedValue;
        value           uniform 0;
    }}

    sides
    {{
        type            slip;
    }}

    "{wall_patch_pattern}"
    {{
        type            zeroGradient;
    }}
}}

// ************************************************************************* //
"""


def write_boundary_condition_k(config: "CFDConfig", fan: "FanConfig | None" = None) -> str:
    u = config.inlet.velocity_m_s
    intensity = config.inlet.turbulence_intensity
    k_val = _compute_k(u, intensity)
    wall_patch_pattern = _wall_patch_pattern(fan)
    return write_foam_header("volScalarField", "k") + f"""
dimensions      [0 2 -2 0 0 0 0];

internalField   uniform {k_val:.6e};

boundaryField
{{
    inlet
    {{
        type            turbulentIntensityKineticEnergyInlet;
        intensity       {intensity:.4f};
        value           uniform {k_val:.6e};
    }}

    outlet
    {{
        type            zeroGradient;
    }}

    sides
    {{
        type            slip;
    }}

    "{wall_patch_pattern}"
    {{
        type            kqRWallFunction;
        value           uniform {k_val:.6e};
    }}
}}

// ************************************************************************* //
"""


def write_boundary_condition_omega(config: "CFDConfig", fan: "FanConfig | None" = None) -> str:
    u = config.inlet.velocity_m_s
    intensity = config.inlet.turbulence_intensity
    hydraulic_diameter = config.inlet.hydraulic_diameter_m
    nu = config.fluid.nu_m2_s
    k_val = _compute_k(u, intensity)
    omega_val = _compute_omega(k_val, nu, hydraulic_diameter)
    wall_patch_pattern = _wall_patch_pattern(fan)
    return write_foam_header("volScalarField", "omega") + f"""
dimensions      [0 0 -1 0 0 0 0];

internalField   uniform {omega_val:.6e};

boundaryField
{{
    inlet
    {{
        type            turbulentMixingLengthFrequencyInlet;
        mixingLength    {0.07 * hydraulic_diameter:.6e};
        value           uniform {omega_val:.6e};
    }}

    outlet
    {{
        type            zeroGradient;
    }}

    sides
    {{
        type            slip;
    }}

    "{wall_patch_pattern}"
    {{
        type            omegaWallFunction;
        value           uniform {omega_val:.6e};
    }}
}}

// ************************************************************************* //
"""


def write_boundary_condition_nut(config: "CFDConfig", fan: "FanConfig | None" = None) -> str:
    wall_patch_pattern = _wall_patch_pattern(fan)
    return write_foam_header("volScalarField", "nut") + f"""
dimensions      [0 2 -1 0 0 0 0];

internalField   uniform 0;

boundaryField
{{
    inlet
    {{
        type            calculated;
        value           uniform 0;
    }}

    outlet
    {{
        type            calculated;
        value           uniform 0;
    }}

    sides
    {{
        type            calculated;
        value           uniform 0;
    }}

    "{wall_patch_pattern}"
    {{
        type            nutkWallFunction;
        value           uniform 0;
    }}
}}

// ************************************************************************* //
"""


# ---------------------------------------------------------------------------
# decomposeParDict
# ---------------------------------------------------------------------------


def write_decompose_par_dict(n_procs: int) -> str:
    return write_foam_header("dictionary", "decomposeParDict", "system") + f"""
numberOfSubdomains  {n_procs};

method          scotch;

// ************************************************************************* //
"""


# ---------------------------------------------------------------------------
# Function objects (postProcessing)
# ---------------------------------------------------------------------------


def write_function_objects(fan: "FanConfig") -> str:
    """
    Write function objects for force/torque extraction on each stage,
    plus pressure rise monitoring between inlet and outlet.
    """
    rotor_stages = fan.rotor_stages
    stator_stages = fan.stator_stages

    force_blocks: list[str] = []
    for stage in rotor_stages + stator_stages:
        patch_name = openfoam_identifier(stage.name, "stage")
        force_blocks.append(
            f"""
    forces_{patch_name}
    {{
        type            forces;
        libs            ("libforces.so");
        patches         ({patch_name});
        rho             rhoInf;
        rhoInf          1.225;
        CofR            (0 0 {stage.axial_position_m:.6f});
        writeControl    timeStep;
        writeInterval   1;
    }}"""
        )

    force_block_str = "\n".join(force_blocks)

    return f"""\
/*--------------------------------*- C++ -*----------------------------------*\\
| =========                 |                                                 |
| \\\\      /  F ield         | OpenFOAM: The Open Source CFD Toolbox           |
|  \\\\    /   O peration     |                                                 |
|   \\\\  /    A nd           |                                                 |
|    \\\\/     M anipulation  |                                                 |
\\*---------------------------------------------------------------------------*/
// Function objects included from controlDict
{force_block_str}

    pressureRise
    {{
        type            surfaceFieldValue;
        libs            ("libfieldFunctionObjects.so");
        fields          (p);
        operation       areaAverage;
        patch           outlet;
        writeFields     no;
        writeControl    timeStep;
        writeInterval   10;
    }}

    pressureInlet
    {{
        type            surfaceFieldValue;
        libs            ("libfieldFunctionObjects.so");
        fields          (p);
        operation       areaAverage;
        patch           inlet;
        writeFields     no;
        writeControl    timeStep;
        writeInterval   10;
    }}

    flowRate
    {{
        type            surfaceFieldValue;
        libs            ("libfieldFunctionObjects.so");
        fields          (phi);
        operation       sum;
        patch           inlet;
        writeFields     no;
        writeControl    timeStep;
        writeInterval   10;
    }}

// ************************************************************************* //
"""
