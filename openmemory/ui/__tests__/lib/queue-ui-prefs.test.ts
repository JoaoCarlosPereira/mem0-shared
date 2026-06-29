import {
  acknowledgeFailedJobs,
  countUnacknowledgedFailed,
  getQueueUiPrefs,
  isHideCompleted,
  queueJobKey,
  setHideCompleted,
} from "@/lib/queue-ui-prefs";

const STORAGE_KEY = "mem0-admin-queue-ui-prefs-v1";

beforeEach(() => {
  window.localStorage.clear();
});

describe("queue-ui-prefs", () => {
  it("acknowledgeFailedJobs marca IDs como vistos", () => {
    acknowledgeFailedJobs(["w1"], ["g1"]);
    expect(countUnacknowledgedFailed(["w1"], ["g1"])).toBe(0);
    expect(countUnacknowledgedFailed(["w2"], [])).toBe(1);
  });

  it("setHideCompleted oculta concluídos por fila", () => {
    expect(isHideCompleted("write")).toBe(false);
    setHideCompleted("write", true);
    expect(isHideCompleted("write")).toBe(true);
    expect(getQueueUiPrefs().hideCompleted.governance).toBe(false);
  });

  it("queueJobKey prefixa o tipo", () => {
    expect(queueJobKey("write", "abc")).toBe("write:abc");
    expect(window.localStorage.getItem(STORAGE_KEY)).toBeNull();
  });
});
