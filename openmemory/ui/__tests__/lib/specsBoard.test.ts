import {
  BOARD_COLUMNS,
  TASK_COLUMN_KEYS,
  handleCardDrop,
  isTaskColumn,
} from "@/lib/specsBoard";
import type { TaskCard } from "@/types/specs";

const task = (over: Partial<TaskCard> = {}): TaskCard => ({
  id: "t1",
  workspace_id: "w1",
  title: "Card 1",
  status: "tasks",
  is_blocked: false,
  version: 3,
  ...over,
});

describe("specsBoard columns", () => {
  it("tem SDD (documentos) + as 5 colunas de task fixas", () => {
    expect(BOARD_COLUMNS[0]).toMatchObject({ key: "SDD", isDocuments: true });
    expect(BOARD_COLUMNS.map((c) => c.key)).toEqual([
      "SDD",
      "tasks",
      "em_andamento",
      "revisao_codigo",
      "fase_teste",
      "concluido",
    ]);
  });

  it("isTaskColumn distingue colunas de task de SDD", () => {
    expect(isTaskColumn("em_andamento")).toBe(true);
    expect(isTaskColumn("SDD")).toBe(false);
    expect(TASK_COLUMN_KEYS).toContain("concluido");
  });
});

describe("handleCardDrop", () => {
  it("drop numa coluna nova chama updateTaskStatus com o expected_version atual", async () => {
    const updateTaskStatus = jest
      .fn()
      .mockResolvedValue({ conflict: false, task: task({ status: "em_andamento" }) });
    const outcome = await handleCardDrop({
      activeId: "t1",
      overColumn: "em_andamento",
      tasks: [task()],
      actor: "host-a",
      updateTaskStatus,
    });
    expect(updateTaskStatus).toHaveBeenCalledWith("t1", {
      expected_version: 3,
      new_status: "em_andamento",
      actor: "host-a",
    });
    expect(outcome.moved).toBe(true);
    expect(outcome.conflict).toBe(false);
    expect(outcome.targetStatus).toBe("em_andamento");
  });

  it("resposta 409 (conflict) é propagada como conflict=true", async () => {
    const updateTaskStatus = jest
      .fn()
      .mockResolvedValue({ conflict: true, current_version: 5, current_status: "revisao_codigo" });
    const outcome = await handleCardDrop({
      activeId: "t1",
      overColumn: "concluido",
      tasks: [task()],
      updateTaskStatus,
    });
    expect(outcome.moved).toBe(true);
    expect(outcome.conflict).toBe(true);
    expect(outcome.result?.current_version).toBe(5);
  });

  it("drop na MESMA coluna não dispara atualização", async () => {
    const updateTaskStatus = jest.fn();
    const outcome = await handleCardDrop({
      activeId: "t1",
      overColumn: "tasks",
      tasks: [task({ status: "tasks" })],
      updateTaskStatus,
    });
    expect(updateTaskStatus).not.toHaveBeenCalled();
    expect(outcome.moved).toBe(false);
  });

  it("drop sem alvo ou fora de coluna de task é ignorado", async () => {
    const updateTaskStatus = jest.fn();
    expect(
      (await handleCardDrop({ activeId: "t1", overColumn: null, tasks: [task()], updateTaskStatus }))
        .moved,
    ).toBe(false);
    expect(
      (await handleCardDrop({ activeId: "t1", overColumn: "SDD", tasks: [task()], updateTaskStatus }))
        .moved,
    ).toBe(false);
    expect(updateTaskStatus).not.toHaveBeenCalled();
  });
});
