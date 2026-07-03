# TechSpec — Autenticação Google e Identidade Usuário/Máquina/Agente

## Resumo Executivo

A implementação adiciona autenticação em duas camadas sobre a arquitetura existente do OpenMemory, sem quebrar o modelo legado. Na **UI**, NextAuth (Auth.js v5) com provider Google conduz o OAuth e protege rotas via `middleware.ts`; no callback, a UI envia o ID token à API, que o valida com `google-auth` (assinatura, `aud`, `iss`, `exp`, claim `hd` = domínio da empresa) e emite um **JWT de sessão próprio**, anexado como `Bearer` pelo axios (o proxy `/api-proxy` já repassa headers). No **backend**, o `TeamAuthMiddleware` evolui para `AuthMiddleware` unificado, que valida três credenciais: JWT de sessão (REST), **token de agente** (opaco, hash SHA-256 no banco, transportado como `?token=` na URL MCP) e os tokens de equipe atuais — requisições MCP sem token continuam passando como `legacy`. O modelo de dados ganha `machines` e `agent_tokens` (migração Alembic aditiva sobre `f1a2b3c4d5e6`), e as memórias legadas passam a pertencer à pessoa por **resolução dinâmica** hostname→`machines.linked_user_id` em tempo de consulta (mesmo padrão de grupos) — nenhum payload do Qdrant é tocado.

**Trade-off principal:** o token de agente na URL (escolhido por compatibilidade universal com todos os clientes MCP) fica gravado em arquivos de config e potencialmente em logs de acesso — compensado por mascaramento obrigatório de `?token=` em toda a cadeia de logs (API, Traefik, OTel), hash no banco e revogação/regeneração de baixo atrito pela UI.

## Arquitetura do Sistema

### Visão dos Componentes

| Componente | Tipo | Responsabilidade |
|---|---|---|
| `ui/middleware.ts` + NextAuth | novo | OAuth Google, proteção de rotas, sessão da UI |
| `ui/app/login`, `ui/app/onboarding` | novo | Tela de login e assistente de 1º login (máquina + grupo + vínculo) |
| `ui/app/settings/install` (painel de agentes) | novo | Gerar/copiar/revogar token, instruções por cliente MCP |
| `api/app/routers/auth.py` | novo | `/auth/google`, `/auth/me`, onboarding e vínculo de máquina |
| `api/app/routers/agent_tokens.py` | novo | CRUD do token de agente do usuário |
| `api/app/middleware/team_auth.py` → `AuthMiddleware` | modificado | Validação unificada (JWT sessão, token de agente, token de equipe, legacy) |
| `api/app/models.py` + migração Alembic | modificado | Colunas em `users`; tabelas `machines`, `agent_tokens`, `link_audit_logs` |
| `api/app/utils/identity_links.py` | novo | Cache e resolução dinâmica hostname→pessoa (padrão de `groups.py`) |
| `api/app/routers/provision.py` | modificado | Receita com `?token=` na URL MCP quando informado |
| `api/app/mcp_server.py` | modificado | Consome contextvars de identidade (atribuição de pessoa quando autenticado) |

**Fluxo de login:** browser → NextAuth (Google) → `POST /auth/google` (ID token) → validação `google-auth` + upsert de `User(person)` → JWT de sessão → axios injeta `Bearer` → proxy repassa → `AuthMiddleware` resolve pessoa.

**Fluxo do agente:** cliente MCP chama `/mcp/{client}/http/{hostname}?token=…` → `AuthMiddleware` extrai e valida hash (cache Redis) → contextvars `auth_user`, `machine`, `auth_method=agent_token` → MCP handler opera com identidade da pessoa; sem `?token=`, segue como hoje (`legacy`).

## Design de Implementação

### Interfaces Principais

