import queuesReducer, {
  setWriteQueue,
  setGovernanceQueue,
  setWriteQueueFilter,
  selectFailedCount,
} from "@/store/queuesSlice";
import type {
  PaginatedWriteQueue,
  PaginatedGovernanceQueue,
} from "@/types/admin";
import type { RootState } from "@/store/store";

const writeQueue: PaginatedWriteQueue = {
  items: [],
  total: 0,
  page: 1,
  pages: 0,
  failed_count: 3,
};

const govQueue: PaginatedGovernanceQueue = {
  items: [],
  total: 0,
  page: 1,
  pages: 0,
  failed_count: 2,
};

function rootWith(queues: Partial<ReturnType<typeof queuesReducer>>): RootState {
  return {
    queues: { ...queuesReducer(undefined, { type: "@@INIT" }), ...queues },
  } as unknown as RootState;
}

describe("queuesSlice", () => {
  it("setWriteQueue atualiza writeQueue no state", () => {
    const state = queuesReducer(undefined, setWriteQueue(writeQueue));
    expect(state.writeQueue).toEqual(writeQueue);
  });

  it("setGovernanceQueue atualiza governanceQueue no state", () => {
    const state = queuesReducer(undefined, setGovernanceQueue(govQueue));
    expect(state.governanceQueue).toEqual(govQueue);
  });

  it("setWriteQueueFilter faz merge parcial preservando page", () => {
    const state = queuesReducer(
      undefined,
      setWriteQueueFilter({ status: "failed" }),
    );
    expect(state.writeQueueFilter).toEqual({ page: 1, status: "failed" });
  });

  it("selectFailedCount retorna 0 quando ambas as filas são null", () => {
    expect(selectFailedCount(rootWith({}))).toBe(0);
  });

  it("selectFailedCount soma failed_count de ambas as filas", () => {
    expect(
      selectFailedCount(rootWith({ writeQueue, governanceQueue: govQueue })),
    ).toBe(5);
  });

  it("selectFailedCount usa apenas a write queue quando governance é null", () => {
    expect(selectFailedCount(rootWith({ writeQueue }))).toBe(3);
  });
});
