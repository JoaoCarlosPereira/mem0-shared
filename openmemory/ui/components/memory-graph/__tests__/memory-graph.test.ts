/**
 * Smoke tests para o adapter memory-graph.
 *
 * Verifica que:
 * 1. setGraphData mapeia nodes/links do payload para o formato interno
 * 2. Nenhum arquivo importa o módulo "obsidian"
 */

// --- Mocks no nível do módulo (hoisted pelo Jest) ---

jest.mock("three", () => ({
  Scene: class Scene {
    children = [];
    add() {}
    remove() {}
  },
}), { virtual: true });

const mockInitGraph = jest.fn();
const mockUpdatePositions = jest.fn();
const mockClear = jest.fn();

jest.mock("../graph-renderer", () => ({
  InstancedGraphRenderer: jest.fn().mockImplementation(function (this: any) {
    this.scene = {};
    this.initGraph = mockInitGraph;
    this.updatePositions = mockUpdatePositions;
    this.updateNodeColor = jest.fn();
    this.updateNodeColors = jest.fn();
    this.getNodeIndexAtRay = jest.fn(() => null);
    this.clear = mockClear;
    this.nodeCount = 0;
    this.edges = [];
    this.edgeIndexBuffer = new Int32Array(0);
    this.linePositions = new Float32Array(0);
    this.positionsStride = 4;
  }),
}));

const mockPhysicsInit = jest.fn().mockResolvedValue(undefined);
const mockPhysicsStart = jest.fn();
const mockPhysicsOnTick = jest.fn();
const mockPhysicsDispose = jest.fn();

jest.mock("../physics-bridge", () => ({
  PhysicsBridge: jest.fn().mockImplementation(function (this: any) {
    this.positionsStride = 4;
    this.nodeCount = 0;
    this.init = mockPhysicsInit;
    this.start = mockPhysicsStart;
    this.stop = jest.fn();
    this.onTick = mockPhysicsOnTick;
    this.setParams = jest.fn();
    this.setPositions = jest.fn();
    this.dispose = mockPhysicsDispose;
  }),
}));

jest.mock("../wasm-loader", () => ({
  getWasmArrayBuffer: () => new ArrayBuffer(8),
  createWorkerBlobUrl: () => "blob:mock",
  revokeWorkerBlobUrl: jest.fn(),
}));

// --- Imports (após mocks) ---
import type { MemoryGraphPayload } from "../types";
import { MemoryGraphAdapter } from "../index";