```python
# api/app/models.py (novas entidades — resumo)
class Machine(Base):
    __tablename__ = "machines"
    id = Column(UUID, primary_key=True, default=uuid4)
    hostname = Column(String, unique=True, index=True, nullable=False)
    linked_user_id = Column(UUID, ForeignKey("users.id"), nullable=True)
    legacy_user_id = Column(UUID, ForeignKey("users.id"), nullable=True)
    status = Column(Enum("unlinked", "linked", "conflict", name="machine_status"),
                    default="unlinked", nullable=False)
    linked_at = Column(DateTime)
    linked_by = Column(UUID, ForeignKey("users.id"))

class AgentToken(Base):
    __tablename__ = "agent_tokens"
    id = Column(UUID, primary_key=True, default=uuid4)
    user_id = Column(UUID, ForeignKey("users.id"), nullable=False)
    token_hash = Column(String, index=True, nullable=False)  # SHA-256; nunca em claro
    prefix = Column(String, nullable=False)                  # ex.: omtk_2F9K
    created_at = Column(DateTime, default=utcnow)
    revoked_at = Column(DateTime, nullable=True)             # índice parcial: 1 ativo/usuário
    last_used_at = Column(DateTime, nullable=True)           # Fase 2
```

```python
# api/app/middleware/team_auth.py (contexto resolvido pelo AuthMiddleware)
@dataclass
class AuthContext:
    method: str                     # "session" | "agent_token" | "team" | "legacy"
    user_id: Optional[UUID]         # pessoa autenticada (session/agent_token)
    machine_hostname: Optional[str] # hostname da URL MCP
    team: Optional[str]             # compatibilidade com tokens de equipe

def resolve_credential(request: Request) -> AuthContext:
    """Precedência: ?token= (rotas /mcp) -> X-API-Key -> Authorization: Bearer.
    JWT válido -> session; hash em agent_tokens (cache Redis) -> agent_token;
    mapa de equipe -> team; nada -> legacy (nunca bloqueia em Fase 1)."""
```

### Modelos de Dados

- **`users` (colunas novas):** `google_sub` (único, nullable), `display_name`, `avatar_url`, `user_type` (`person`|`legacy_host`, backfill = `legacy_host`). Linhas legadas intocadas; pessoa usa `user_id = google_sub` como chave técnica (sem colisão com hostnames).
- **`machines`, `agent_tokens`:** conforme interfaces acima.
- **`link_audit_logs`:** `id`, `machine_id`, `actor_user_id`, `action` (`link`|`unlink`|`conflict_detected`|`conflict_resolved`), `detail` (JSON), `created_at` — trilha exigida pelo PRD para todo vínculo.
- **Migração:** revision única `g2b3c4d5e6f7_add_identity_tables` com `down_revision="f1a2b3c4d5e6"`; backfill cria uma linha em `machines` (status `unlinked`, `legacy_user_id` preenchido) para cada `users.user_id` legado existente.
- **JWT de sessão (payload):** `sub` (users.id), `email`, `name`, `exp` (alinhado ao TTL da sessão NextAuth), assinado com `AUTH_JWT_SECRET` (HS256).

### Endpoints de API

| Método | Caminho | Request | Response |
|---|---|---|---|
| POST | `/api/v1/auth/google` | `{id_token}` | `200 {access_token, user, first_login}`; `403` domínio não permitido |
| GET | `/api/v1/auth/me` | Bearer | `200 {user, machine?, group?}`; `401` |
| POST | `/api/v1/auth/onboarding` | `{hostname, group_name}` + Bearer | `200 {linked, memories_count}`; `409` conflito (registra em `link_audit_logs` e `machines.status=conflict`) |
| GET | `/api/v1/agent-token` | Bearer | `200 {prefix, created_at, revoked_at, last_used_at}` ou `404` |
| POST | `/api/v1/agent-token` | Bearer | `201 {token, prefix}` — token em claro **só nesta resposta**; revoga o anterior |
| DELETE | `/api/v1/agent-token` | Bearer | `204` (revogação) |
| GET | `/provision` | `?host=&group=&token=` | receita atual + `?token=` embutido na URL MCP quando informado |

Rotas MCP inalteradas na forma; `?token=` é novo parâmetro opcional validado no middleware.

## Pontos de Integração

