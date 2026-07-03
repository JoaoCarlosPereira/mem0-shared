---
status: completed
title: Endpoints /auth/google e /auth/me — validação do ID token Google e JWT de sessão
type: backend
complexity: medium
dependencies:
  - task_01
---

# Endpoints /auth/google e /auth/me — validação do ID token Google e JWT de sessão

## Visão Geral
Implementa o núcleo da autenticação de pessoas: a API recebe o ID token do Google enviado pela UI, valida com `google-auth` (assinatura, `aud`, `iss`, `exp` e domínio via claim `hd`), registra/atualiza o usuário `person` (chave = claim `sub`) e emite o JWT de sessão próprio consumido por todas as chamadas seguintes.

<critical>
- SEMPRE LEIA o PRD e o TechSpec antes de começar
- CONSULTE O TECHSPEC para detalhes de implementação — não duplique aqui
- FOQUE NO "O QUÊ" — descreva o que precisa ser feito, não como
- MINIMIZE CÓDIGO — mostre código só para ilustrar estrutura atual ou áreas problemáticas
- TESTES OBRIGATÓRIOS — toda tarefa DEVE incluir testes nos entregáveis
</critical>

<requirements>
- `POST /api/v1/auth/google` DEVE validar o ID token com a biblioteca `google-auth` e recusar com 403 quando o claim `hd` não corresponder a `AUTH_ALLOWED_DOMAIN` (ou quando `hd` estiver ausente — conta não gerenciada).
- O usuário DEVE ser identificado pelo claim `sub` (estável), nunca pelo e-mail; upsert em `users` com `user_type='person'`, `google_sub`, `email`, `display_name`, `avatar_url`.
- A resposta DEVE incluir `access_token` (JWT HS256 assinado com `AUTH_JWT_SECRET`, payload conforme "Modelos de Dados" do TechSpec) e `first_login` (true quando o usuário `person` acabou de ser criado).
- `GET /api/v1/auth/me` DEVE retornar usuário, máquina vinculada e grupo a partir do Bearer, e 401 sem/with JWT inválido.
- O router DEVE seguir o padrão do repo: schemas Pydantic inline, `APIRouter(prefix=..., tags=[...])`, registro em `routers/__init__.py` e `main.py`.
- Novas dependências (`google-auth`, `pyjwt`) DEVEM entrar em `requirements.txt`; segredos lidos de env (`AUTH_JWT_SECRET`, `AUTH_ALLOWED_DOMAIN`, `GOOGLE_CLIENT_ID`), sem valores hardcoded.
</requirements>

## Subtarefas
- [x] 2.1 Criar `routers/auth.py` com `POST /auth/google` (validação + upsert + JWT) e `GET /auth/me`.
- [x] 2.2 Implementar a verificação do ID token isolada em função testável (mockável nos testes).
- [x] 2.3 Implementar emissão e decodificação do JWT de sessão (HS256, TTL alinhado à sessão NextAuth).
- [x] 2.4 Registrar o router e adicionar as dependências em `requirements.txt`.
- [x] 2.5 Cobrir domínio permitido/negado, first_login e JWT expirado com testes.

## Detalhes de Implementação
Ver seções "Endpoints de API" e "Modelos de Dados" do TechSpec e o ADR-002. Estruturar o router no padrão de `routers/groups.py` (schemas inline com `ConfigDict(from_attributes=True)`, helpers `_privados`, `Depends(get_db)`). A função de verificação Google deve ser injetável/mockável para os testes não dependerem de rede.

### Arquivos Relevantes
- `openmemory/api/app/routers/auth.py` — novo router (criar).
- `openmemory/api/app/routers/groups.py` — exemplar do padrão de router/schemas inline.
- `openmemory/api/app/routers/__init__.py` e `openmemory/api/main.py` — registro em dois pontos (padrão do repo).
- `openmemory/api/requirements.txt` — adicionar `google-auth` e `pyjwt`.

### Arquivos Dependentes
- `openmemory/api/app/models.py` — colunas de `users` criadas na task_01.
- `openmemory/api/app/middleware/team_auth.py` — task_03 consumirá a decodificação do JWT desta tarefa.
- `openmemory/ui/lib/api-client.ts` — task_07 anexará o `access_token` emitido aqui.

### ADRs Relacionados
- [ADR-002: NextAuth na UI com JWT de sessão emitido pela API](../adrs/adr-002.md) — define validação, claims e emissão do JWT.

## Entregáveis
- Endpoints `POST /api/v1/auth/google` e `GET /api/v1/auth/me` funcionais.
- Funções reutilizáveis de emissão/validação do JWT de sessão.
- Testes unitários com cobertura >= 80% **(OBRIGATÓRIO)**
- Testes de integração dos endpoints via `TestClient` **(OBRIGATÓRIO)**

## Testes
- Testes unitários:
  - [ ] ID token com `hd` igual a `AUTH_ALLOWED_DOMAIN` cria usuário `person` e retorna `first_login=true`.
  - [ ] Segundo login do mesmo `sub` não cria usuário novo e retorna `first_login=false` (mesmo se o e-mail mudou).
  - [ ] ID token com `hd` divergente ou ausente retorna 403 com mensagem clara.
  - [ ] ID token inválido/expirado (mock do `google-auth` lançando exceção) retorna 401.
  - [ ] JWT emitido decodifica com `sub`, `email`, `name`, `exp`; JWT expirado é rejeitado.
- Testes de integração:
  - [ ] Fluxo `POST /auth/google` → `GET /auth/me` com o Bearer retornado devolve o mesmo usuário (fixture SQLite `StaticPool` + `dependency_overrides[get_db]`).
  - [ ] `GET /auth/me` sem Authorization retorna 401.
- Meta de cobertura: >= 80%
- Todos os testes devem passar

## Critérios de Sucesso
- Todos os testes passando
- Cobertura de testes >= 80%
- Nenhum segredo hardcoded; domínio permitido configurável por env
- `sub` do Google é a única chave de identidade da pessoa (e-mail apenas informativo)
