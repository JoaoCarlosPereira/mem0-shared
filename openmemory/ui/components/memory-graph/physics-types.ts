import type { SimulationParams } from "./types";

export type WorkerIncomingMessage =
  | {
      type: "INIT";
      wasmBytes: ArrayBuffer;
      nodeCount: number;
      edgesFlat: Uint32Array;
      params?: Partial<SimulationParams>;
      initialPositions?: Float32Array;
    }
  | { type: "STEP"; count?: number }
  | { type: "SET_PARAMS"; params: Partial<SimulationParams> }
  | { type: "SET_POSITIONS"; positions: Float32Array }
  | { type: "RETURN_BUFFER"; buffer: ArrayBuffer };

export type WorkerOutgoingMessage =
  | {
      type: "READY";
      sharedBuffer?: SharedArrayBuffer;
      positionsStride: 4;
      nodeCount: number;
    }
  | {
      type: "TICK";
      positions?: Float32Array;
      frameTimeMs: number;
      usedShared: boolean;
    }
  | { type: "ERROR"; error: string };