- **Google OAuth/OIDC:** NextAuth (UI, fluxo de autorização) e `google-auth` (API, verificação do ID token). Falha do Google impede novos logins; sessões válidas, tokens de agente e modo legado continuam operando (sem retry — erro claro na tela de login).
- **Redis (existente):** cache do hash de token validado (TTL 60 s) e do mapa hostname→pessoa; invalidação no commit de vínculo/revogação.
- **Traefik (existente):** mascaramento do query param `token` no access log (config em `compose/proxy.yml`).

## Análise de Impacto

| Componente | Tipo de Impacto | Descrição e Risco | Ação Necessária |
|---|---|---|---|
| `middleware/team_auth.py` | modificado | Vira `AuthMiddleware`; risco de regressão nos tokens de equipe (médio) | Preservar modos/skip-list; ampliar `test_team_auth.py` |
| `models.py` + Alembic | modificado | Tabelas/colunas novas, aditivas (baixo) | Rodar `alembic upgrade head` no deploy (passo manual do bootstrap) |
| `routers/provision.py` | modificado | URL com `?token=` opcional (baixo) | Manter receita atual válida sem token |
| `mcp_server.py` | modificado | Lê contextvars de identidade; caminho legado intacto (médio) | Testes MCP existentes devem passar sem alteração |
| `ui` (layout, providers, axios, profileSlice) | modificado | Sessão real substitui `NEXT_PUBLIC_USER_ID` (médio) | Interceptor Bearer; `profileSlice` derivado de `/auth/me` |
| `docker-compose.scale.yml` | modificado | Novas envs/secrets Google + JWT (baixo) | `GOOGLE_CLIENT_ID/SECRET`, `NEXTAUTH_SECRET`, `AUTH_JWT_SECRET`, `AUTH_ALLOWED_DOMAIN` |
| Rate limit / CORS | inalterado | Bearer via proxy evita cookie cross-origin | Nenhuma |

## Abordagem de Testes

### Testes Unitários

- **API (pytest, padrão do repo):** `AuthMiddleware` em app FastAPI isolado (padrão `test_team_auth.py`) — precedência de credenciais, JWT expirado/inválido, token revogado, legacy passa, tokens de equipe inalterados nos 3 modos; validação do ID token com mock do `google-auth` (domínio errado → 403; `sub` como chave); geração/revogação de token (hash persistido, claro nunca no banco, índice parcial de 1 ativo); onboarding (vínculo, conflito 409, `link_audit_logs`); resolução dinâmica com cache (fixture SQLite `StaticPool` + `dependency_overrides[get_db]`).
- **UI (jest + testing-library, padrão do repo):** redirect de rota protegida sem sessão; painel de token (exibição única, copiar, revogar, regenerar); wizard de onboarding (sugestão de máquina, conflito).

### Testes de Integração

- `TestClient` ponta a ponta: login simulado → onboarding → geração de token → chamada MCP com `?token=` → atribuição correta nos contextvars; e chamada MCP sem token → comportamento idêntico ao atual (suítes `test_mcp_*` existentes como regressão).
- Verificação de mascaramento: nenhuma ocorrência de token em claro nos logs capturados durante a suíte.

## Sequenciamento de Desenvolvimento

### Ordem de Construção

1. **Migração Alembic + models** (`machines`, `agent_tokens`, `link_audit_logs`, colunas de `users`) — sem dependências.
2. **`/auth/google` + emissão de JWT** (`google-auth`, `pyjwt`) — depende do passo 1.
3. **`AuthMiddleware` unificado** (JWT + hash de agente + equipe + legacy, cache Redis, mascaramento de log) — depende dos passos 1 e 2.
4. **Endpoints `agent-token`** (gerar/consultar/revogar) — depende dos passos 1 e 3.
5. **Onboarding + resolução dinâmica** (`/auth/onboarding`, `identity_links.py`, conflito 409) — depende dos passos 1 e 2.
6. **Provision com `?token=`** — depende do passo 4.
7. **UI: NextAuth + login + `middleware.ts` + interceptor Bearer** — depende do passo 2.
8. **UI: wizard de onboarding** — depende dos passos 5 e 7.
9. **UI: painel de instalação de agentes** — depende dos passos 4, 6 e 7.
10. **Mascaramento no Traefik + envs/secrets no compose** — depende do passo 3.
11. **Integração ponta a ponta + regressão MCP + deploy** (rebuild **somente** `openmemory-mcp`/`openmemory-ui`; `alembic upgrade head` manual) — depende de todos.

