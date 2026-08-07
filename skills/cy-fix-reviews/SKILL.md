---
name: cy-fix-reviews
description: Corrige issues de review (reviews-NNN/ e/ou comentários do Kanban Shared); move cards para em_andamento, aplica fixes, e reinsere no pipeline revisao_codigo → fase_teste → concluido. Triagem em PT-BR. Use para resolver issues documentados. Não use para execução de tarefa limpa sem review nem fetch de provider.
---

# Corrigir Reviews (Kanban MCP)

Execute remediação de review com o Kanban Shared como fonte de verdade do status.

<HARD-GATE>
**KANBAN:** Antes de editar código para um card, garanta que está em `em_andamento` usando `claim_task` (inclusive para reentrada a partir de `revisao_codigo` ou `fase_teste`). `update_task_status` não entra em `em_andamento`. Após os fixes, reentre no pipeline obrigatório: `revisao_codigo` → `fase_teste` → `concluido` (sem pular). Veja `../cy-create-prd/references/kanban-shared-obrigatorio.md`.
**VERIFY:** `cy-final-verify` em `fase_teste` antes de `concluido`.
</HARD-GATE>

## Entradas Obrigatórias

- Arquivos de issue delimitados em `<batch_issue_files>` **e/ou** `task_id`s Shared com comentários de review.
- `workspace_id` / `project_id` quando existirem cards no quadro.
- Fluxo de verificação do repositório exigido por `cy-final-verify`.

## Fluxo de Trabalho

1. Reunir contexto do round + quadro.
   - Ler frontmatter dos issues delimitados (provider, round, severity) quando existirem arquivos locais.
   - Resolver cards Shared: quadro / `task_id`s ligados ao lote; anotar `version` e coluna.
   - Ler `<batch_scope>` para nome PRD/feature, caminhos, flags de auto-commit.

2. Triagem.
   - Ler todo issue local e os comentários do card com `list_spec_comments(target_type="task", target_id=<task_id>)` antes de editar. Use `get_task(task_id)` para confirmar descrição e versão atuais e `list_task_history(task_id)` quando precisar auditar transições.
   - Arquivos locais: definir `status` no frontmatter como `valid` ou `invalid`; escrever `## Triagem` em PT-BR.
   - Nos cards Shared: `add_spec_comment` com decisão de triagem quando útil.

3. Mover cards para implementação.
   - Para cada card com fixes válidos: use `claim_task(task_id)` para entrar ou reentrar em `em_andamento`; isso também renova a lease quando o agente já é o assignee. Se outro assignee estiver ativo, pare e reporte. Limpe bloqueio ao iniciar trabalho.
   - Não edite código enquanto a coluna oficial ainda disser `concluido`.

4. Corrigir issues válidos por completo.
   - Ordem de severidade: critical → high → medium → low.
   - Fixes em qualidade de produção; adicione/atualize testes quando o comportamento mudar.
   - Mantenha alterações restritas aos arquivos delimitados; documente exceções na triagem / comentário no card.
   - Sem refactors não relacionados.

5. Fechar arquivos de issue locais (se houver).
   - `valid` → `resolved` somente após código + caminho de verificação concluídos.
   - `invalid` → documente o motivo, depois `resolved`.

6. Reentrar no pipeline Kanban (obrigatório).
   - Após fixes prontos para review: `update_task_status(..., "revisao_codigo")` + `add_spec_comment` breve.
   - Após review ok: `update_task_status(..., "fase_teste")`.
   - Execute `cy-final-verify`; com APROVADO: `update_task_status(..., "concluido")`.
   - Com REPROVADO: permaneça bloqueado em `fase_teste` ou volte a `em_andamento` — nunca pule para `concluido`.

7. Verificar antes de afirmações de conclusão.
   - Use `cy-final-verify` antes de qualquer afirmação de conclusão ou commit automático.
   - Se todos os issues forem invalid e nenhum código mudou: pule commit vazio; ainda confirme estado do quadro.
   - Deixe o diff pronto a menos que auto-commit esteja habilitado.

## Política de Idioma — PT-BR

| Conteúdo | Onde |
|----------|------|
| Triagem / comentários | issue files e/ou `add_spec_comment` |
| Status oficial | colunas Kanban MCP |

## Regras Críticas

- Não busque/exporte reviews dentro deste fluxo.
- Não chame scripts específicos de provider nem mutações `gh`.
- Não marque issues como `resolved` nem cards como `concluido` antes de trabalho + verificação completos.
- Não pule `revisao_codigo` ou `fase_teste` após corrigir.
