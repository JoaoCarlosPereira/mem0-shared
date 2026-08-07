---
name: cy-execute-task
description: Executa uma TaskCard do SpecWorkspace Mem0 Shared ponta a ponta com claim, implementação, revisão, testes e atualização do Kanban MCP. Artefatos e comunicação em PT-BR. Use quando houver card no quadro (ou task_id/workspace). Não use para correção de reviews em lote, verificação isolada ou planejamento PRD/TechSpec.
---

# Executar Task de Spec (Kanban MCP)

Execute uma `TaskCard` Shared do claim até `concluido`, respeitando o pipeline obrigatório do Kanban.

<HARD-GATE>
**KANBAN:** Antes de qualquer edição de código, chame `claim_task`. Atualize o quadro Shared em **cada** mudança de fase na mesma interação. Nunca rastreie conclusão apenas no chat ou em `.docs/tasks/*.md` local.
**PIPELINE (sem pular):** `tasks` → `em_andamento` → `revisao_codigo` → `fase_teste` → `concluido`. Nunca pule direto para `concluido`. Veja `../cy-create-prd/references/kanban-shared-obrigatorio.md`.
**FIDELIDADE ABSOLUTA:** Trabalhe estritamente dentro da especificação. NÃO complete informações por conta própria. Se o usuário alterar requisitos durante a execução, **você DEVE atualizar a spec (PRD/TechSpec/TaskCard)** no MCP antes de mexer no código.
**MCP `kanban`:** Após cada `claim_task` / `update_task_status`, leia `kanban.means` e **`kanban.do_now`** na resposta e execute essa instrução antes de avançar de coluna. Ignore isso = execução incompleta.
**VERIFY:** Use `cy-final-verify` enquanto o card estiver em `fase_teste` antes de mover para `concluido`.
</HARD-GATE>

## Entradas Obrigatórias

- `project_id` (nome do repo/projeto) e slug da feature **ou** `workspace_id` + `task_id` explícitos.
- Opcional: modo auto-commit.
- Opcional: sinal para usar `cy-workflow-memory` / mem0 para notas duráveis.

## Fluxo de Trabalho

1. Resolver contexto Shared (MCP).
   - Resolver workspace: `list_spec_workspaces(project_id)` / quadro; manter `workspace_id`.
   - Identificar a `TaskCard` (`task_id`, `version`, `status`, `description`). Prefira um `task_id` explícito.
   - **Como descobrir o `task_id` quando ele não foi informado:** chame `list_tasks(workspace_id, status="tasks", include_description=true)`, filtre cards desbloqueados e confirme dependências. Use `get_task(task_id)` antes do claim para ler a descrição e a versão atuais.
     - O documento mestre `tasks` e sua coluna `Card ID` servem para rastreabilidade e validação cruzada, não são o único índice técnico.
     - Se não houver cards no backlog, consulte as demais colunas antes de concluir que não há trabalho. Não invente ids e não implemente sem claim.
   - Ler PRD / TechSpec / tasks master / **adrs** via `read_spec_document` (`prd`, `techspec`, `tasks`, `adrs`). **Não** confie em `adrs/*.md` local.
   - Exigir `get_task(task_id)` antes do claim para obter a descrição e a versão atuais; após conflitos ou alterações externas, reler o card antes de prosseguir.
   - Após a leitura, verifique conflitos entre a descrição do card, TechSpec e ADRs. Se os requisitos se contradizerem, pare e reporte — não adivinhe.
   - Se mem0 / workflow-memory estiver disponível, carregue contexto durável antes de editar (veja `cy-workflow-memory`).

2. Claim antes de codar.
   - Chame `claim_task(task_id)`. Com `claimed=false`, **não** edite código; escolha outro card ou pare.
   - Mantenha o `version` retornado para chamadas posteriores de `update_task_status`.
   - O card deve estar em `em_andamento` antes de qualquer implementação.
   - **Leia `kanban.do_now` da resposta** e siga (implementar; só depois `revisao_codigo`).

