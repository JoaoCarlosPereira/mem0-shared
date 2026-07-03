---
status: completed
title: Modelos e migração Alembic de identidade (machines, agent_tokens, link_audit_logs, colunas em users)
type: backend
complexity: medium
dependencies: []
---

# Modelos e migração Alembic de identidade (machines, agent_tokens, link_audit_logs, colunas em users)

## Visão Geral
Cria a fundação de dados dos três conceitos do PRD (Usuário, Máquina, Agente): tabelas `machines`, `agent_tokens` e `link_audit_logs`, e colunas de identidade Google em `users`. Todas as demais tarefas dependem destas entidades. A migração é 100% aditiva e preserva as linhas legadas (hostname) intactas.

<critical>
- SEMPRE LEIA o PRD e o TechSpec antes de começar
- CONSULTE O TECHSPEC para detalhes de implementação — não duplique aqui
- FOQUE NO "O QUÊ" — descreva o que precisa ser feito, não como
- MINIMIZE CÓDIGO — mostre código só para ilustrar estrutura atual ou áreas problemáticas
- TESTES OBRIGATÓRIOS — toda tarefa DEVE incluir testes nos entregáveis
</critical>

<requirements>
- `users` DEVE ganhar as colunas `google_sub` (String, único, nullable), `display_name`, `avatar_url` e `user_type` (`person`|`legacy_host`), com backfill `legacy_host` para todas as linhas existentes.
- DEVE existir a tabela `machines` com `hostname` único/indexado, `linked_user_id` e `legacy_user_id` (FKs nullable para `users.id`), `status` (`unlinked`|`linked`|`conflict`), `linked_at`, `linked_by` e timestamps, conforme "Modelos de Dados" do TechSpec.
- DEVE existir a tabela `agent_tokens` com `token_hash` (SHA-256, indexado), `prefix`, `created_at`, `revoked_at`, `last_used_at`; o token em claro NUNCA é persistido.
- DEVE haver garantia de no máximo 1 token ativo por usuário (índice parcial `WHERE revoked_at IS NULL`; em SQLite de teste, validação equivalente na camada de aplicação).
- DEVE existir a tabela `link_audit_logs` (`machine_id`, `actor_user_id`, `action`, `detail` JSON, `created_at`).
- A migração DEVE ser encadeada ao head atual (`f1a2b3c4d5e6`), aditiva e idempotente (guardas via `sa.inspect`), com FKs/constraints atrás de gate `dialect.name == "postgresql"` e backfill criando uma linha `machines` (status `unlinked`, `legacy_user_id` preenchido) para cada usuário legado existente.
- Nada nesta tarefa toca o Qdrant ou dados de memórias.
</requirements>

## Subtarefas
- [x] 1.1 Adicionar as classes `Machine`, `AgentToken` e `LinkAuditLog` em `models.py`, com relações para `User`.
- [x] 1.2 Adicionar as colunas de identidade Google e `user_type` em `User`.
- [x] 1.3 Criar a migração Alembic encadeada ao head `f1a2b3c4d5e6` com guardas de idempotência e gate por dialeto.
- [x] 1.4 Implementar o backfill: `user_type='legacy_host'` para linhas existentes e uma linha `machines` `unlinked` por hostname legado.
- [x] 1.5 Implementar `downgrade()` espelhado (drop na ordem correta, com guardas).
- [x] 1.6 Cobrir modelos e migração com testes (unitários + upgrade/downgrade).

## Detalhes de Implementação
Seguir a seção "Modelos de Dados" e o ADR-004 do TechSpec. Usar `e0f1a2b3c4d5_add_groups_table.py` como exemplar do padrão do repo: `bind = op.get_bind()` + `sa.inspect(bind)` para guardas de existência, FKs somente em PostgreSQL (SQLite dos testes obtém a integridade via `create_all`), backfill com `sa.table`/`op.execute`. `Base.metadata.create_all` do startup deve gerar esquema idêntico ao da migração.

### Arquivos Relevantes
- `openmemory/api/app/models.py` — modelos `User` (linha ~153), novas classes e colunas.
- `openmemory/api/alembic/versions/e0f1a2b3c4d5_add_groups_table.py` — exemplar de migração aditiva/idempotente com backfill.
- `openmemory/api/alembic/versions/f1a2b3c4d5e6_add_token_usage_logs.py` — head atual (`down_revision` da nova revision).

### Arquivos Dependentes
- `openmemory/api/app/utils/db.py` — `get_or_create_user`/`get_user_and_app` devem continuar funcionando com os novos campos (default `legacy_host`).
- `openmemory/api/app/utils/groups.py` — `ensure_user_group` cria `User` legado; não pode quebrar com as novas colunas.
- `openmemory/api/tests/` — fixtures SQLite `StaticPool` + `Base.metadata.create_all` passam a criar as novas tabelas.

### ADRs Relacionados
- [ADR-004: Novas tabelas machines e agent_tokens + colunas em users](../adrs/adr-004.md) — define integralmente o esquema desta tarefa.

## Entregáveis
- Modelos `Machine`, `AgentToken`, `LinkAuditLog` e colunas novas em `User`.
- Migração Alembic com `upgrade`/`downgrade`, backfill de `machines` e `user_type`.
- Testes unitários com cobertura >= 80% **(OBRIGATÓRIO)**
- Testes de integração da migração (upgrade/downgrade) **(OBRIGATÓRIO)**

## Testes
- Testes unitários:
  - [ ] Criar `Machine` com hostname único persiste; hostname duplicado viola a constraint de unicidade.
  - [ ] `AgentToken` persiste apenas `token_hash`/`prefix`; segundo token ativo para o mesmo usuário é rejeitado (índice parcial/validação).
  - [ ] `users.google_sub` aceita NULL (linhas legadas) e rejeita duplicidade quando preenchido.
  - [ ] `LinkAuditLog` grava `action` e `detail` JSON e navega para `Machine`/`User`.
- Testes de integração:
  - [ ] `alembic upgrade head` cria as 3 tabelas e as colunas de `users` (validar via `sa.inspect`), no padrão de `test_postgres_migrations.py`.
  - [ ] Upgrade sobre banco com usuários legados: cada hostname ganha exatamente uma linha `machines` `unlinked` com `legacy_user_id` correto e `user_type='legacy_host'`.
  - [ ] `alembic downgrade -1` remove tabelas/colunas sem erro.
- Meta de cobertura: >= 80%
- Todos os testes devem passar

## Critérios de Sucesso
- Todos os testes passando
- Cobertura de testes >= 80%
- Migração encadeada ao head `f1a2b3c4d5e6`, aditiva, sem alterar nenhuma linha legada de `users.user_id`
- Esquema gerado por `create_all` idêntico ao da migração (ambientes de teste e produção equivalentes)
