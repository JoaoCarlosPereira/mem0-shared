/**
 * Tipos do grafo de memórias — port do obsidian-3d-graph (MIT).
 * Sem dependências Obsidian; tipagem alinhada ao TechSpec.
 */

/** Nó no grafo 3D de memórias. */
export interface GraphNode {
  id: string;
  name: string;
  content?: string;
  tags?: string[];
  group?: string;
  color?: string;
  x?: number;
  y?: number;
  z?: number;
  /** Indica que o nó não tem arestas acima do limiar. */
  orphan?: boolean;
  created_at?: string;
}

export interface GraphLink {
  source: string | GraphNode;
  target: string | GraphNode;
}

export interface MemoryGraphMeta {
  workspace_id?: string;
  project_id?: string;
  node_count?: number;
  link_count?: number;
  timestamp?: string;
}

export interface MemoryGraphPayload {
  meta: MemoryGraphMeta;
  nodes: GraphNode[];
  links: GraphLink[];
}

export interface SimulationParams {
  repulsion: number;
  attraction: number;
  link_distance: number;
  gravity: number;
  damping: number;
  max_velocity: number;
  dt: number;
  theta: number;
  alpha_min?: number;
}

export const DEFAULT_SIMULATION_PARAMS: SimulationParams = {
  repulsion: 400.0,
  attraction: 0.02,
  link_distance: 30.0,
  gravity: 0.05,
  damping: 0.85,
  max_velocity: 40.0,
  dt: 0.3,
  theta: 0.8,
  alpha_min: 0.001,
};

export interface NodeData {
  id: string;
  name: string;
  val?: number;
  color?: string;
  orphan?: boolean;
}

export interface EdgeData {
  source: number;
  target: number;
  color?: string;
}