3. Montar o checklist de execução.
   - Extraia entregáveis, critérios de aceite e cada item de Validation/Test da `description` do card em um checklist numerado.
   - Imprima o checklist (PT-BR) antes de implementar.
   - Capture um sinal de baseline pré-alteração que comprove que a tarefa ainda não está concluída.
   - Não entre em `revisao_codigo` até que cada item do checklist tenha sido tratado no código (ou explicitamente adiado com `add_spec_comment`).

4. Implementar a tarefa (coluna: `em_andamento`).
   - **Fidelidade estrita:** Mantenha o escopo restrito ao card. Se o card for ambíguo, PARE e pergunte ao usuário. Não invente requisitos ou tome decisões funcionais por conta própria.
   - **Manter Specs Atualizadas:** Se o usuário pedir uma mudança de escopo, regras de negócio ou requisitos durante a execução, você DEVE atualizar o documento fonte via MCP (`write_spec_document` para PRD/TechSpec ou `update_task` para a TaskCard) **ANTES** de aplicar a alteração no código. As specs são a única fonte da verdade e não podem ficar defasadas.
   - Siga os padrões do repositório e APIs reais de dependências.
   - Em bloqueio: `update_task_status` com o mesmo status + `is_blocked=true` + `block_reason` **e** `add_spec_comment` — não narre apenas no chat.
   - Registre descobertas fora de escopo como notas/comentários de follow-up, não como expansão silenciosa de escopo.

5. Mover para revisão de código (coluna: `revisao_codigo`) — **obrigatório**.
   - Quando a implementação estiver pronta para review: `update_task_status(task_id, "revisao_codigo", expected_version=...)`.
   - **Leia `kanban.do_now`** (revisar diff, comentar; próxima = `fase_teste`).
   - Faça self-review do diff; resolva problemas bloqueantes ou comente-os.
   - Use `add_spec_comment` para notas de review no card.
   - **Não** chame `concluido` daqui. **Não** pule esta coluna.

6. Mover para fase de teste (coluna: `fase_teste`) — **obrigatório**.
   - Após review aceitável: `update_task_status(..., "fase_teste", ...)`.
   - Execute todo comando de teste/validação do card **e** use `cy-final-verify`.
   - Publique evidência (comando + resumo do exit code) via `add_spec_comment` quando útil.
   - Se a verificação falhar: permaneça em `fase_teste` (bloqueado) ou volte a `em_andamento` para corrigir — **nunca** `concluido`.

7. Concluir (coluna: `concluido`) — somente a partir de `fase_teste` com PASS.
   - Somente após veredito **APROVADO** do `cy-final-verify`: `update_task_status(..., "concluido", ...)`.
   - Opcionalmente sincronize mem0 / workflow memory com aprendizados duráveis.
   - Leia `references/tracking-checklist.md` antes de declarar concluído.
   - Sequência: evidência PASS → Kanban `concluido` → commit opcional.

8. Comportamento de commit.
   - Se auto-commit estiver habilitado, crie um commit local somente após o Kanban estar em `concluido` (ou claramente após evidência PASS se o commit preceder a mudança final de coluna na mesma interação — o quadro ainda deve chegar a `concluido` antes de dizer ao usuário que a tarefa terminou).
   - Se auto-commit estiver desabilitado, deixe o diff pronto para review.
   - Nunca faça push automaticamente.
   - Se abandonar: `release_task(task_id)` de volta ao backlog — nunca simule `concluido`.

## Política de Idioma — PT-BR

| Artefato | Destino |
|----------|---------|
| PRD / TechSpec / tasks | Mem0 Shared via `read_spec_document` |
| Card / coluna / comentários | Kanban MCP (`claim_task`, `update_task_status`, `add_spec_comment`) |
| Memória durável | mem0 MCP / `cy-workflow-memory` |

Regras:
- Comunicação com o usuário e comentários no card em PT-BR
- Não use arquivos locais `_prd.md` / `task_*.md` como fonte de verdade do status
- Código segue as convenções do repositório

## Tratamento de Erros

- Se `claim_task` falhar por exclusividade, pare de codar e reporte `current_assignee`.
- Se `update_task_status` retornar `conflict=true`, releia quadro/versão e tente de novo — nunca sobrescreva cegamente.
- Se o MCP estiver indisponível, PARE e reporte — não use arquivos locais de status como system of record.
- Se a validação falhar, mantenha o card fora de `concluido` até corrigir.
