---
status: completed
title: UI — painel de instalação de agentes
type: frontend
complexity: medium
dependencies:
  - task_04
  - task_06
  - task_07
---

# UI — painel de instalação de agentes

## Visão Geral
Cria o painel onde o usuário autenticado gerencia seu token de agente: geração com exibição única e cópia, revogação e regeneração com confirmação, e instruções passo a passo de instalação por cliente MCP (claude-code, cursor, codex) com a URL/comando do provision já incluindo o token.

<critical>
- SEMPRE LEIA o PRD e o TechSpec antes de começar
- CONSULTE O TECHSPEC para detalhes de implementação — não duplique aqui
- FOQUE NO "O QUÊ" — descreva o que precisa ser feito, não como
- MINIMIZE CÓDIGO — mostre código só para ilustrar estrutura atual ou áreas problemáticas
- TESTES OBRIGATÓRIOS — toda tarefa DEVE incluir testes nos entregáveis
</critical>

<requirements>
- O painel DEVE exibir o token em claro APENAS na resposta da geração, com botão de copiar e aviso explícito "você não poderá vê-lo novamente"; depois disso, apenas `prefix` e datas (`GET /agent-token`).
- Revogar e regenerar DEVEM pedir confirmação (AlertDialog) explicando o impacto (agentes com o token antigo param de autenticar) — regeneração = novo POST (o backend revoga o anterior).
- As instruções por cliente DEVEM apresentar o comando/config do `GET /provision` com `?token=` preenchido, com botão de copiar por cliente.
- Estado sem token gerado (404) DEVE mostrar call-to-action de primeira geração.
- Textos em PT-BR; componentes do design system existente; página protegida por sessão.
</requirements>

## Subtarefas
- [x] 9.1 Criar a página do painel (`/settings/install` ou rota equivalente) com os estados: sem token, token recém-gerado (claro visível), token existente (só metadados).
- [x] 9.2 Criar hook `useAgentTokenApi` (gerar/consultar/revogar, padrão `useGroupsApi`).
- [x] 9.3 Implementar regenerar/revogar com AlertDialog de confirmação.
- [x] 9.4 Montar as instruções por cliente com o comando do provision incluindo o token.
- [x] 9.5 Cobrir os estados do painel e o hook com testes.

## Detalhes de Implementação
Ver PRD F3 (painel), "Endpoints de API" do TechSpec e ADR-003. Seguir a composição de `app/settings/page.tsx` (Tabs/Card/AlertDialog/estado local, sem novo slice Redux). O valor em claro do token vive apenas em estado de componente — nunca em Redux/localStorage.

### Arquivos Relevantes
- `openmemory/ui/app/settings/install/page.tsx` — nova página (criar).
- `openmemory/ui/hooks/useAgentTokenApi.ts` — novo hook (criar).
- `openmemory/ui/app/settings/page.tsx` — exemplar de página de settings (Tabs, AlertDialog, toasts).
- `openmemory/ui/lib/mcp-install.ts` (e teste `__tests__/lib/mcp-install`) — lógica existente de instruções MCP a reaproveitar/estender.

### Arquivos Dependentes
- `openmemory/ui/components/Navbar.tsx` — entrada de navegação para o painel.
- `openmemory/ui/app/onboarding/page.tsx` — task_08 redireciona para cá ao concluir.

### ADRs Relacionados
- [ADR-003: Token de agente transportado na URL MCP](../adrs/adr-003.md) — exibição única, cópia e instruções com `?token=`.

## Entregáveis
- Painel de instalação completo com ciclo de vida do token e instruções por cliente.
- Hook `useAgentTokenApi` reutilizável.
- Testes unitários com cobertura >= 80% **(OBRIGATÓRIO)**
- Testes de integração dos estados do painel (axios mockado) **(OBRIGATÓRIO)**

## Testes
- Testes (jest + testing-library, `jest.mock("axios")`):
  - [ ] `GET /agent-token` 404 renderiza o call-to-action de primeira geração.
  - [ ] POST de geração exibe o token em claro uma única vez com o aviso; após navegar/refazer fetch, apenas `prefix` e datas aparecem.
  - [ ] Botão copiar coloca o token/comando no clipboard (mock de `navigator.clipboard`).
  - [ ] Revogar exige confirmação e chama `DELETE /agent-token`; regenerar chama novo `POST` após confirmação.
  - [ ] Instruções por cliente contêm a URL com `?token=` do token recém-gerado (asserção `stringContaining`).
- Meta de cobertura: >= 80%
- Todos os testes devem passar

## Critérios de Sucesso
- Todos os testes passando
- Cobertura de testes >= 80%
- Token em claro nunca persiste fora do estado transitório do componente
- Usuário conclui a configuração de um agente apenas com o conteúdo do painel (sem documentação externa)
