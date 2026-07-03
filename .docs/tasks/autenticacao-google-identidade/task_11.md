---
status: completed
title: Integração MCP com identidade e testes E2E de regressão
type: backend
complexity: medium
dependencies:
  - task_03
  - task_04
  - task_05
  - task_06
---

# Integração MCP com identidade e testes E2E de regressão

## Visão Geral
Fecha o MVP no lado dos agentes: o servidor MCP passa a consumir a identidade resolvida pelo `AuthMiddleware` (pessoa/máquina/método) para atribuição das operações, mantendo o caminho legado intocado. Valida o conjunto com testes ponta a ponta (token → operação → atribuição) e a regressão completa das suítes MCP existentes.

<critical>
- SEMPRE LEIA o PRD e o TechSpec antes de começar
- CONSULTE O TECHSPEC para detalhes de implementação — não duplique aqui
- FOQUE NO "O QUÊ" — descreva o que precisa ser feito, não como
- MINIMIZE CÓDIGO — mostre código só para ilustrar estrutura atual ou áreas problemáticas
- TESTES OBRIGATÓRIOS — toda tarefa DEVE incluir testes nos entregáveis
</critical>

<requirements>
- Quando `method="agent_token"`, o fluxo MCP DEVE disponibilizar a pessoa autenticada na atribuição (contextvars consumidas por `usage_attribution` e logging estruturado), mantendo o hostname da URL como máquina.
- Divergência entre a máquina vinculada do dono do token e o hostname da URL NÃO bloqueia em Fase 1, mas DEVE ser registrada em log estruturado (insumo para conflitos na Fase 2).
- Quando não há token (`method="legacy"`), o comportamento DEVE ser byte-idêntico ao atual: `ensure_user_registered(hostname)`, atribuição por hostname, `?group=` na 1ª conexão — todas as suítes `test_mcp_*` existentes passam sem alteração.
- O payload gravado no Qdrant NÃO muda nesta tarefa (continua `hostname`; ADR-005) — a identidade da pessoa fica nas trilhas relacionais/logs.
- Os testes E2E DEVEM cobrir o fluxo completo do MVP no backend: login → onboarding → geração de token → provision → chamada MCP autenticada → atribuição correta.
</requirements>

## Subtarefas
- [x] 11.1 Consumir `AuthContext`/contextvars nas rotas MCP (`handle_streamable_http`, `handle_sse`) e no caminho de escrita (`add_memories`).
- [x] 11.2 Propagar a pessoa autenticada para `usage_attribution` (métrica de tokens) e para o logging estruturado.
- [x] 11.3 Registrar em log a divergência máquina-do-token × hostname-da-URL.
- [x] 11.4 Escrever os testes E2E do fluxo completo (com fixture de banco compartilhada).
- [x] 11.5 Rodar e garantir a regressão integral das suítes MCP/auditoria existentes.

## Detalhes de Implementação
Ver "Arquitetura do Sistema" (fluxo do agente) do TechSpec e ADRs 005/006. Pontos de consumo: `mcp_server.py` linhas ~88-148 (`add_memories`/`ensure_user_registered`), ~238-243 (`usage_attribution` em `search_memory`), rotas ~520-644. A identidade adicional é aditiva — não alterar assinaturas de `_record_write_audit`/`record_memory_reads` nesta fase (colunas de pessoa nas trilhas são Fase 2).

### Arquivos Relevantes
- `openmemory/api/app/mcp_server.py` — rotas MCP, `add_memories`, `usage_attribution`.
- `openmemory/api/app/utils/token_usage_wrapper.py` — atribuição de consumo (campo `user_id` hoje = hostname).
- `openmemory/api/app/utils/identity_links.py` — resolução pessoa↔máquina (task_05).
- `openmemory/api/tests/test_mcp_server.py`, `test_mcp_write_enqueue.py`, `test_mcp_read_project.py`, `test_token_usage_*.py` — suítes de regressão obrigatórias.

### Arquivos Dependentes
- `openmemory/api/app/utils/read_audit.py` e `write_audit_logs` — ganharão a dimensão pessoa na Fase 2 (não tocar agora).
- `openmemory/api/app/middleware/rate_limit.py` — continua keyed por `(project, hostname)`; sem mudança.

### ADRs Relacionados
- [ADR-006: Middleware unificado de autenticação](../adrs/adr-006.md) — origem das contextvars consumidas.
- [ADR-005: Resolução dinâmica hostname→pessoa](../adrs/adr-005.md) — payload do Qdrant permanece intocado.

## Entregáveis
- Fluxo MCP com atribuição de pessoa quando autenticado por token.
- Log estruturado de divergência máquina/hostname.
- Suíte E2E do MVP backend.
- Testes unitários com cobertura >= 80% **(OBRIGATÓRIO)**
- Regressão integral das suítes MCP existentes **(OBRIGATÓRIO)**

## Testes
- Testes unitários:
  - [ ] Chamada MCP com token válido: `usage_attribution` registra a pessoa (e não apenas o hostname) e `auth_method="agent_token"` aparece no log estruturado.
  - [ ] Chamada MCP sem token: atribuição idêntica à atual (hostname), `ensure_user_registered` chamado, `?group=` vincula grupo na 1ª conexão.
  - [ ] Token de pessoa cuja máquina vinculada difere do hostname da URL: operação prossegue e o log de divergência é emitido.
  - [ ] Token revogado em chamada MCP: 401 (comportamento do middleware, verificado no contexto MCP).
- Testes de integração (E2E):
  - [ ] Fluxo completo: `POST /auth/google` → `POST /auth/onboarding` → `POST /agent-token` → `GET /provision?token=` → chamada MCP com a URL gerada → atribuição correta de pessoa/máquina/agente.
  - [ ] Suítes `test_mcp_*`, `test_read_audit.py` e `test_token_usage_*` passam sem alteração de expectativas.
- Meta de cobertura: >= 80%
- Todos os testes devem passar

## Critérios de Sucesso
- Todos os testes passando (novos + regressão integral)
- Cobertura de testes >= 80%
- Zero mudança de comportamento para agentes legados (sem token)
- Payload do Qdrant inalterado (verificável nos testes de escrita)
