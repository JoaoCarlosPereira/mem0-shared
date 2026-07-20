---
name: cy-create-tasks
description: Decompõe PRD e TechSpec em tarefas detalhadas em PT-BR, com enriquecimento via exploração do código. Lê PRD/TechSpec e grava a lista mestra (document_type="tasks") e cada tarefa como TaskCard no Mem0 Shared via MCP. Use quando existir PRD/TechSpec e precisar de tarefas executáveis. Não use para PRD, TechSpec ou execução direta de tarefas.
argument-hint: "[feature-name] [prd-file]"
---

# Create Tasks

Decompose requirements into detailed, actionable task files with codebase-informed enrichment.

## Required Inputs

- Feature name identifying the `.docs/tasks/<name>/` directory.
- At minimum, `_prd.md` or `_techspec.md` in that directory.

## Workflow

1. Load type registry.
   - Read `.docs/config.toml`.
   - If it contains `[tasks].types`, use that list as the allowed `type` values.
   - Otherwise use the built-in defaults: `frontend`, `backend`, `docs`, `test`, `infra`, `refactor`, `chore`, `bugfix`.

2. Load context (PRD/TechSpec via MCP — ADR-002).
   - Derive the slug from the feature name; determine the `project_id` (project/repo name, "default" if none).
   - Resolve the workspace: `list_spec_workspaces(project_id=<project>)`; if absent, `create_spec_workspace(project_id, slug, name)`. Keep the `workspace_id`.
   - Read the PRD via `read_spec_document(workspace_id, document_type="prd")` and the TechSpec via `read_spec_document(workspace_id, document_type="techspec")`.
   - Read existing ADRs from `.docs/tasks/<name>/adrs/` (ADRs remain local in this MVP) to understand the decision context.
   - If any MCP tool errors (service unavailable), STOP and report clearly — do NOT read/write local `_prd.md`/`_techspec.md`/task files as a fallback (ADR-002/ADR-007).
   - If the TechSpec is missing (`found=false`):
     - Warn the user that tasks will be higher-level without TechSpec implementation guidance.
     - Derive tasks from PRD functional requirements and user stories instead of TechSpec implementation sections.
     - During enrichment, rely more heavily on codebase exploration to fill `## Implementation Details`, `### Relevant Files`, and `### Dependent Files`.
     - Mark `<requirements>` with PRD-derived behavioral requirements instead of TechSpec-derived technical requirements.
     - Explicitly call out missing implementation detail gaps in the task body instead of inventing specifics.
   - If neither the PRD nor the TechSpec is found in the workspace, stop and ask the user to create at least one first (via `cy-create-prd`/`cy-create-techspec`).
   - Spawn an Agent tool call to explore the codebase for files to create or modify, test patterns, and coding conventions.

3. Break down into tasks.
   - Decompose implementation sections from the TechSpec into granular, independently implementable tasks.
   - **Each task MUST be independently implementable when all of its declared dependencies are met.** No task may require undeclared work from another task. If two tasks share a tight coupling, either merge them or extract the shared piece into a dependency task.
   - **No circular dependencies.** If task A depends on task B, task B must NOT depend on task A (directly or transitively).
   - Each task must have: title, type, complexity, and dependencies.
   - Assign complexity using these criteria:
     - `low`: Single file change, no new interfaces, no concurrency, straightforward logic.
     - `medium`: 2-4 files, may introduce a new interface or struct, limited integration points.
     - `high`: 5+ files, new subsystem or significant refactor, multiple integration points, concurrency involved.
     - `critical`: Cross-cutting change affecting many packages, high risk of regression, requires coordination with other tasks.
   - When a task directly implements or is constrained by a specific ADR, include the ADR reference in the task's "Related ADRs" section under Implementation Details.
   - Embed test requirements in every task. Never create separate tasks dedicated solely to testing.
   - Follow the structure defined in `references/task-template.md`.
   - Refer to `references/task-context-schema.md` for metadata field definitions.

4. Present task breakdown for interactive approval **in PT-BR**.
   - Show all tasks with: titles, descriptions, complexity ratings, and dependency chains.
   - Wait for user feedback before proceeding.
   - If the user requests changes, revise the breakdown and present again.
   - Iterate until the user explicitly approves.

5. Persist the master task list via MCP.
   - Build the master task list in **PT-BR** using this exact markdown table format and persist it as the workspace's `tasks` document with `write_spec_document(workspace_id, document_type="tasks", content=<table>, expected_version=<version|null>)`:
     ```markdown
     # [Nome da Feature] — Lista de Tarefas

     ## Tarefas

     | # | Título | Status | Complexidade | Dependências |
     |---|--------|--------|--------------|--------------|
     | 01 | [Título da tarefa] | pending | [low/medium/high/critical] | [task_NN, ... ou —] |
     ```
   - Task numbering (`task_01`, `task_02`, ...) must be sequential and consistent between the master `tasks` document and the individual `TaskCard`s created in step 6.
   - **Do NOT write any local `_tasks.md` / `task_NN.md` files.** The shared workspace is the single source of truth (ADR-002).
   - **Conflict/unavailability:** on `conflict=true`, re-read and reconcile before retrying; on tool error, STOP and report — no local fallback.

