---
status: completed
title: Endpoints do token de agente — gerar, consultar e revogar
type: backend
complexity: medium
dependencies:
  - task_01
  - task_03
---

# Endpoints do token de agente — gerar, consultar e revogar

## Visão Geral
Expõe o ciclo de vida do token de agente do usuário autenticado: geração (com exibição única do valor em claro), consulta de metadados (prefixo, datas) e revogação. É a credencial que os agentes MCP usarão via `?token=` e que o painel da UI (task_09) consome.

<critical>
- SEMPRE LEIA o PRD e o TechSpec antes de começar
- CONSULTE O TECHSPEC para detalhes de implementação — não duplique aqui
- FOQUE NO "O QUÊ" — descreva o que precisa ser feito, não como
- MINIMIZE CÓDIGO — mostre código só para ilustrar estrutura atual ou áreas problemáticas
- TESTES OBRIGATÓRIOS — toda tarefa DEVE incluir testes nos entregáveis
</critical>

<requirements>
- Todos os endpoints DEVEM exigir `method="session"` (JWT da UI) — token de agente ou equipe não gerencia tokens.
- `POST /api/v1/agent-token` DEVE gerar valor imprevisível (CSPRNG, ex.: `secrets.token_urlsafe`), com prefixo identificável (`omtk_...`), persistir SOMENTE o SHA-256 + prefixo, revogar o token ativo anterior na mesma transação e retornar o valor em claro apenas nesta resposta (201).
- `GET /api/v1/agent-token` DEVE retornar apenas metadados (`prefix`, `created_at`, `revoked_at`, `last_used_at`) ou 404 quando o usuário nunca gerou token.
- `DELETE /api/v1/agent-token` DEVE marcar `revoked_at` (204) e invalidar o cache Redis do hash (integração com task_03).
- A regra "1 token ativo por usuário" DEVE ser preservada em concorrência (transação + índice parcial da task_01).
- O valor em claro NUNCA pode aparecer em logs, respostas de erro ou no banco.
</requirements>

## Subtarefas
- [x] 4.1 Criar `routers/agent_tokens.py` com os três endpoints e schemas inline.
- [x] 4.2 Implementar geração segura (CSPRNG + prefixo + SHA-256) como helper reutilizável.
- [x] 4.3 Implementar revogação com invalidação do cache de validação (task_03).
- [x] 4.4 Registrar o router em `routers/__init__.py` e `main.py`.
- [x] 4.5 Cobrir geração/rotação/revogação e exclusividade de token ativo com testes.

## Detalhes de Implementação
Ver seções "Endpoints de API" e "Interfaces Principais" do TechSpec (modelo `AgentToken`) e ADRs 003/004. Router no padrão de `routers/groups.py`. A identidade do chamador vem das contextvars/`AuthContext` populadas pelo `AuthMiddleware` (task_03) — não reimplementar validação de JWT aqui.

### Arquivos Relevantes
- `openmemory/api/app/routers/agent_tokens.py` — novo router (criar).
- `openmemory/api/app/models.py` — modelo `AgentToken` (task_01).
- `openmemory/api/app/middleware/team_auth.py` — fonte da identidade (`AuthContext`) e do cache a invalidar.
- `openmemory/api/app/routers/__init__.py`, `openmemory/api/main.py` — registro do router.

### Arquivos Dependentes
- `openmemory/api/app/routers/provision.py` — task_06 embute o token gerado aqui na URL MCP.
- `openmemory/ui/app/settings/` — task_09 consome estes endpoints no painel.

### ADRs Relacionados
- [ADR-004: Novas tabelas machines e agent_tokens](../adrs/adr-004.md) — esquema e regra de 1 token ativo.
- [ADR-003: Token de agente na URL](../adrs/adr-003.md) — requisitos de sigilo e revogação de baixo atrito.

## Entregáveis
- Endpoints `POST`/`GET`/`DELETE /api/v1/agent-token` funcionais.
- Helper de geração segura de token reutilizável.
- Testes unitários com cobertura >= 80% **(OBRIGATÓRIO)**
- Testes de integração do ciclo de vida completo **(OBRIGATÓRIO)**

## Testes
- Testes unitários:
  - [ ] `POST` sem token prévio retorna 201 com `token` em claro iniciando pelo `prefix` retornado; banco contém apenas o hash.
  - [ ] `POST` com token ativo existente revoga o anterior (`revoked_at` preenchido) e cria um novo — nunca dois ativos.
  - [ ] `GET` sem token gerado retorna 404; com token retorna metadados SEM o valor em claro.
  - [ ] `DELETE` marca `revoked_at` e retorna 204; `DELETE` sem token ativo retorna 404.
  - [ ] Chamada autenticada com `method="agent_token"` (não sessão) recebe 403.
- Testes de integração:
  - [ ] Ciclo completo: gerar → validar via middleware (`?token=`) → revogar → mesma validação falha com 401 (cache invalidado).
- Meta de cobertura: >= 80%
- Todos os testes devem passar

## Critérios de Sucesso
- Todos os testes passando
- Cobertura de testes >= 80%
- Token em claro presente exclusivamente na resposta 201 (verificado em logs e banco)
- Regra de 1 token ativo por usuário mantida sob chamadas concorrentes
