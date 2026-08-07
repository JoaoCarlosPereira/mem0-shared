---
name: cy-review-round
description: Revisão de código da implementação no SpecWorkspace Shared; move cards para revisao_codigo, comenta no Kanban MCP e pode gerar reviews-NNN/ em PT-BR para cy-fix-reviews. Use para auditoria de qualidade ou round manual. Não use para fetch de provider, correção de issues, execução de tarefas ou edição de código-fonte.
---

# Round de Review (Kanban MCP)

Execute uma revisão de código estruturada e mantenha o Kanban Shared sincronizado. Opcionalmente produza um diretório `reviews-NNN/` que `cy-fix-reviews` possa processar.

<HARD-GATE>
**KANBAN:** Cards em review DEVEM estar na coluna `revisao_codigo` via `update_task_status` (nunca review "só no chat"). Adicione achados com `add_spec_comment` no card. Não mova para `concluido`. Não pule para `fase_teste` até o review ser aceitável. Veja `../cy-create-prd/references/kanban-shared-obrigatorio.md`.
**NO CODE EDITS** nesta skill — remediação é `cy-fix-reviews` / retorno a `em_andamento`.
</HARD-GATE>

## Entradas Obrigatórias

- `project_id` + slug da feature **ou** `workspace_id`.
- Opcional: `task_id`s específicos ou caminhos de arquivo para delimitar o review.
- Opcional: ainda escrever `reviews-NNN/` local para ferramenta de fix em lote (além dos comentários no Kanban).

## Fluxo de Trabalho

1. Resolver workspace Shared.
   - `list_spec_workspaces(project_id)` / quadro; manter `workspace_id`.
   - Ler PRD / TechSpec / tasks / **adrs** via `read_spec_document`. Não usar `.docs/tasks/` como fallback para specs ou status.
   - Listar cards com `list_tasks(workspace_id, status="em_andamento", include_description=true)` e `list_tasks(workspace_id, status="revisao_codigo", include_description=true)`. Usar `get_task` para confirmar descrição e versão.

2. Identificar escopo do review.
   - Prefira `git diff` / caminhos das descrições dos cards claimed.
   - Se o usuário forneceu caminhos, limite a eles.
   - Se não houver escopo, use `git diff main...HEAD --name-only` ou pergunte ao usuário.
   - Para cada card entrando em review: `update_task_status(task_id, "revisao_codigo", expected_version=...)` se ainda não estiver lá.

3. Executar a revisão de código.
   - Leia `references/review-criteria.md` para severidade e áreas de avaliação.
   - Priorize se >15 arquivos (implementação core primeiro).
   - Cruze com requisitos do PRD/TechSpec Shared.
   - Deduplique issues (um issue por causa raiz).
   - Ignore ruído puro de linter (`make lint` / linter do projeto primeiro).
   - Foque em sinal, não volume.

4. Persistir achados (Kanban primeiro).
   - Para cada achado material: `add_spec_comment` no `task_id` relevante (severidade + arquivo + fix sugerido, PT-BR).
   - Se o review encontrar problemas bloqueantes: mantenha o card em `revisao_codigo` com `is_blocked=true` + `block_reason` e registre comentário; a correção posterior usa `claim_task` para reentrar em `em_andamento`.
   - Se o review estiver limpo para um card: deixe em `revisao_codigo` (ou permita ao executor mover para `fase_teste`) — **esta skill não** move para `fase_teste`/`concluido` a menos que o usuário peça explicitamente para avançar um card limpo para `fase_teste` após review limpo.

5. Opcional: Gerar arquivos de issue locais para `cy-fix-reviews`.
   - Se o caller quiser um diretório em lote: crie `.docs/tasks/<slug>/reviews-NNN/` somente quando houver issues (mesmo frontmatter/template de antes — veja `references/issue-template.md`).
   - Numeração de round e regras de corpo em PT-BR inalteradas.
   - Se não houver issues e nenhum round local foi pedido: reporte review limpo (PT-BR) e pule criação de diretório.

6. Resumir (PT-BR).
   - Recomendação de merge, contagens por severidade, quais cards foram movidos/comentados no quadro Shared.
   - Sugira `cy-fix-reviews` para remediação em lote quando existirem issues locais; caso contrário, corrija via `cy-execute-task` retornando a `em_andamento`.

7. Verificar os artefatos do review.
   - Use `cy-final-verify` só para afirmações de "round de review concluído" sobre arquivos de issue / comentários — não para conclusão de código de produto.
   - Confirme que todo card revisado reflete `revisao_codigo` (ou exceção documentada) no quadro.

## Política de Idioma — PT-BR

| Artefato | Destino |
|----------|---------|
| Comentários de review | `add_spec_comment` no card Shared |
| Issues em lote (opcional) | `reviews-NNN/issue_*.md` |
| PRD / TechSpec | `read_spec_document` |

## Regras Críticas

- Não corrija os issues encontrados (sem edições no código-fonte).
- Não mova cards para `concluido`.
- Não pule a atualização do Kanban ao revisar um card Shared.
- Não crie rounds de review vazios em disco.
- Não chame scripts específicos de provider nem mutações `gh`.

## Tratamento de Erros

- Se workspace/card não puder ser resolvido via MCP, pare e reporte.
- Se o MCP estiver indisponível, PARE — não finja que arquivos locais são o quadro.
- Se nenhum arquivo puder ser identificado para review, peça caminhos ao usuário.
