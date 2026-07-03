---
status: completed
title: Onboarding backend — vínculo máquina→conta, conflito e resolução dinâmica
type: backend
complexity: high
dependencies:
  - task_01
  - task_02
---

# Onboarding backend — vínculo máquina→conta, conflito e resolução dinâmica

## Visão Geral
Implementa a migração do modelo legado: o endpoint de onboarding vincula a máquina informada (e seu usuário legado, se existir) à conta Google, com escolha de grupo, trilha em `link_audit_logs` e bloqueio de conflito. Cria também `identity_links.py`, a resolução dinâmica hostname→pessoa (com cache) que faz as memórias legadas pertencerem ao usuário sem tocar o Qdrant.

<critical>
- SEMPRE LEIA o PRD e o TechSpec antes de começar
- CONSULTE O TECHSPEC para detalhes de implementação — não duplique aqui
- FOQUE NO "O QUÊ" — descreva o que precisa ser feito, não como
- MINIMIZE CÓDIGO — mostre código só para ilustrar estrutura atual ou áreas problemáticas
- TESTES OBRIGATÓRIOS — toda tarefa DEVE incluir testes nos entregáveis
</critical>

<requirements>
- `POST /api/v1/auth/onboarding` DEVE exigir sessão (`method="session"`), receber `{hostname, group_name}` e: (a) vincular a máquina à pessoa (`machines.status='linked'`, `linked_at`, `linked_by`), (b) associar o usuário legado correspondente quando existir, (c) aplicar o grupo escolhido via `get_or_create_group`, (d) retornar `{linked, memories_count}`.
- Máquina já vinculada a OUTRA pessoa DEVE retornar 409, marcar `machines.status='conflict'` e registrar `conflict_detected` em `link_audit_logs` — nunca vincular automaticamente.
- Repetir onboarding da própria máquina DEVE ser idempotente (200, sem duplicar vínculo nem log de conflito).
- Todo vínculo/desvínculo DEVE gerar linha em `link_audit_logs` com ator e timestamp.
- `identity_links.py` DEVE expor resolução hostname→pessoa com cache (padrão de `app/utils/groups.py`: best-effort, nunca derruba a consulta) e invalidação no commit do vínculo.
- NENHUM payload do Qdrant é lido ou modificado por esta tarefa (ADR-005).
</requirements>

## Subtarefas
- [x] 5.1 Adicionar `POST /auth/onboarding` ao router de auth com validações e transação de vínculo.
- [x] 5.2 Implementar a detecção de usuário legado por hostname e o cálculo de `memories_count` (contagem via metadados relacionais/Qdrant count por filtro — sem alterar payloads).
- [x] 5.3 Implementar o estado de conflito (409 + `status='conflict'` + `link_audit_logs`).
- [x] 5.4 Criar `app/utils/identity_links.py` com cache hostname→pessoa e invalidação.
- [x] 5.5 Registrar auditoria de vínculo (`link`/`conflict_detected`) em todas as transições.
- [x] 5.6 Cobrir vínculo, idempotência, conflito e cache com testes.

## Detalhes de Implementação
Ver seções "Endpoints de API" e "Arquitetura do Sistema" do TechSpec e ADRs 004/005. `identity_links.py` replica a estrutura de `app/utils/groups.py` (cache em módulo + invalidate + fallback silencioso). O grupo usa `get_or_create_group` existente (`groups.py:115`). A escolha de grupo no onboarding NÃO altera o grupo do usuário legado — apenas o da pessoa.

### Arquivos Relevantes
- `openmemory/api/app/routers/auth.py` — router criado na task_02; adicionar o endpoint de onboarding.
- `openmemory/api/app/utils/identity_links.py` — novo módulo de resolução dinâmica (criar).
- `openmemory/api/app/utils/groups.py` — exemplar de cache/invalidatação e `get_or_create_group`.
- `openmemory/api/app/models.py` — `Machine`, `LinkAuditLog`, `User` (task_01).

### Arquivos Dependentes
- `openmemory/api/app/routers/memories.py` — leitura/UI resolve autor por hostname (`_author_hostname_from_memory`); consumirá `identity_links` em fases futuras.
- `openmemory/api/app/mcp_server.py` — task_11 usa a resolução para atribuição.
- `openmemory/ui/app/onboarding/` — task_08 consome este endpoint.

### ADRs Relacionados
- [ADR-005: Resolução dinâmica hostname→pessoa](../adrs/adr-005.md) — contrato central desta tarefa.
- [ADR-004: Novas tabelas machines e agent_tokens](../adrs/adr-004.md) — estados de `machines` e `link_audit_logs`.

## Entregáveis
- Endpoint `POST /api/v1/auth/onboarding` com vínculo, grupo, conflito e auditoria.
- Módulo `identity_links.py` com cache e invalidação.
- Testes unitários com cobertura >= 80% **(OBRIGATÓRIO)**
- Testes de integração do fluxo de vínculo **(OBRIGATÓRIO)**

## Testes
- Testes unitários:
  - [ ] Onboarding com hostname legado existente vincula máquina + usuário legado e retorna `memories_count` > 0.
  - [ ] Onboarding com hostname inédito cria `machines` `linked` sem `legacy_user_id` e retorna `memories_count=0`.
  - [ ] Hostname vinculado a outra pessoa retorna 409, `status='conflict'` e linha `conflict_detected` em `link_audit_logs`.
  - [ ] Repetição do onboarding pela mesma pessoa é idempotente (200, um único vínculo/log).
  - [ ] `resolve_person_for_hostname` retorna a pessoa após vínculo e `None` para hostname não vinculado; falha de banco não propaga exceção.
  - [ ] Invalidação: após novo vínculo, o cache reflete a mudança imediatamente.
- Testes de integração:
  - [ ] Fluxo `POST /auth/google` → `POST /auth/onboarding` → `GET /auth/me` retorna máquina e grupo vinculados.
- Meta de cobertura: >= 80%
- Todos os testes devem passar

## Critérios de Sucesso
- Todos os testes passando
- Cobertura de testes >= 80%
- Zero escrita no Qdrant durante o onboarding (verificável nos testes)
- Conflitos nunca resolvidos automaticamente; trilha completa em `link_audit_logs`