describe("memory-graph adapter", () => {
  let mockScene: any;

  beforeEach(() => {
    jest.clearAllMocks();
    mockScene = { add: jest.fn(), remove: jest.fn(), children: [] };
  });

  describe("setGraphData", () => {
    it("mapeia nodes/links do payload para o formato interno", () => {
      const payload: MemoryGraphPayload = {
        meta: { workspace_id: "ws-1", project_id: "proj-1", node_count: 2, link_count: 1 },
        nodes: [
          { id: "n1", name: "Memoria 1", content: "Conteudo A", color: "#ff0000" },
          { id: "n2", name: "Memoria 2", content: "Conteudo B", color: "#00ff00" },
        ],
        links: [{ source: "n1", target: "n2" }],
      };

      const adapter = new MemoryGraphAdapter(mockScene);
      adapter.setGraphData(payload);

      expect(mockInitGraph).toHaveBeenCalledTimes(1);
      const [nodeData, edges] = mockInitGraph.mock.calls[0];

      // nodes mapeados corretamente
      expect(nodeData).toHaveLength(2);
      expect(nodeData[0].id).toBe("n1");
      expect(nodeData[0].name).toBe("Memoria 1");
      expect(nodeData[0].color).toBe("#ff0000");
      expect(nodeData[1].id).toBe("n2");

      // links mapeados para índices posicionais
      expect(edges).toHaveLength(1);
      expect(edges[0].source).toBe(0);
      expect(edges[0].target).toBe(1);
    });

    it("ignora links com node inexistente", () => {
      const payload: MemoryGraphPayload = {
        meta: {},
        nodes: [{ id: "n1", name: "Só" }],
        links: [
          { source: "n1", target: "n-inexistente" },
          { source: "n-inexistente", target: "n1" },
        ],
      };

      const adapter = new MemoryGraphAdapter(mockScene);
      adapter.setGraphData(payload);

      expect(mockInitGraph).toHaveBeenCalledTimes(1);
      const [, edges] = mockInitGraph.mock.calls[0];
      expect(edges).toHaveLength(0);
    });

    it("handle vazio payload sem erros", () => {
      const payload: MemoryGraphPayload = {
        meta: {},
        nodes: [],
        links: [],
      };

      const adapter = new MemoryGraphAdapter(mockScene);
      expect(() => adapter.setGraphData(payload)).not.toThrow();
    });

    it("marca nós sem arestas como orphan=true", () => {
      const payload: MemoryGraphPayload = {
        meta: {},
        nodes: [
          { id: "a", name: "A" },
          { id: "b", name: "B" },
          { id: "c", name: "C" },
        ],
        links: [{ source: "a", target: "b" }],
      };

      const adapter = new MemoryGraphAdapter(mockScene);
      adapter.setGraphData(payload);

      const [nodeData] = mockInitGraph.mock.calls[0];
      expect(nodeData[0].orphan).toBe(false); // a tem aresta
      expect(nodeData[1].orphan).toBe(false); // b tem aresta
      expect(nodeData[2].orphan).toBe(true);  // c não tem aresta
    });

    it("orphan explícito no payload prevalece sobre detecção automática", () => {
      const payload: MemoryGraphPayload = {
        meta: {},
        nodes: [
          { id: "a", name: "A" },
          { id: "b", name: "B" },
        ],
        links: [{ source: "a", target: "b" }],
      };

      const adapter = new MemoryGraphAdapter(mockScene);
      // Forçar orphan explícito no node "a" (mesmo tendo aresta)
      payload.nodes[0].orphan = true;
      adapter.setGraphData(payload);

      const [nodeData] = mockInitGraph.mock.calls[0];
      expect(nodeData[0].orphan).toBe(true);
      expect(nodeData[1].orphan).toBe(false);
    });

    it("usa cor orange para órfãos e zinc para normais", () => {
      const payload: MemoryGraphPayload = {
        meta: {},
        nodes: [
          { id: "a", name: "A" },
          { id: "b", name: "B" },
        ],
        links: [],
      };

      const adapter = new MemoryGraphAdapter(mockScene);
      adapter.setGraphData(payload);

      const [nodeData] = mockInitGraph.mock.calls[0];
      // Ambos são órfãos (sem arestas) — cor orange padrão
      expect(nodeData[0].orphan).toBe(true);
      expect(nodeData[1].orphan).toBe(true);
      // Cor padrão de órfão é orange-400 (#fb923c)
      expect(nodeData[0].color).toBe(undefined);
    });

    it("aceita links com GraphNode em vez de string", () => {
      const payload: MemoryGraphPayload = {
        meta: {},
        nodes: [
          { id: "a", name: "A" },
          { id: "b", name: "B" },
        ],
        links: [
          {
            source: { id: "a", name: "A" },
            target: { id: "b", name: "B" },
          },
        ],
      };

      const adapter = new MemoryGraphAdapter(mockScene);
      adapter.setGraphData(payload);

      expect(mockInitGraph).toHaveBeenCalledTimes(1);
      const [, edges] = mockInitGraph.mock.calls[0];
      expect(edges).toHaveLength(1);
      expect(edges[0].source).toBe(0);
      expect(edges[0].target).toBe(1);
    });
  });

  describe("sem dependência obsidian", () => {
    const fs = require("fs");
    const path = require("path");

    it.each([
      "index.ts",
      "graph-renderer.ts",
      "physics-bridge.ts",
      "physics-types.ts",
      "types.ts",
      "wasm-loader.ts",
    ])("%s não importa o módulo obsidian", (file) => {
      const content = fs.readFileSync(path.join(__dirname, "..", file), "utf-8");
      expect(content).not.toMatch(/from\s+["']obsidian["']/);
      expect(content).not.toMatch(/require\(\s*["']obsidian["']\s*\)/);
    });

    it("NOTICE contém atribuição MIT do obsidian-3d-graph", () => {
      const notice = fs.readFileSync(path.join(__dirname, "..", "NOTICE"), "utf-8");
      expect(notice).toContain("MIT License");
      expect(notice).toContain("obsidian-3d-graph");
      expect(notice).toContain("Aryan Gupta");
    });
  });
});
