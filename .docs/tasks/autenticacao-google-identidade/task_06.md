---
status: completed
title: Provision com ?token= embutido na URL MCP
type: backend
complexity: low
dependencies:
  - task_04
---

# Provision com ?token= embutido na URL MCP

## Visão Geral
Estende a receita de instalação de agentes (`GET /provision`) para aceitar um token de agente e embuti-lo como `?token=` na URL MCP gerada para cada cliente (claude-code, cursor, codex). Agentes instalados com a nova receita passam a se autenticar como a pessoa dona do token; a receita sem token permanece válida (modo legado).

<critical>
- SEMPRE LEIA o PRD e o TechSpec antes de começar
- CONSULTE O TECHSPEC para detalhes de implementação — não duplique aqui
- FOQUE NO "O QUÊ" — descreva o que precisa ser feito, não como
- MINIMIZE CÓDIGO — mostre código só para ilustrar estrutura atual ou áreas problemáticas
- TESTES OBRIGATÓRIOS — toda tarefa DEVE incluir testes nos entregáveis
</critical>

<requirements>
- `GET /provision` DEVE aceitar o query param opcional `token` e propagá-lo como `?token=` na URL MCP dos três hosts (JSON de claude-code/cursor e TOML do codex), combinando corretamente com o `?group=` existente.
- A receita SEM `token` DEVE permanecer byte-idêntica ao comportamento atual (compatibilidade legada).
- O placeholder `{hostname}` e a semântica do `?group=` (vínculo de equipe na 1ª conexão) NÃO podem mudar.
- O valor do token NÃO pode ser logado pelo endpoint (aplicar o mascaramento da task_03 também aqui).
</requirements>

## Subtarefas
- [x] 6.1 Adicionar o parâmetro `token` ao endpoint e à montagem da URL em `_mcp_config`.
- [x] 6.2 Garantir composição correta de query string (`?token=...&group=...`) nos três formatos de receita.
- [x] 6.3 Atualizar as instruções textuais da receita mencionando o token quando presente.
- [x] 6.4 Cobrir com testes as receitas com e sem token nos três hosts.

## Detalhes de Implementação
Ver seção "Endpoints de API" do TechSpec e ADR-003. A mudança é local a `provision.py` (`_mcp_config`, linhas 62-94, e texto da receita). Testes seguem o padrão de `test_provision.py` existente (router carregado isolado via `importlib`).

### Arquivos Relevantes
- `openmemory/api/app/routers/provision.py` — endpoint e `_mcp_config` a estender.
- `openmemory/api/tests/test_provision.py` — suíte existente a ampliar (exemplar de asserção sobre a receita).

### Arquivos Dependentes
- `openmemory/ui/app/settings/` — task_09 monta o comando de instalação com o token do usuário.
- `openmemory/api/app/middleware/team_auth.py` — o `?token=` embutido será validado pelo middleware (task_03).

### ADRs Relacionados
- [ADR-003: Token de agente transportado na URL MCP](../adrs/adr-003.md) — define o formato `?token=`.

## Entregáveis
- `GET /provision` com suporte a `?token=` nos três hosts.
- Testes unitários com cobertura >= 80% **(OBRIGATÓRIO)**
- Testes de integração da receita gerada **(OBRIGATÓRIO)**

## Testes
- Testes unitários:
  - [ ] `GET /provision?host=claude-code&token=abc` gera URL MCP contendo `?token=abc`; sem `token`, a URL é idêntica à atual.
  - [ ] Com `token` E `group`, a query string contém ambos corretamente separados.
  - [ ] Receita TOML do codex embute o token no campo `url` sem quebrar o parse TOML.
  - [ ] Nenhum log emitido pelo endpoint contém o valor do token.
- Testes de integração:
  - [ ] Receita gerada com token, aplicada a uma chamada MCP simulada, autentica via middleware como `method="agent_token"`.
- Meta de cobertura: >= 80%
- Todos os testes devem passar

## Critérios de Sucesso
- Todos os testes passando
- Cobertura de testes >= 80%
- Receita sem token permanece idêntica à atual (regressão zero para o fluxo legado)
