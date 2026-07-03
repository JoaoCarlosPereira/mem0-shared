---
status: completed
title: UI — NextAuth, tela de login, middleware de proteção e Bearer no axios
type: frontend
complexity: high
dependencies:
  - task_02
---

# UI — NextAuth, tela de login, middleware de proteção e Bearer no axios

## Visão Geral
Introduz autenticação real na UI: NextAuth (Auth.js v5) com provider Google, tela de login, `middleware.ts` protegendo todas as rotas e o JWT de sessão da API anexado como Bearer em todas as chamadas axios. O `profileSlice` passa a derivar da sessão em vez do env `NEXT_PUBLIC_USER_ID`.

<critical>
- SEMPRE LEIA o PRD e o TechSpec antes de começar
- CONSULTE O TECHSPEC para detalhes de implementação — não duplique aqui
- FOQUE NO "O QUÊ" — descreva o que precisa ser feito, não como
- MINIMIZE CÓDIGO — mostre código só para ilustrar estrutura atual ou áreas problemáticas
- TESTES OBRIGATÓRIOS — toda tarefa DEVE incluir testes nos entregáveis
</critical>

<requirements>
- NextAuth v5 com provider Google DEVE ser configurado; no callback de sign-in, a UI DEVE chamar `POST /api/v1/auth/google` com o ID token e armazenar o `access_token` da API na sessão NextAuth.
- `middleware.ts` DEVE bloquear toda rota sem sessão, redirecionando para `/login` (exceto `/login`, assets e rotas do próprio NextAuth).
- A tela `/login` DEVE exibir apenas o botão "Entrar com Google" e mensagens de erro específicas (domínio não permitido → mensagem clara do 403 da API).
- O interceptor do axios (`lib/api-client.ts`) DEVE anexar `Authorization: Bearer <access_token>` em todas as chamadas, mantendo o header `x-client-name: openmemory-ui` existente.
- `profileSlice` DEVE ser populado a partir de `GET /auth/me` (nome, e-mail, avatar), removendo a dependência funcional de `NEXT_PUBLIC_USER_ID`.
- Login com `first_login=true` DEVE redirecionar para `/onboarding` (página criada na task_08; nesta tarefa basta o redirect).
- Cabeçalho (Navbar) DEVE exibir nome/avatar e ação de logout.
</requirements>

## Subtarefas
- [x] 7.1 Instalar e configurar NextAuth v5 (provider Google, callbacks, rota `app/api/auth/[...nextauth]`).
- [x] 7.2 Criar `middleware.ts` com a proteção de rotas e exceções.
- [x] 7.3 Criar a página `/login` com botão Google e tratamento de erro de domínio.
- [x] 7.4 Integrar sessão → `POST /auth/google` → `access_token` na sessão e no interceptor axios.
- [x] 7.5 Derivar `profileSlice` de `/auth/me` e exibir nome/avatar/logout na Navbar.
- [x] 7.6 Cobrir middleware, login e interceptor com testes.

## Detalhes de Implementação
Ver seções "Arquitetura do Sistema" (fluxo de login) do TechSpec e ADR-002. Envolver a árvore em `SessionProvider` em `app/providers.tsx` (hoje só Redux). Envs novas: `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `NEXTAUTH_SECRET`, `NEXTAUTH_URL` — atenção ao mecanismo de injeção runtime do `entrypoint.sh` (sed em `NEXT_PUBLIC_*`); segredos de servidor não passam por esse mecanismo. Textos de UI em PT-BR.

### Arquivos Relevantes
- `openmemory/ui/package.json` — adicionar `next-auth@^5` (pnpm).
- `openmemory/ui/app/providers.tsx` e `openmemory/ui/app/layout.tsx` — adicionar SessionProvider.
- `openmemory/ui/middleware.ts` — novo (não existe hoje).
- `openmemory/ui/app/login/page.tsx` — nova página.
- `openmemory/ui/lib/api-client.ts` — interceptor Bearer (hoje só injeta `x-client-name`).
- `openmemory/ui/store/profileSlice.ts:13` — remover dependência de `NEXT_PUBLIC_USER_ID`.
- `openmemory/ui/components/Navbar.tsx` — nome/avatar/logout.

### Arquivos Dependentes
- `openmemory/ui/hooks/*.ts` — hooks de API passam a operar autenticados (sem mudança de assinatura esperada).
- `openmemory/ui/entrypoint.sh` e `openmemory/docker-compose.scale.yml` — task_10 adiciona as envs.

### ADRs Relacionados
- [ADR-002: NextAuth na UI com JWT de sessão emitido pela API](../adrs/adr-002.md) — arquitetura desta tarefa.

## Entregáveis
- Login Google funcional com proteção de todas as rotas da UI.
- Bearer da API anexado em todas as chamadas axios.
- `profileSlice` derivado da sessão real.
- Testes unitários com cobertura >= 80% **(OBRIGATÓRIO)**
- Testes de integração do fluxo de login (mockando NextAuth/axios) **(OBRIGATÓRIO)**

## Testes
- Testes (jest + testing-library, padrão `jest.mock("axios")` do repo):
  - [ ] Acesso a rota protegida sem sessão redireciona para `/login` (teste do matcher/lógica do middleware).
  - [ ] Callback de login com `POST /auth/google` bem-sucedido armazena `access_token` e redireciona: `/` quando `first_login=false`, `/onboarding` quando `true`.
  - [ ] Resposta 403 da API (domínio não permitido) exibe mensagem específica na tela de login.
  - [ ] Interceptor anexa `Authorization: Bearer` e preserva `x-client-name` (asserção com `expect.objectContaining` nos headers).
  - [ ] `profileSlice` popula nome/e-mail/avatar a partir do mock de `/auth/me`.
- Testes de integração:
  - [ ] Fluxo login → sessão → chamada de API autenticada → logout limpa sessão e volta ao `/login`.
- Meta de cobertura: >= 80%
- Todos os testes devem passar

## Critérios de Sucesso
- Todos os testes passando
- Cobertura de testes >= 80%
- Nenhuma rota da UI acessível sem sessão
- `NEXT_PUBLIC_USER_ID` sem uso funcional no fluxo autenticado
