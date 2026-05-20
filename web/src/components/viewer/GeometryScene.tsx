import { Bounds, OrbitControls, PerspectiveCamera } from "@react-three/drei";
import { Canvas, useLoader } from "@react-three/fiber";
import { Suspense, useMemo } from "react";
import { MeshStandardMaterial } from "three";
import { STLLoader } from "three-stdlib";
import type { StlFileItem } from "../../types/api";

interface GeometrySceneProps {
  files: StlFileItem[];
  visible: Set<string>;
  mode: "solid" | "wireframe" | "xray";
  resetKey: number;
}

export default function GeometryScene({ files, visible, mode, resetKey }: GeometrySceneProps) {
  const activeFiles = files.filter((file) => visible.has(file.name));

  return (
    <div className="viewer-canvas">
      <Canvas key={resetKey} shadows dpr={[1, 2]}>
        <color attach="background" args={["#f8fafc"]} />
        <PerspectiveCamera makeDefault position={[0.22, -0.28, 0.18]} fov={45} />
        <OrbitControls makeDefault enableDamping />
        <ambientLight intensity={0.55} />
        <directionalLight position={[2, -3, 4]} intensity={1.8} castShadow />
        <Suspense fallback={null}>
          <Bounds fit clip observe margin={1.35}>
            <group rotation={[Math.PI / 2, 0, 0]}>
              {activeFiles.map((file, index) => (
                <StlMesh key={file.name} file={file} index={index} mode={mode} />
              ))}
              <AxialReferenceArrow />
            </group>
          </Bounds>
        </Suspense>
      </Canvas>
    </div>
  );
}

function StlMesh({
  file,
  index,
  mode
}: {
  file: StlFileItem;
  index: number;
  mode: "solid" | "wireframe" | "xray";
}) {
  const geometry = useLoader(STLLoader, file.url);
  const material = useMemo(() => {
    const color = colorForFile(file.name, index);
    return new MeshStandardMaterial({
      color,
      roughness: 0.42,
      metalness: 0.08,
      wireframe: mode === "wireframe",
      transparent: mode === "xray",
      opacity: mode === "xray" ? 0.36 : 1
    });
  }, [file.name, index, mode]);

  const preparedGeometry = useMemo(() => {
    const clone = geometry.clone();
    clone.computeVertexNormals();
    return clone;
  }, [geometry]);

  return <mesh geometry={preparedGeometry} material={material} castShadow receiveShadow />;
}

function AxialReferenceArrow() {
  return (
    <group position={[0, 0, -0.08]}>
      <mesh position={[0, 0, 0.08]}>
        <cylinderGeometry args={[0.002, 0.002, 0.14, 16]} />
        <meshStandardMaterial color="#0f8f8a" />
      </mesh>
      <mesh position={[0, 0, 0.16]}>
        <coneGeometry args={[0.008, 0.024, 20]} />
        <meshStandardMaterial color="#0f8f8a" />
      </mesh>
    </group>
  );
}

function colorForFile(name: string, index: number) {
  const lower = name.toLowerCase();
  if (lower.includes("stator")) {
    return "#d97706";
  }
  if (lower.includes("hub")) {
    return "#64748b";
  }
  if (lower.includes("duct")) {
    return "#0f8f8a";
  }
  if (lower.includes("rotor") || lower.includes("blade")) {
    return "#2563eb";
  }
  return fallbackColors[index % fallbackColors.length];
}

const fallbackColors = ["#2563eb", "#d97706", "#0f8f8a", "#7c3aed", "#dc2626"];