6. Enrich each task and create it as a `TaskCard` via MCP.
   - Enrichment stays a **local agent process** (codebase exploration); only the final result is persisted via MCP. There is no MCP operation for exploration.
   - Process tasks in dependency order (a task after all tasks it depends on) so the board reflects the same order validated by the anti-cycle logic in step 3.
   - For each task, build the complete enriched body locally, then create the card with `create_task(workspace_id, title=<task title>, description=<full enriched body>, branch_ref=<optional>)`.
     - `create_task` persists `title`, `description` and `branch_ref` only. Encode the remaining task metadata **inside `description`** as a metadata header, preserving the template fields: `type`, `complexity`, and `dependencies` (list the dependency task numbers, e.g. `Dependências: task_01, task_02`), followed by the full task body.
     - The card is created in the `tasks` (backlog) column by default — correct for a freshly generated plan.
   - **Partial-failure handling:** track which tasks were created successfully. If a `create_task` (or the step-5 write) errors mid-way (Mem0 Shared unavailable), STOP immediately and report to the user **exactly which tasks were already created** and which remain, so they know the precise partial state — do NOT invent a local fallback file.
   - Map the task to PRD requirements and TechSpec guidance.
   - Spawn an Agent tool call to discover relevant files, dependent files, integration points, and project rules for this specific task.
   - Fill ALL template sections from `references/task-template.md` in **PT-BR** into the card `description`. Every task body MUST contain each of the following sections — omitting any is a failure:
     - `## Visão Geral`: o que a tarefa realiza e por quê, em 2–3 frases.
     - `<critical>` block: lembretes críticos padrão (ler PRD/TechSpec, consultar TechSpec, foco no O QUÊ, minimizar código, testes obrigatórios).
     - `<requirements>` block: requisitos técnicos numerados com linguagem DEVE/DEVE SER.
     - `## Subtarefas`: 3–7 itens de checklist descrevendo O QUÊ, não COMO.
     - `## Detalhes de Implementação`: caminhos de arquivos, pontos de integração. Referenciar TechSpec.
     - `### Arquivos Relevantes`: caminhos descobertos com motivos breves.
     - `### Arquivos Dependentes`: arquivos afetados com motivos breves.
     - `### ADRs Relacionados`: links para ADRs relevantes, ou omitir se não houver.
     - `## Entregáveis`: saídas concretas com testes obrigatórios e meta >= 80% de cobertura.
     - `## Testes`: casos de teste específicos em checklist (unitários e integração).
     - `## Critérios de Sucesso`: resultados mensuráveis incluindo "Todos os testes passando" e "Cobertura >= 80%".
   - Reassess complexity based on exploration findings before creating the card (metadata in `description`).
   - If enrichment fails for one task (a local exploration problem, not an MCP error), report it and continue to the next; report all such failures at the end. An MCP/service error, by contrast, STOPS the run with the partial-state report above.

7. Validate the plan.
   - The anti-cycle and independence checks run in step 3, before any card is created (there are no local files to lint with `compozy tasks validate`, which operates on `.docs/tasks/`).
   - After creation, confirm the board via `list_spec_workspaces(project_id)` and/or `read_spec_document(workspace_id, document_type="tasks")`: the card count matches the master list and dependency order is consistent.
   - Report to the user (PT-BR) the shared workspace (project + slug) and how many `TaskCard`s were created.

## Anti-Patterns

Do NOT produce tasks with these defects:

- **Mega-tasks.** If a task touches more than 7 files or has more than 7 subtasks, it is too broad. Split it into smaller tasks with explicit dependencies between them.
- **TechSpec duplication.** Do NOT copy interface definitions, code snippets, or architectural diagrams from the TechSpec into task files. Reference the TechSpec section by name in PT-BR (e.g., "Ver seção 'Interfaces Principais' do TechSpec") instead of reproducing its content.
- **Vague test cases.** Do NOT write test descriptions like "testar caminho feliz" without detalhe. Each test case must name the specific input, condition, or behavior being verified (e.g., "POST /job/done com job ID inexistente retorna 404").

## Language Policy — PT-BR

**Todos** os artefatos gerados ou enriquecidos por esta skill são em **português brasileiro (PT-BR)**:

| Artefato | Destino |
|----------|---------|
| PRD/TechSpec (entrada) | Mem0 Shared via `read_spec_document` |
| Lista mestra | Mem0 Shared via `write_spec_document` (document_type="tasks") |
| Tarefas | `TaskCard` no quadro via `create_task` (metadados no `description`) |

Regras:
- Apresente o breakdown de tarefas ao usuário em PT-BR antes da aprovação
- Leia PRD, TechSpec e ADRs (já em PT-BR) sem traduzir para inglês ao citar
- Frontmatter YAML mantém chaves em inglês (`status`, `title`, `type`, `complexity`, `dependencies`) por compatibilidade com o parser Compozy; valores de `title` e corpo do arquivo em PT-BR
- Se criar ou alterar PRD/TechSpec/ADR durante o enriquecimento, use os modelos de `cy-create-prd` / `cy-create-techspec`

## Error Handling

- If neither the PRD nor the TechSpec is found in the workspace, stop and ask the user to create at least one first.
- If the MCP tools (Mem0 Shared) are unavailable, stop and report clearly — including, during card creation, exactly which tasks were already created (partial state). Never write a local fallback file (ADR-002/ADR-007).
- If `write_spec_document` (master `tasks` document) returns `conflict=true`, re-read and reconcile before retrying.
- If the user rejects the task breakdown, incorporate all feedback before presenting again.
- If codebase exploration reveals task boundaries that do not match the TechSpec, note the discrepancy and ask the user how to proceed.
