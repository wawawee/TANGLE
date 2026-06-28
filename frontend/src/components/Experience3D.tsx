import { Float, MeshDistortMaterial, OrbitControls, PerspectiveCamera, Text } from '@react-three/drei';
import { Canvas, useFrame } from '@react-three/fiber';
import { useRef, useState } from 'react';
import * as THREE from 'three';

function IntensityCube({ intensity }: { intensity: number }) {
  const mesh = useRef<THREE.Mesh>(null!);
  const [hovered, setHover] = useState(false);

  useFrame(() => {
    mesh.current.rotation.x += 0.01 * (intensity / 50);
    mesh.current.rotation.y += 0.01 * (intensity / 50);
  });

  return (
    <Float speed={2} rotationIntensity={1} floatIntensity={1}>
      <mesh
        ref={mesh}
        onPointerOver={() => setHover(true)}
        onPointerOut={() => setHover(false)}
        scale={hovered ? 1.1 : 1}
      >
        <boxGeometry args={[3, 3, 3]} />
        <MeshDistortMaterial
          color={hovered ? '#8b5cf6' : '#06b6d4'}
          speed={2}
          distort={0.4}
          radius={1}
          opacity={0.8}
          transparent
        />
        <Text
          position={[0, 0, 1.6]}
          fontSize={0.2}
          color="white"
          anchorX="center"
          anchorY="middle"
        >
          ANLAGSTAVLAN
        </Text>
        <Text
          position={[0, -0.4, 1.6]}
          fontSize={0.1}
          color="rgba(255,255,255,0.6)"
          anchorX="center"
          anchorY="middle"
        >
          STRATEGY ENCAPSULATED
        </Text>
      </mesh>
    </Float>
  );
}

export default function Experience3D({ active, intensity }: { active: boolean, intensity: number }) {
  if (!active) return null;

  return (
    <div className={`scene-3d-container ${active ? 'scene-3d-active' : ''}`}>
      <Canvas>
        <PerspectiveCamera makeDefault position={[0, 0, 8]} />
        <OrbitControls enableZoom={true} />
        <ambientLight intensity={0.5} />
        <pointLight position={[10, 10, 10]} intensity={1} />
        <spotLight position={[-10, 10, 10]} angle={0.15} penumbra={1} />
        <IntensityCube intensity={intensity} />
        <gridHelper args={[20, 20]} position={[0, -4, 0]} />
      </Canvas>

      {/* HUD for 3D Mode */}
      <div className="absolute top-10 left-1/2 -translate-x-1/2 pointer-events-none text-center">
        <h2 className="text-4xl font-black tracking-tighter text-slate-800 opacity-20">3D PROCESSING CORE</h2>
        <p className="text-xs font-mono text-slate-400">Tactical Strategy Solidified</p>
      </div>
    </div>
  );
}