### Dependências Técnicas

- Credenciais OAuth no Google Cloud Console (client ID/secret com redirect da UI na LAN) — bloqueante para os passos 2 e 7.
- Novas dependências: `next-auth@^5` (UI); `google-auth`, `pyjwt` (API, `requirements.txt`).
- Deploy respeita as regras CRITICAL do repo: sem rebuild de stack inteira, sem tocar `mem0_store`.

## Monitoramento e Observabilidade

- **Métricas:** `AUTH_OK_TOTAL`/`AUTH_DENIED_TOTAL` ganham label `method` (`session|agent_token|team|legacy`); contadores de logins, vínculos e revogações; cache hit-rate do lookup de token.
- **Logs estruturados:** `auth_method`, `user_id` (pessoa), `machine` ao lado do `team_var`/`request_id` atuais; `?token=` sempre mascarado (`token=***`).
- **Alerta operacional:** taxa de `AUTH_DENIED{method=agent_token}` anômala (token revogado em uso → possível vazamento ou agente desatualizado).

## Considerações Técnicas

### Decisões-Chave

Registradas em ADR (seção final): arquitetura NextAuth+JWT (ADR-002), token na URL (ADR-003), modelo de dados (ADR-004), resolução dinâmica (ADR-005), middleware unificado (ADR-006).

### Riscos Conhecidos

- **Token em URL exposto em logs intermediários** (probabilidade média): mascaramento em API + Traefik + OTel como critério de aceite; rotação de baixo atrito.
- **`Base.metadata.create_all` no startup convive com Alembic:** as tabelas novas nasceriam sem migração em ambiente limpo — a revision Alembic permanece a fonte canônica; validar que `create_all` e a migração geram esquema idêntico.
- **Ordem de middlewares (Starlette):** `AuthMiddleware` continua externo ao CORS; como a sessão usa Bearer (não cookie), o problema CORS+credenciais não se aplica, mas respostas 401 do middleware devem incluir headers CORS para a UI ler o erro.
- **TTLs dessincronizados** entre sessão NextAuth e JWT da API: alinhar expiração e renovar o JWT no callback de refresh do NextAuth.

## Registros de Decisão de Arquitetura

- [ADR-001: Entrega incremental em 3 fases com convivência com o legado](adrs/adr-001.md) — decisão de produto (PRD).
- [ADR-002: NextAuth na UI com JWT de sessão emitido pela API](adrs/adr-002.md) — OAuth na UI, validação e sessão na API via Bearer.
- [ADR-003: Token de agente transportado na URL MCP](adrs/adr-003.md) — `?token=` universal, com mascaramento obrigatório em logs.
- [ADR-004: Novas tabelas `machines` e `agent_tokens` + colunas em `users`](adrs/adr-004.md) — os 3 conceitos do PRD modelados de forma aditiva.
- [ADR-005: Resolução dinâmica hostname→pessoa](adrs/adr-005.md) — payloads do Qdrant intocados; padrão de grupos reaproveitado.
- [ADR-006: Middleware unificado de autenticação](adrs/adr-006.md) — `TeamAuthMiddleware` evolui preservando modos, métricas e legado.
- [ADR-007: Login Google via Device Flow](adrs/adr-007.md) — sem URL de redirect (UI em IP interno/HTTP); mesma validação de domínio do ADR-002; credencial tipo "TVs e dispositivos de entrada limitada".
- [ADR-008: Token de agente imutável e permanentemente exibível](adrs/adr-008.md) — get-or-create idempotente, valor recuperável (`token_value`), sem rotação/revogação via API (válvula administrativa no banco); supersede o show-once dos ADRs 003/004.
