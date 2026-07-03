---
status: completed
title: Infra — envs/secrets Google+JWT no compose e mascaramento no Traefik
type: infra
complexity: low
dependencies:
  - task_03
---

# Infra — envs/secrets Google+JWT no compose e mascaramento no Traefik

## Visão Geral
Prepara o deploy: adiciona as variáveis/segredos de OAuth Google e JWT aos serviços do compose (API e UI) seguindo o padrão de secrets do projeto, e garante que o Traefik não exponha o `?token=` das URLs MCP em access logs. Também documenta o passo de migração no roteiro de deploy.

<critical>
- SEMPRE LEIA o PRD e o TechSpec antes de começar
- CONSULTE O TECHSPEC para detalhes de implementação — não duplique aqui
- FOQUE NO "O QUÊ" — descreva o que precisa ser feito, não como
- MINIMIZE CÓDIGO — mostre código só para ilustrar estrutura atual ou áreas problemáticas
- TESTES OBRIGATÓRIOS — toda tarefa DEVE incluir testes nos entregáveis
</critical>

<requirements>
- O bloco `x-api-env` do compose DEVE ganhar `AUTH_JWT_SECRET` e `AUTH_ALLOWED_DOMAIN`; o serviço `openmemory-ui` DEVE ganhar `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `NEXTAUTH_SECRET`, `NEXTAUTH_URL` — segredos via arquivo/secret (padrão `/run/secrets/...` já usado por `AUTH_TOKENS_FILE`), nunca commitados.
- O Traefik (`compose/proxy.yml`) DEVE permanecer sem access log OU, se habilitado, com query strings de `/mcp` mascaradas/dropadas — o `?token=` nunca pode aparecer em log do proxy (hoje não há `--accesslog`; a configuração deve deixar isso explícito e à prova de habilitação acidental).
- `.env.example`/documentação de deploy DEVEM listar as novas variáveis com descrição e o passo manual `alembic upgrade head` (padrão `bootstrap-scale.sh`).
- O deploy DEVE seguir as regras CRITICAL do repo: rebuild somente de `openmemory-mcp`/`openmemory-write-worker`/`openmemory-ui`; nenhum serviço de dados (`mem0_store`, postgres) recriado.
</requirements>

## Subtarefas
- [x] 10.1 Adicionar as envs/secrets da API ao `x-api-env` e as da UI ao serviço `openmemory-ui`.
- [x] 10.2 Revisar `entrypoint.sh` da UI: segredos de servidor (NextAuth) não passam pelo sed de `NEXT_PUBLIC_*` — validar que chegam ao runtime do Next (envs de serviço chegam via environment do compose; documentado no .env.example).
- [x] 10.3 Configurar/comentar o access log do Traefik garantindo ausência de query strings de `/mcp` (+ `--no-access-log` no uvicorn, que também logava a URL completa).
- [x] 10.4 Atualizar `.env.example` e o roteiro de deploy (migração manual + rebuild seletivo).
- [x] 10.5 Validar a stack com testes de parse do compose (padrão `test_docker_stack_backup.py` — Docker indisponível na máquina de dev); smoke de deploy documentado para o host da stack.

## Detalhes de Implementação
Ver "Pontos de Integração" e "Análise de Impacto" do TechSpec e ADRs 002/003. O compose atual define `AUTH_MODE`/`AUTH_TOKENS_FILE` no bloco `x-api-env` (`docker-compose.scale.yml` linhas ~51-53) — seguir esse padrão. O `compose/proxy.yml` não tem access log hoje (flags CLI no `command:`, linhas 11-17); qualquer habilitação futura deve nascer com drop de query.

### Arquivos Relevantes
- `openmemory/docker-compose.scale.yml` — blocos `x-api-env` e serviço `openmemory-ui` (linhas ~223-227).
- `openmemory/compose/proxy.yml` — `command:` do Traefik (linhas 11-17).
- `openmemory/ui/entrypoint.sh` — mecanismo de injeção runtime de envs da UI.
- `openmemory/scripts/bootstrap-scale.sh:103` — passo de migração manual a documentar.

### Arquivos Dependentes
- `openmemory/api/app/routers/auth.py` e `middleware/team_auth.py` — consumidores de `AUTH_JWT_SECRET`/`AUTH_ALLOWED_DOMAIN`.
- `openmemory/ui/middleware.ts` e config NextAuth — consumidores das envs da UI (task_07).

### ADRs Relacionados
- [ADR-002: NextAuth na UI com JWT de sessão emitido pela API](../adrs/adr-002.md) — variáveis exigidas.
- [ADR-003: Token de agente transportado na URL MCP](../adrs/adr-003.md) — mascaramento na cadeia do proxy.

## Entregáveis
- Compose atualizado com envs/secrets de auth (API e UI).
- Traefik garantidamente sem exposição de `?token=` em logs.
- `.env.example` e roteiro de deploy atualizados.
- Testes/validações de configuração **(OBRIGATÓRIO)**

## Testes
- Validações de configuração:
  - [ ] `docker compose -f docker-compose.scale.yml config` resolve sem erro com as novas variáveis definidas e com defaults ausentes.
  - [ ] Container da API enxerga `AUTH_JWT_SECRET`/`AUTH_ALLOWED_DOMAIN`; container da UI enxerga as envs NextAuth (teste de fumaça `docker compose run --rm ... env`).
  - [ ] Com access log do Traefik habilitado em ambiente de teste, requisição `/mcp/...?token=segredo` não registra `segredo` no log do proxy.
- Teste de fumaça de deploy:
  - [ ] Rebuild seletivo (`openmemory-mcp`, `openmemory-ui`) sobe com a stack de dados intacta (`points_count` do Qdrant inalterado).
- Meta de cobertura: >= 80% (sobre scripts/validações automatizáveis)
- Todos os testes devem passar

## Critérios de Sucesso
- Todos os testes/validações passando
- Nenhum segredo commitado no repositório
- `?token=` ausente de qualquer log do proxy
- Roteiro de deploy documenta migração manual e rebuild seletivo (regras CRITICAL respeitadas)
