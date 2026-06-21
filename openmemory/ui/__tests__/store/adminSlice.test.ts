import adminReducer, {
  setAdminOverview,
  setPollingInterval,
} from "@/store/adminSlice";
import type { AdminOverview } from "@/types/admin";

const overview: AdminOverview = {
  total_projects: 3,
  total_memories: 42,
  memories_last_24h: 5,
  write_queue_queued: 1,
  write_queue_processing: 0,
  write_queue_failed: 2,
  governance_queue_queued: 0,
  governance_queue_processing: 0,
  governance_queue_failed: 0,
};

describe("adminSlice", () => {
  it("state inicial tem overview=null e pollingIntervalMs=15000", () => {
    const state = adminReducer(undefined, { type: "@@INIT" });
    expect(state.overview).toBeNull();
    expect(state.pollingIntervalMs).toBe(15000);
  });

  it("setAdminOverview atualiza o state com o overview recebido", () => {
    const state = adminReducer(undefined, setAdminOverview(overview));
    expect(state.overview).toEqual(overview);
    expect(state.loading).toBe(false);
  });

  it("setPollingInterval mantém o valor dentro de 10000–60000", () => {
    let state = adminReducer(undefined, setPollingInterval(30000));
    expect(state.pollingIntervalMs).toBe(30000);
    state = adminReducer(undefined, setPollingInterval(5000));
    expect(state.pollingIntervalMs).toBe(10000);
    state = adminReducer(undefined, setPollingInterval(120000));
    expect(state.pollingIntervalMs).toBe(60000);
  });
});
