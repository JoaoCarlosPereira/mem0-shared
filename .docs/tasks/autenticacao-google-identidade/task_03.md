---
status: completed
title: AuthMiddleware unificado (session/agent_token/team/legacy) e mascaramento de token em logs
type: backend
complexity: high
dependencies:
  - task_01
  - task_02
---

# AuthMiddleware unificado (session/agent_token/team/legacy) e mascaramento de token em logs

## Visão Geral
Evolui o `TeamAuthMiddleware` para o `AuthMiddleware` unificado: um único ponto que resolve JWT de sessão (UI), token de agente (`?token=` nas rotas MCP, hash em `agent_tokens` com cache Redis) e tokens de equipe existentes, populando contextvars de identidade. Requisições MCP sem token continuam passando como `legacy` — nada do comportamento atual muda para quem não migrou.

<critical>
- SEMPRE LEIA o PRD e o TechSpec antes de começar
- CONSULTE O TECHSPEC para detalhes de implementação — não duplique aqui
- FOQUE NO "O QUÊ" — descreva o que precisa ser feito, não como
- MINIMIZE CÓDIGO — mostre código só para ilustrar estrutura atual ou áreas problemáticas
- TESTES OBRIGATÓRIOS — toda tarefa DEVE incluir testes nos entregáveis
</critical>

<requirements>
- A extração DEVE seguir a precedência do ADR-006: `?token=` (rotas `/mcp/*`) → `X-API-Key` → `Authorization: Bearer`.
- JWT válido DEVE resolver para `method="session"` (pessoa); token opaco com hash em `agent_tokens` (não revogado) DEVE resolver para `method="agent_token"` (pessoa + máquina da URL); mapa de equipe DEVE continuar resolvendo `method="team"`; ausência de credencial DEVE resolver `method="legacy"` sem bloquear (Fase 1).
- O comportamento atual dos tokens de equipe DEVE ser preservado byte a byte nos 3 modos `AUTH_MODE=off|warn|enforce` (suíte `test_team_auth.py` existente passa sem alteração de expectativa).
- Contextvars novas (`auth_user_var`, `machine_var`, `auth_method_var`) DEVEM seguir o padrão do repo: `ContextVar` no nível de módulo, set com token e `reset` no `finally` (padrão `usage_attribution`).
- O lookup do hash DEVE usar cache Redis (TTL 60 s) com invalidação na revogação; falha de Redis não pode derrubar a requisição (fallback ao banco).
- O parâmetro `?token=` DEVE ser mascarado (`token=***`) em TODO log estruturado/exceção da API antes de qualquer registro; token revogado em rota MCP DEVE retornar erro claro (401) mesmo em modo `warn` para `method="agent_token"` explícito.
</requirements>

## Subtarefas
- [x] 3.1 Refatorar `team_auth.py` para o `AuthMiddleware` com `AuthContext` e resolução em precedência.
- [x] 3.2 Adicionar contextvars de identidade em `logging_context.py` (com exposição no `StructuredContextFilter`).
- [x] 3.3 Implementar lookup de `agent_tokens` por hash com cache Redis e fallback ao banco.
- [x] 3.4 Implementar mascaramento de `?token=` nos logs da API (filtro central de logging).
- [x] 3.5 Ampliar métricas `AUTH_OK_TOTAL`/`AUTH_DENIED_TOTAL` com label `method`.
- [x] 3.6 Garantir regressão zero: suíte `test_team_auth.py` atual passa e é ampliada para os novos métodos.

## Detalhes de Implementação
Ver seção "Interfaces Principais" do TechSpec (dataclass `AuthContext`, `resolve_credential`) e o ADR-006. Replicar o padrão de contextvars de `app/utils/token_usage_wrapper.py` (context manager com `var.set()`/`var.reset(token)` no `finally`) e de `app/utils/logging_context.py` (`team_var`). A validação do JWT reutiliza as funções da task_02. Instrumentação nunca quebra o fluxo (padrão `_record_write_audit`).

### Arquivos Relevantes
- `openmemory/api/app/middleware/team_auth.py` — middleware a evoluir (extração `_extract_token` linhas 69-76, modos, métricas).
- `openmemory/api/app/utils/logging_context.py` — contextvars existentes (`request_id_var`, `team_var`) e `StructuredContextFilter`.
- `openmemory/api/app/utils/token_usage_wrapper.py` — padrão de set/reset de contextvars a replicar.
- `openmemory/api/tests/test_team_auth.py` — suíte de regressão obrigatória e exemplar de teste de middleware (app FastAPI isolado).

### Arquivos Dependentes
- `openmemory/api/main.py:53-64` — ordem de registro de middlewares (AuthMiddleware permanece externo ao CORS; 401 deve incluir headers CORS).
- `openmemory/api/app/mcp_server.py` — task_11 consumirá as contextvars populadas aqui.
- `openmemory/api/app/middleware/rate_limit.py` — convive na cadeia; sem mudança esperada.

### ADRs Relacionados
- [ADR-006: Middleware unificado de autenticação](../adrs/adr-006.md) — desenho integral desta tarefa.
- [ADR-003: Token de agente na URL](../adrs/adr-003.md) — obrigação de mascaramento de `?token=`.

## Entregáveis
- `AuthMiddleware` com resolução dos 4 métodos e contextvars de identidade.
- Cache Redis do lookup de token com invalidação e fallback.
- Mascaramento de `?token=` em logs da API.
- Testes unitários com cobertura >= 80% **(OBRIGATÓRIO)**
- Testes de integração da cadeia de middleware **(OBRIGATÓRIO)**

## Testes
- Testes unitários (app FastAPI isolado, padrão `test_team_auth.py`):
  - [ ] Precedência: request com `?token=` E header Bearer resolve pelo `?token=` em rota `/mcp`.
  - [ ] JWT válido → `method="session"` e `auth_user_var` preenchida; JWT expirado → 401 com headers CORS.
  - [ ] Token de agente válido → `method="agent_token"` com pessoa+máquina; token revogado → 401 mesmo em `warn`.
  - [ ] Token de equipe nos modos `off|warn|enforce` → comportamento idêntico ao atual (suíte existente sem alteração).
  - [ ] Sem credencial em rota MCP → `method="legacy"`, requisição passa.
  - [ ] Redis indisponível (mock) → lookup cai para o banco sem erro para o cliente.
- Testes de integração:
  - [ ] Log capturado durante requisição com `?token=segredo` não contém `segredo` em nenhuma linha.
  - [ ] Revogação de token invalida o cache: requisição seguinte com o mesmo token recebe 401.
- Meta de cobertura: >= 80%
- Todos os testes devem passar

## Critérios de Sucesso
- Todos os testes passando (incluindo `test_team_auth.py` original sem modificação de expectativas)
- Cobertura de testes >= 80%
- Overhead do middleware no hot path MCP ≤ 5 ms p95 (com cache aquecido)
- Nenhuma ocorrência de token em claro em logs da API
