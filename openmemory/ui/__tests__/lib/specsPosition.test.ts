import {
  computeInsertPosition,
  POSITION_STEP,
  sortTasksByPosition,
} from "@/lib/specsPosition";
import { handleCardDrop } from "@/lib/specsBoard";
import type { TaskCard } from "@/types/specs";

const task = (over: Partial<TaskCard> = {}): TaskCard => ({
  id: "t1",
  workspace_id: "w1",
  title: "Card 1",
  status: "tasks",
  is_blocked: false,
  version: 3,
  position: POSITION_STEP,
  ...over,
});

describe("specsPosition", () => {
  it("ordena por position", () => {
    const sorted = sortTasksByPosition([
      task({ id: "b", position: 200 }),
      task({ id: "a", position: 100 }),
    ]);
    expect(sorted.map((t) => t.id)).toEqual(["a", "b"]);
  });

  it("computeInsertPosition append no fim e mid entre cards", () => {
    const col = [
      task({ id: "a", position: 100 }),
      task({ id: "b", position: 300 }),
    ];
    expect(computeInsertPosition(col, "x", null)).toBe(300 + POSITION_STEP);
    expect(computeInsertPosition(col, "x", "b")).toBe(200);
    expect(computeInsertPosition(col, "x", "a")).toBe(50);
  });
});

describe("handleCardDrop position", () => {
  it("drop na mesma coluna atualiza position via updateTask", async () => {
    const updateTask = jest.fn().mockResolvedValue({
      conflict: false,
      task: task({ id: "t1", position: 200, version: 4 }),
    });
    const updateTaskStatus = jest.fn();
    const tasks = [
      task({ id: "t1", status: "em_andamento", position: 100, version: 3 }),
      task({ id: "t2", status: "em_andamento", position: 300 }),
    ];
    const outcome = await handleCardDrop({
      activeId: "t1",
      overColumn: "t2",
      tasks,
      actor: "host-a",
      updateTaskStatus,
      updateTask,
    });
    expect(updateTaskStatus).not.toHaveBeenCalled();
    expect(updateTask).toHaveBeenCalledWith("t1", {
      expected_version: 3,
      position: 150,
    });
    expect(outcome.moved).toBe(true);
    expect(outcome.conflict).toBe(false);
    expect(outcome.position).toBe(150);
  });

  it("mudança de coluna também persiste position", async () => {
    const updateTaskStatus = jest.fn().mockResolvedValue({
      conflict: false,
      task: task({
        id: "t1",
        status: "fase_teste",
        version: 4,
        assignee: "host-a",
      }),
    });
    const updateTask = jest.fn().mockResolvedValue({
      conflict: false,
      task: task({ id: "t1", status: "fase_teste", version: 5, position: 65536 }),
    });
    const outcome = await handleCardDrop({
      activeId: "t1",
      overColumn: "fase_teste",
      tasks: [
        task({
          id: "t1",
          status: "em_andamento",
          assignee: "host-a",
          version: 3,
        }),
      ],
      actor: "host-a",
      updateTaskStatus,
      updateTask,
    });
    expect(updateTaskStatus).toHaveBeenCalled();
    expect(updateTask).toHaveBeenCalledWith(
      "t1",
      expect.objectContaining({ expected_version: 4, position: POSITION_STEP }),
    );
    expect(outcome.moved).toBe(true);
    expect(outcome.position).toBe(POSITION_STEP);
  });
});
