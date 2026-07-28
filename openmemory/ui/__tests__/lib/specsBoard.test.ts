import {
  BOARD_COLUMNS,
  TASK_COLUMN_KEYS,
  handleCardDrop,
  isTaskColumn,
  pickBoardDropTarget,
  resolveDropColumn,
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

describe("resolveDropColumn", () => {
  it("aceita id de coluna diretamente", () => {
    expect(resolveDropColumn("em_andamento", [])).toBe("em_andamento");
  });

  it("resolve coluna a partir do id de outro card (drop sobre card)", () => {
    const tasks = [
      task({ id: "a", status: "tasks" }),
      task({ id: "b", status: "revisao_codigo" }),
    ];
    expect(resolveDropColumn("b", tasks)).toBe("revisao_codigo");
  });

  it("ignora id desconhecido e SDD", () => {
    expect(resolveDropColumn(null, [])).toBeNull();
    expect(resolveDropColumn("SDD", [])).toBeNull();
    expect(resolveDropColumn("missing", [task()])).toBeNull();
  });
});

describe("pickBoardDropTarget", () => {
  it("prefere card (type=task) sobre coluna quando ambos batem", () => {
    expect(
      pickBoardDropTarget([
        { id: "em_andamento", data: { type: "column", status: "em_andamento" } },
        { id: "card-x", data: { type: "task", status: "em_andamento" } },
      ]),
    ).toBe("card-x");
  });

  it("escolhe coluna de task quando não há card sob o ponteiro", () => {
    expect(
      pickBoardDropTarget([
        { id: "SDD", data: { type: "column", status: "SDD" } },
        { id: "fase_teste", data: { type: "column", status: "fase_teste" } },
      ]),
    ).toBe("fase_teste");
  });

  it("ignora SDD sozinho e retorna null", () => {
    expect(
      pickBoardDropTarget([{ id: "SDD", data: { type: "column", status: "SDD" } }]),
    ).toBeNull();
  });

  it("lista vazia retorna null", () => {
    expect(pickBoardDropTarget([])).toBeNull();
  });
});

describe("handleCardDrop", () => {
  it("tasks → em_andamento usa claimTask (não updateTaskStatus)", async () => {
    const updateTaskStatus = jest.fn();
    const claimTask = jest.fn().mockResolvedValue({ claimed: true, version: 4 });
    const outcome = await handleCardDrop({
      activeId: "t1",
      overColumn: "em_andamento",
      tasks: [task()],
      actor: "host-a",
      updateTaskStatus,
      claimTask,
    });
    expect(claimTask).toHaveBeenCalledWith("t1", "host-a");
    expect(updateTaskStatus).not.toHaveBeenCalled();
    expect(outcome.moved).toBe(true);
    expect(outcome.conflict).toBe(false);
    expect(outcome.targetStatus).toBe("em_andamento");
  });

  it("drop sobre outro card move para a coluna desse card", async () => {
    const updateTaskStatus = jest.fn().mockResolvedValue({ conflict: false });
    const tasks = [
      task({ id: "t1", status: "em_andamento", assignee: "host-a" }),
      task({ id: "t2", status: "fase_teste" }),
    ];
    const outcome = await handleCardDrop({
      activeId: "t1",
      overColumn: "t2",
      tasks,
      actor: "host-a",
      updateTaskStatus,
    });
    expect(updateTaskStatus).toHaveBeenCalledWith("t1", {
      expected_version: 3,
      new_status: "fase_teste",
      actor: "host-a",
    });
    expect(outcome.moved).toBe(true);
    expect(outcome.targetStatus).toBe("fase_teste");
  });

  it("claim negado propaga claimedDenied", async () => {
    const claimTask = jest
      .fn()
      .mockResolvedValue({ claimed: false, current_assignee: "host-b" });
    const outcome = await handleCardDrop({
      activeId: "t1",
      overColumn: "em_andamento",
      tasks: [task()],
      actor: "host-a",
      updateTaskStatus: jest.fn(),
      claimTask,
    });
    expect(outcome.moved).toBe(true);
    expect(outcome.conflict).toBe(true);
    expect(outcome.claimedDenied).toBe(true);
    expect(outcome.currentAssignee).toBe("host-b");
  });

  it("voltar ao backlog usa releaseTask", async () => {
    const releaseTask = jest.fn().mockResolvedValue({});
    const updateTaskStatus = jest.fn();
    const outcome = await handleCardDrop({
      activeId: "t1",
      overColumn: "tasks",
      tasks: [task({ status: "revisao_codigo" })],
      actor: "host-a",
      updateTaskStatus,
      releaseTask,
    });
    expect(releaseTask).toHaveBeenCalled();
    expect(updateTaskStatus).not.toHaveBeenCalled();
    expect(outcome.moved).toBe(true);
    expect(outcome.targetStatus).toBe("tasks");
  });

  it("demais colunas usam updateTaskStatus com expected_version", async () => {
    const updateTaskStatus = jest
      .fn()
      .mockResolvedValue({ conflict: false, task: task({ status: "fase_teste" }) });
    const outcome = await handleCardDrop({
      activeId: "t1",
      overColumn: "fase_teste",
      tasks: [task({ status: "em_andamento", assignee: "host-a" })],
      actor: "host-a",
      updateTaskStatus,
    });
    expect(updateTaskStatus).toHaveBeenCalledWith("t1", {
      expected_version: 3,
      new_status: "fase_teste",
      actor: "host-a",
    });
    expect(outcome.moved).toBe(true);
    expect(outcome.conflict).toBe(false);
  });

  it("resposta 409 (conflict) é propagada como conflict=true", async () => {
    const updateTaskStatus = jest
      .fn()
      .mockResolvedValue({ conflict: true, current_version: 5, current_status: "revisao_codigo" });
    const outcome = await handleCardDrop({
      activeId: "t1",
      overColumn: "concluido",
      tasks: [task({ status: "fase_teste" })],
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
