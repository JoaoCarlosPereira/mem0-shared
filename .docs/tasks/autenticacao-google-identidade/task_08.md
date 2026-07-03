---
status: completed
title: UI — wizard de onboarding de primeiro login
type: frontend
complexity: medium
dependencies:
  - task_05
  - task_07
---

# UI — wizard de onboarding de primeiro login

## Visão Geral
Cria o assistente exibido no primeiro login: coleta o nome da máquina atual (com sugestão quando detectável), a escolha do grupo/equipe e confirma o vínculo com o usuário legado ("Encontramos N memórias associadas a esta máquina"). Conclui direcionando ao painel de instalação de agentes.

<critical>
- SEMPRE LEIA o PRD e o TechSpec antes de começar
- CONSULTE O TECHSPEC para detalhes de implementação — não duplique aqui
- FOQUE NO "O QUÊ" — descreva o que precisa ser feito, não como
- MINIMIZE CÓDIGO — mostre código só para ilustrar estrutura atual ou áreas problemáticas
- TESTES OBRIGATÓRIOS — toda tarefa DEVE incluir testes nos entregáveis
</critical>

<requirements>
- A página `/onboarding` DEVE ser acessível apenas autenticado e ser oferecida quando `first_login=true` (redirect da task_07); usuário já vinculado que acessar diretamente DEVE ser levado ao dashboard.
- O formulário DEVE coletar hostname (input com sugestão) e grupo (lista de `GET /admin/groups` + opção de criar novo), enviando `POST /api/v1/auth/onboarding`.
- Resposta de sucesso DEVE exibir o resumo do vínculo (contagem de memórias herdadas) e link/redirect para o painel de instalação (task_09).
- Resposta 409 (conflito) DEVE exibir mensagem clara de que a máquina pertence a outra conta e que o caso ficou registrado para tratamento — sem opção de forçar o vínculo.
- Textos em PT-BR e componentes do design system existente (Card, Button, Tabs/AlertDialog conforme padrão de `app/settings/page.tsx`).
</requirements>

## Subtarefas
- [x] 8.1 Criar a página `/onboarding` com as etapas máquina → grupo → confirmação.
- [x] 8.2 Criar hook `useOnboardingApi` (padrão `useGroupsApi`: `useCallback` + axios + `getApiUrl()`).
- [x] 8.3 Integrar a lista de grupos existente e a criação de grupo novo.
- [x] 8.4 Tratar sucesso (resumo + redirect) e conflito 409 (mensagem terminal).
- [x] 8.5 Cobrir o wizard e o hook com testes.

## Detalhes de Implementação
Ver seção "Experiência do Usuário" do PRD (fluxo de primeiro contato) e "Endpoints de API" do TechSpec. Estado local no componente (padrão da página de grupos — sem novo slice Redux). A sugestão de hostname pode usar heurística simples (sem API nova); não bloquear o envio manual.

### Arquivos Relevantes
- `openmemory/ui/app/onboarding/page.tsx` — nova página (criar).
- `openmemory/ui/hooks/useOnboardingApi.ts` — novo hook (criar).
- `openmemory/ui/hooks/useGroupsApi.ts` — exemplar de hook puro e fonte da lista de grupos.
- `openmemory/ui/app/settings/page.tsx` — exemplar de composição Card/Tabs/AlertDialog/estado controlado.

### Arquivos Dependentes
- `openmemory/ui/middleware.ts` — task_07; `/onboarding` entra nas rotas protegidas.
- `openmemory/ui/app/settings/install/` — task_09 é o destino do redirect final.

### ADRs Relacionados
- [ADR-004: Novas tabelas machines e agent_tokens](../adrs/adr-004.md) — estados de vínculo refletidos na UX (linked/conflict).

## Entregáveis
- Página `/onboarding` completa com os três passos e tratamento de conflito.
- Hook `useOnboardingApi` reutilizável.
- Testes unitários com cobertura >= 80% **(OBRIGATÓRIO)**
- Testes de integração do fluxo do wizard (axios mockado) **(OBRIGATÓRIO)**

## Testes
- Testes (jest + testing-library, `jest.mock("axios")`):
  - [ ] Submissão com hostname legado exibe resumo com `memories_count` retornado pelo mock.
  - [ ] Resposta 409 exibe a mensagem de conflito e não oferece retry de vínculo forçado.
  - [ ] Lista de grupos renderiza opções do mock de `/admin/groups`; criação de grupo novo dispara o POST correto.
  - [ ] Hook chama `POST /api/v1/auth/onboarding` com `{hostname, group_name}` (asserção `toHaveBeenCalledWith`).
  - [ ] Usuário sem `first_login` acessando `/onboarding` é redirecionado ao dashboard.
- Meta de cobertura: >= 80%
- Todos os testes devem passar

## Critérios de Sucesso
- Todos os testes passando
- Cobertura de testes >= 80%
- Fluxo de primeiro login completo em uma única visita (login → onboarding → painel de instalação)
- Conflito nunca resolve vínculo automaticamente pela UI
