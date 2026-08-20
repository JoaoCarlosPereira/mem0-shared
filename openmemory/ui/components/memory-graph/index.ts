/**
 * Adapter principal do memory-graph.
 *
 * Este módulo exporta apenas a função `setGraphData`, que recebe um
 * MemoryGraphPayload da API e o converte nas estruturas internas do
 * InstancedGraphRenderer e do PhysicsBridge.
 *
 * Nenhum módulo `obsidian` é importado aqui.
 *
 * @module memory-graph
 */

import * as THREE from "three";
import { InstancedGraphRenderer } from "./graph-renderer";
import { PhysicsBridge, type TickCallback } from "./physics-bridge";
import { getWasmArrayBuffer } from "./wasm-loader";
import type {
  EdgeData,
  GraphNode,
  GraphLink,
  MemoryGraphPayload,
  MemoryGraphMeta,
  SimulationParams,
} from "./types";

/** Ponto de entrada principal: aceita payloads da API e alimenta renderer + física. */
export class MemoryGraphAdapter {
  private renderer: InstancedGraphRenderer | null = null;
  private physics: PhysicsBridge | null = null;
  private scene: THREE.Scene;
  private nodes: GraphNode[] = [];
  private edges: EdgeData[] = [];
  private tickCallback: TickCallback | null = null;
  private nodeIndexMap: Map<string, number> = new Map();
  private initSeq = 0;

  constructor(scene: THREE.Scene) {
    this.scene = scene;
  }

  /**
   * Recebe um payload da API e atualiza renderer + física.
   *
   * @example
   *   const adapter = new MemoryGraphAdapter(scene);
   *   adapter.setGraphData(payload);
   */
  setGraphData(payload: MemoryGraphPayload): void {
    const { nodes, links } = payload;
    this.nodes = nodes;
    this.nodeIndexMap.clear();
    nodes.forEach((n, i) => this.nodeIndexMap.set(n.id, i));

    // Build edge list (indexed by position)
    this.edges = [];
    for (const link of links) {
      const src = typeof link.source === "string"
        ? this.nodeIndexMap.get(link.source)
        : this.nodeIndexMap.get(link.source.id);
      const tgt = typeof link.target === "string"
        ? this.nodeIndexMap.get(link.target)
        : this.nodeIndexMap.get(link.target.id);
      if (src !== undefined && tgt !== undefined) {
        this.edges.push({ source: src, target: tgt });
      }
    }

    // Marcar nós órfãos (não aparecem em nenhuma aresta)
    const nodeIdsInEdges = new Set<string>();
    for (const link of links) {
      const src = typeof link.source === "string" ? link.source : link.source.id;
      const tgt = typeof link.target === "string" ? link.target : link.target.id;
      nodeIdsInEdges.add(src);
      nodeIdsInEdges.add(tgt);
    }

    // Initialize renderer
    const nodeData = this.nodes.map((n) => ({
      id: n.id,
      name: n.name,
      val: 1.5,
      color: n.color,
      orphan: n.orphan ?? !nodeIdsInEdges.has(n.id),
    }));

    if (!this.renderer) {
      this.renderer = new InstancedGraphRenderer(this.scene);
    }
    this.renderer.initGraph(nodeData, this.edges, 1.5);

    // Initialize physics (WASM) whenever the payload has a graph.
    if (this.physics) {
      this.physics.dispose();
      this.physics = null;
    }
    this.initSeq++;
    if (nodes.length > 0 && this.edges.length > 0) {
      const seq = ++this.initSeq;
      const phys = new PhysicsBridge();
      this.physics = phys;
      const wasmBuf = getWasmArrayBuffer();
      phys
        .init(
          wasmBuf,
          nodes.length,
          new Uint32Array(this.edges.flatMap((e) => [e.source, e.target])),
        )
        .then(() => {
          // Descarta callback de um init obsoleto (setGraphData repetido).
          if (seq !== this.initSeq) return;
          phys.onTick((positions, frameTimeMs) => {
            this.updatePositions(positions);
            this.tickCallback?.(positions, frameTimeMs);
          });
          phys.start();
        })
        .catch((err) => {
          console.error("[MemoryGraph] WASM physics failed:", err);
        });
    }
  }

  /** Register a callback to receive physics tick positions. */
  onTick(cb: TickCallback): void {
    this.tickCallback = cb;
  }

  /** Update positions from physics. */
  updatePositions(positions: Float32Array): void {
    this.renderer?.updatePositions(positions);
  }

  dispose(): void {
    this.renderer?.clear();
    this.physics?.dispose();
    this.renderer = null;
    this.physics = null;
  }
}

/** Função simplificada para quem só quer setar um grafo de uma vez. */
export function setGraphData(
  scene: THREE.Scene,
  payload: MemoryGraphPayload,
  tickCallback?: TickCallback,
): MemoryGraphAdapter {
  const adapter = new MemoryGraphAdapter(scene);
  if (tickCallback) adapter.onTick(tickCallback);
  adapter.setGraphData(payload);
  return adapter;
}

export {
  InstancedGraphRenderer,
  PhysicsBridge,
  type TickCallback,
  type GraphNode,
  type GraphLink,
  type MemoryGraphPayload,
  type MemoryGraphMeta,
  type SimulationParams,
  type EdgeData,
};
