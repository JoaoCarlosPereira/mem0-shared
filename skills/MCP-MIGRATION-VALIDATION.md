# Validação manual — Migração das skills `/cy-create-*` para MCP (Tarefas 9–11)

> As skills `/cy-create-*` rodam por um agente Claude, não por um test runner.
> A validação é **manual, contra um servidor MCP ao vivo** (OpenMemory + Qdrant +
> LLM/embeddings). Este documento é o checklist a executar. Marque cada item ao
> validar no seu ambiente.
>
> **Pré-requisitos do ambiente:**
> - Stack OpenMemory no ar com as tools MCP das Tarefas 7 e 8 disponíveis
>   (`create_spec_workspace`, `list_spec_workspaces`, `write_spec_document`,
>   `read_spec_document`, `search_specs`, `create_task`, `claim_task`,
>   `release_task`, `update_task_status`, `add_spec_comment`).
> - Qdrant com a collection `openmemory_specs` (provisionada no primeiro uso).
> - As skills atualizadas instaladas na máquina do agente
>   (`C:\Users\s293\.claude\skills\cy-create-*` — espelho versionado em
>   `skills/cy-create-*/` neste repo).

## Rollout (decisão registrada)

- As skills piloto foram **espelhadas neste repositório** em `skills/cy-create-prd/`,
  `skills/cy-create-techspec/` e `skills/cy-create-tasks/` para tornar a migração
  auditável no PR. O `SKILL.md` global (`~/.claude/skills/...`) foi atualizado com
  o mesmo conteúdo. **Cada máquina/usuário que usa as skills precisa receber a
  versão atualizada** (copiar do espelho do repo para o caminho global).

---

## Tarefa 9 — `/cy-create-prd`

- [ ] **Fluxo feliz ponta a ponta:** rodar `/cy-create-prd <feature>` até a
      aprovação; confirmar que o PRD foi gravado via `write_spec_document`
      (document_type="prd") no workspace compartilhado e que **nenhum**
      `.docs/tasks/<slug>/_prd.md` local foi criado.
- [ ] **Workspace idempotente:** rodar de novo com o mesmo slug; confirmar que
      reaproveita o workspace existente (não cria duplicado) e entra em modo de
      atualização (lê a versão atual via `read_spec_document`).
- [ ] **Indisponibilidade do serviço:** parar o servidor MCP e rodar a skill;
      confirmar que ela **falha com mensagem clara**, sem gravar `_prd.md` local.
- [ ] **Conflito de versão:** simular duas gravações concorrentes (gravar uma vez
      por outro caminho e então aprovar a skill com versão desatualizada);
      confirmar que a skill informa o conflito, relê a versão atual e **não
      sobrescreve silenciosamente**.
- [ ] **HARD-GATE preservado:** confirmar que nenhuma gravação MCP ocorre antes da
      aprovação do usuário.

---

## Tarefa 10 — `/cy-create-techspec`

- [ ] **Fluxo encadeado PRD → TechSpec:** para um workspace com PRD já gravado pela
      Tarefa 9, rodar `/cy-create-techspec`; confirmar que o PRD é lido via
      `read_spec_document` (document_type="prd") e a TechSpec é gravada via
      `write_spec_document` (document_type="techspec") — sem `_prd.md`/`_techspec.md`
      locais.
- [ ] **Modo standalone (sem PRD):** rodar em um workspace sem PRD; confirmar que a
      skill **pede a descrição ao usuário** em vez de falhar.
- [ ] **ADRs locais:** confirmar que os ADRs criados nesta skill continuam gravados
      em `.docs/tasks/<name>/adrs/` (fora do escopo remoto do MVP).
- [ ] **Conflito de versão:** simular gravação concorrente da TechSpec; confirmar que
      não sobrescreve silenciosamente.
- [ ] **Indisponibilidade do serviço:** parar o MCP e confirmar falha clara, sem
      fallback local.

---

## Tarefa 11 — `/cy-create-tasks`

- [ ] **Fluxo encadeado PRD → TechSpec → Tasks:** para um workspace com PRD e
      TechSpec já gravados (Tarefas 9 e 10), rodar `/cy-create-tasks`; confirmar que
      PRD/TechSpec são lidos via `read_spec_document`, a lista mestra é gravada via
      `write_spec_document` (document_type="tasks") e **cada tarefa vira uma
      `TaskCard`** via `create_task` — sem `_tasks.md`/`task_NN.md` locais.
- [ ] **Metadados e dependências:** confirmar que tipo/complexidade/dependências
      ficam preservados no `description` da `TaskCard` e que a ordem de dependência
      é consistente no quadro.
- [ ] **Falha parcial:** simular indisponibilidade do MCP **após** algumas tasks
      criadas; confirmar que a skill reporta **exatamente quais tasks já foram
      criadas** antes da falha, sem inventar arquivo local.
- [ ] **Cards no backlog:** confirmar que as tasks nascem na coluna `tasks`
      (backlog) do quadro Kanban.
