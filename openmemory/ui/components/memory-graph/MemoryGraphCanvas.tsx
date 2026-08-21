"use client";

import { useEffect, useRef, useState } from "react";
import * as THREE from "three";
import { MemoryGraphAdapter, type MemoryGraphPayload } from ".";

interface MemoryGraphCanvasProps {
  payload: MemoryGraphPayload | null;
  loading: boolean;
  error: string | null;
  onNodeClick: (nodeId: string) => void;
}

/**
 * Canvas 3D para visualização do grafo de memórias.
 * Carrega THREE e o MemoryGraphAdapter dinamicamente para evitar SSR crash.
 */
export function MemoryGraphCanvas({
  payload,
  loading,
  error,
  onNodeClick,
}: MemoryGraphCanvasProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const adapterRef = useRef<MemoryGraphAdapter | null>(null);
  const raycasterRef = useRef(new THREE.Raycaster());
  const mouseRef = useRef(new THREE.Vector2());
  // Mantém o payload atual acessível ao handler de clique (registrado no mount).
  const payloadRef = useRef<MemoryGraphPayload | null>(payload);
  const [canvasReady, setCanvasReady] = useState(false);
  const [canvasError, setCanvasError] = useState<string | null>(null);

  useEffect(() => {
    payloadRef.current = payload;
  }, [payload]);

  // Initialize Three.js scene on mount (client-only)
  useEffect(() => {
    if (!containerRef.current) return;

    let scene: THREE.Scene | null = null;
    let camera: THREE.PerspectiveCamera | null = null;
    let renderer: THREE.WebGLRenderer | null = null;
    let animationId: number | null = null;
    let adapter: MemoryGraphAdapter | null = null;

    const initScene = async () => {
      try {
        // Dynamically import OrbitControls (client-only)
        const { OrbitControls } = await import("three/addons/controls/OrbitControls.js");

        scene = new THREE.Scene();
        scene.background = new THREE.Color("#020617"); // bg-deep zinc/dark OpenMemory

        camera = new THREE.PerspectiveCamera(
          75,
          containerRef.current!.clientWidth / containerRef.current!.clientHeight,
          0.1,
          1000
        );
        camera.position.z = 100;

        renderer = new THREE.WebGLRenderer({ antialias: true });
        renderer.setSize(
          containerRef.current!.clientWidth,
          containerRef.current!.clientHeight
        );
        renderer.setPixelRatio(window.devicePixelRatio);
        containerRef.current!.appendChild(renderer.domElement);

        const controls = new OrbitControls(camera, renderer.domElement);
        controls.enableDamping = true;
        controls.dampingFactor = 0.05;

        // Add ambient light
        const ambientLight = new THREE.AmbientLight(0xffffff, 0.6);
        scene.add(ambientLight);

        setCanvasReady(true);
        setCanvasError(null);

        adapter = new MemoryGraphAdapter(scene);
        adapterRef.current = adapter;

        // Animation loop
        const animate = () => {
          animationId = requestAnimationFrame(animate);
          controls.update();
          if (renderer && scene && camera) {
            renderer.render(scene, camera);
          }
        };
        animate();

        // Resize handler
        const handleResize = () => {
          if (!containerRef.current || !camera || !renderer) return;
          const w = containerRef.current.clientWidth;
          const h = containerRef.current.clientHeight;
          camera.aspect = w / h;
          camera.updateProjectionMatrix();
          renderer.setSize(w, h);
        };
        window.addEventListener("resize", handleResize);

        // Click handler for node selection
        const handleClick = (event: MouseEvent) => {
          if (!scene || !camera) return;
          const rect = containerRef.current!.getBoundingClientRect();
          mouseRef.current.x =
            ((event.clientX - rect.left) / rect.width) * 2 - 1;
          mouseRef.current.y =
            -((event.clientY - rect.top) / rect.height) * 2 + 1;

          raycasterRef.current.setFromCamera(mouseRef.current, camera);

          // Get node index at ray
          const nodeIndex = (adapter as any)?.renderer?.getNodeIndexAtRay
            ? (adapter as any).renderer.getNodeIndexAtRay(raycasterRef.current)
            : null;

          if (nodeIndex !== null && payloadRef.current) {
            const node = payloadRef.current.nodes[nodeIndex];
            if (node && node.id) {
              onNodeClick(node.id);
            }
          }
        };
        renderer.domElement.addEventListener("click", handleClick);

        // Store cleanup
        (containerRef.current as any).__mem0Cleanup = () => {
          window.removeEventListener("resize", handleResize);
          renderer.domElement.removeEventListener("click", handleClick);
        };
      } catch (err: any) {
        setCanvasError(err.message || "Erro ao inicializar canvas 3D");
      }
    };

    initScene();

    return () => {
      (containerRef.current as any)?.__mem0Cleanup?.();
      if (animationId !== null) cancelAnimationFrame(animationId);
      if (renderer) {
        renderer.dispose();
        if (renderer.domElement.parentNode) {
          renderer.domElement.parentNode.removeChild(renderer.domElement);
        }
      }
      adapter?.dispose();
      adapterRef.current = null;
    };
  }, []); // Only run once on mount

  // Update graph data when payload changes
  useEffect(() => {
    if (!adapterRef.current || !payload || !canvasReady) return;

    try {
      adapterRef.current.setGraphData(payload);
    } catch (err: any) {
      console.error("[MemoryGraph] Error updating graph data:", err);
    }
  }, [payload, canvasReady]);

  if (canvasError) {
    return (
      <div className="flex flex-col items-center justify-center py-12 text-center">
        <p className="text-red-400 mb-4">{canvasError}</p>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center py-12 text-center">
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-slate-600 border-t-indigo-500" />
        <p className="mt-4 text-sm text-slate-400">Carregando grafo...</p>
      </div>
    );
  }

  if (!payload || payload.nodes.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-12 text-center">
        <p className="text-slate-400">
          Nenhum dado de grafo disponível. Adicione memórias conectadas para
          visualizar o grafo.
        </p>
      </div>
    );
  }

  return (
    <div className="relative h-[600px] w-full rounded-lg border border-slate-800 bg-slate-900/50">
      <div ref={containerRef} className="h-full w-full" />
      {/* Hint de similaridade (ADR-002) */}
      <div className="absolute bottom-3 left-3 rounded bg-slate-900/80 px-3 py-1 text-xs text-slate-400">
        As conexões representam similaridade semântica (não são links explícitos)
      </div>
      {/* Contador */}
      <div className="absolute bottom-3 right-3 rounded bg-slate-900/80 px-3 py-1 text-xs text-slate-400">
        {payload.nodes.length} nós · {payload.links.length} arestas · Clique em
        um nó para ver detalhes
      </div>
    </div>
  );
}

export default MemoryGraphCanvas;
