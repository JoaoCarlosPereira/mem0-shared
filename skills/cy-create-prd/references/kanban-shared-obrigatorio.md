# Quadro Kanban Shared — regra obrigatória

O quadro Kanban do **Mem0 Shared** (UI Documentações / SpecWorkspace) é a **única fonte de verdade** do progresso da equipe. Agentes MCP **DEVEM** refletir nele **cada** atividade — nunca só no chat, em arquivos locais ou no final da sessão.

## Iron law

**Nenhuma atividade relevante sem atualizar o quadro.** Se o agente fez progresso e o card/workspace no Shared ainda mostra o estado antigo, a execução está incompleta.

## Pipeline de colunas (obrigatório — sem pular)

Todo `TaskCard` **DEVE** percorrer as colunas **nesta ordem**. Proibido ir de `em_andamento` (ou backlog) direto para `concluido`.

```
tasks (backlog)
  │  claim_task
  ▼
em_andamento          ← implementação / coding
  │  update_task_status
  ▼
revisao_codigo        ← review do diff; checklist + comentários no card
  │  update_task_status
  ▼
fase_teste            ← rodar testes / evidência fresca
  │  update_task_status (só com evidência APROVADA)
  ▼
concluido
```

| Coluna | Quando entrar | Critério mínimo antes de avançar |
|--------|---------------|----------------------------------|
| `tasks` | `create_task` | Dependências atendidas; card escolhido |
| `em_andamento` | **somente** `claim_task` | Código no escopo do card; sem claim = não editar |
| `revisao_codigo` | após implementação “pronta para review” | Diff revisado (self-review ou peer); issues anotados com `add_spec_comment`; **não** pular esta coluna |
| `fase_teste` | após review ok (ou correções da review aplicadas) | Suite/comandos de teste executados **nesta** fase; evidência (comando + exit code) no comentário ou na resposta |
| `concluido` | **somente** vindo de `fase_teste` | Evidência de teste APROVADA; nunca concluir a partir de `em_andamento` ou `revisao_codigo` |

**Voltar coluna:** se a review ou o teste reprovarem, volte com `update_task_status` para `em_andamento` (corrigir) ou mantenha `revisao_codigo` / `fase_teste` com `is_blocked=true` + motivo — **não** salte para `concluido`.

**Release:** `release_task` só para devolver ao backlog (`tasks`). Não use release para “concluir”.

## O que atualizar

| Momento | Ação MCP obrigatória |
|---------|----------------------|
| Workspace criado / PRD em andamento | `create_spec_workspace` (se preciso); manter workspace em `planejamento` via `update_spec_workspace_status` |
| PRD aprovado e gravado | `write_spec_document` (prd); se houver ADRs, **também** `write_spec_document` (adrs) com o texto completo |
| TechSpec aprovado e gravado | `write_spec_document` (techspec) + **sempre** `write_spec_document` (adrs) com ADRs técnicos (e produto, se mudaram); se o trabalho técnico começou de fato, `update_spec_workspace_status(..., "ativo")` |
| Lista de tarefas criada | `write_spec_document` (tasks) + `create_task` para **cada** card (nascem em `tasks` / backlog) |
| Antes de implementar | `claim_task(task_id)` → `em_andamento` |
| Bloqueio | `update_task_status` com `is_blocked=true` + `block_reason` **e** `add_spec_comment` |
| Implementação pronta | `update_task_status(..., "revisao_codigo", expected_version=...)` — **nunca** `concluido` aqui |
| Review ok | `update_task_status(..., "fase_teste", ...)` — **nunca** `concluido` aqui |
| Testes ok com evidência | `update_task_status(..., "concluido", ...)` — **somente** nesta etapa |
| Desistir / devolver ao backlog | `release_task(task_id)` |
| Feature/workspace encerrado | `update_spec_workspace_status(..., "concluido")` |

Colunas válidas: `tasks` | `em_andamento` | `revisao_codigo` | `fase_teste` | `concluido`.

## Documento `adrs` (não é card Kanban)

Tipos de documento SDD: `prd` | `techspec` | `tasks` | **`adrs`**.

- ADRs **não** viram TaskCards. Vivem no documento versionado `document_type="adrs"` (alias MCP `adr`).
- Fonte de verdade do texto completo: `write_spec_document(..., document_type="adrs", ...)`.
- PRD/TechSpec/tasks referenciam via links markdown `[ADR-NNN: Título](adrs/adr-NNN.md)` (a UI Shared abre o doc `adrs` e rola até `#adr-NNN`).
- **Proibido** deixar ADRs só em arquivos locais `.docs/.../adrs/*.md` ou só embutidos no PRD/TechSpec sem gravar o documento `adrs`.
- Ao criar ou alterar qualquer ADR: ler `read_spec_document(..., "adrs")`, mesclar o texto completo (`### ADR-NNN: ...`), gravar com `expected_version` correto.

## Anti-padrões (proibidos)

- Implementar código sem `claim_task`
- **Pular `revisao_codigo` ou `fase_teste`** e ir direto a `concluido`
- Marcar `concluido` no mesmo turno em que ainda está implementando (sem passar pelas duas colunas intermediárias com atualização MCP explícita em cada uma)
- Dizer “tarefa concluída” no chat sem o card estar em `concluido` **e** ter passado por review + teste no quadro
- Deixar bloqueio só na conversa
- Atualizar só arquivos locais e ignorar o quadro
- Empilhar várias colunas “no final” num único `update_task_status` para `concluido` — cada transição real = uma chamada MCP na hora certa
- Ignorar `conflict=true` / `claimed=false` — reler o quadro e reconciliar

## Checklist rápido (antes de responder ao usuário)

1. O card no Shared está na coluna correta desta fase?
2. Se avancei de fase, chamei `update_task_status` (ou `claim_task`) **nesta** interação?
3. Li o campo **`kanban.do_now`** da resposta MCP e executei essa instrução (não pulei para a próxima coluna)?
4. Se vou a `concluido`, o card **já esteve** em `revisao_codigo` e depois em `fase_teste` (com evidência de teste)?
5. Se estou bloqueado, o card está marcado e comentado?

## Respostas MCP (`kanban`)

Toda resposta bem-sucedida de `create_task`, `claim_task`, `release_task` e `update_task_status` inclui:

```json
"kanban": {
  "column": "em_andamento",
  "label": "Em andamento",
  "means": "…o que a coluna representa…",
  "do_now": "…o que DEVE ser feito agora…",
  "next_column": "revisao_codigo",
  "next_action": "update_task_status",
  "pipeline": ["tasks","em_andamento","revisao_codigo","fase_teste","concluido"],
  "pipeline_rule": "…"
}
```

**Obrigatório:** após cada chamada, ler `kanban.do_now` e cumprir essa coluna **antes** de chamar a próxima transição. Avanço que pula coluna é rejeitado com `policy: true, code: "skip_pipeline"`.
