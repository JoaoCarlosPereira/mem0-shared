# TechSpec — Prompts de Coluna Configuráveis para Agentes Kanban

**Workspace:** kanban-column-prompts  
**Status:** rascunho  
**Data:** 2026-08-09  
**Projeto:** sharemem  
**Baseado no PRD:** document_id `8ec8e3a7-c5d2-4e3b-82a8-630b5da007e2` (v2)

---

## Resumo Executivo

Esta feature adiciona **prompts personalizáveis por coluna** do pipeline Kanban que substituem o `do_now` fixo (`COLUMN_GUIDE` em `kanban_pipeline.py`) quando configurados. Os prompts são armazenados em uma nova tabela PostgreSQL (`kanban_column_prompts`), acessíveis via REST API no prefixo `/api/v1/specs/`, editáveis por qualquer usuário com acesso ao painel admin em uma nova aba (`/admin/kanban-prompts`), e injetados no bloco `kanban.column_prompt` da resposta MCP de `update_task_status`.

**Decisão arquitetural principal:** cache em memória com TTL configurável (10 minutos) no `mcp_server.py`. A API é single-instance no deploy atual, o que elimina a necessidade de invalidação distribuída. O `COLUMN_GUIDE` em `kanban_pipeline.py` permanece inalterado como fallback.

**Trade-off principal:** cache em memória vs. leitura direta do banco. O cache com TTL de 10 minutos sacrifica consistência imediata para reduzir carga no PostgreSQL, com staleness aceitável dado o contexto de uso (admin edita, espera até 10 min para refletir em cards já movimentados).

---

## Arquitetura do Sistema

### Componentes Principais

```
┌─────────────────────────────────────────────────────────────┐
│  Admin UI (Next.js)                                         │
│  /admin/kanban-prompts                                       │
│  ├─ Aba na sidebar (AdminSidebar.tsx)                       │
│  └─ Grade inline de edição (KanbanPromptsPage.tsx)          │
└──────────────────┬──────────────────────────────────────────┘
                   │ PUT /api/v1/specs/kanban-prompts/:status
                   │ GET /api/v1/specs/kanban-prompts
                   ▼
┌─────────────────────────────────────────────────────────────┐
│  API (FastAPI)                                              │
│  openmemory/api/app/routers/specs.py                        │
│  ├─ Novos endpoints GET/PUT /kanban-prompts[/:status]       │
│  └─ Pydantic schemas KanbanPromptRead / KanbanPromptUpdate  │
└──────────────────┬──────────────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────────────┐
│  mcp_server.py                                              │
│  ├─ Cache dict: {column_status: {prompt, is_enabled}}      │
│  ├─ load_prompts_cache(): carrega do banco no boot         │
│  └─ enrich_status_payload(): injeta column_prompt          │
└──────────────────┬──────────────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────────────┐
│  PostgreSQL                                                 │
│  kanban_column_prompts                                      │
│  ├─ column_status (PK, VARCHAR(100))                        │
│  ├─ prompt (TEXT)                                           │
│  ├─ is_enabled (BOOLEAN, DEFAULT TRUE)                      │
│  ├─ updated_at (TIMESTAMPTZ, NOW())                         │
│  └─ updated_by (VARCHAR(255))                               │
└─────────────────────────────────────────────────────────────┘
```

### Fluxo de Dados

1. **Admin edita prompt:** `PUT /api/v1/specs/kanban-prompts/:status` → persiste no DB → invalida cache.
2. **Agente movimenta card:** `update_task_status` → `enrich_status_payload` lê do cache → injeta `kanban.column_prompt` no JSON de resposta.
3. **Fallback:** se `column_prompt` é `null` ou prompt desativado → `kanban.do_now` permanece com o valor fixo de `COLUMN_GUIDE`.

### Interações com Sistemas Externos

- **Nenhum sistema externo** é modificado ou integrado. Esta é uma feature additive dentro do OpenMemory.
- O backup existente (`pg_dump`) já cobre a tabela nova automaticamente.
- O `install.py --update` já executa Alembic migrations, garantindo que a tabela seja criada em upgrades.

---

## Design de Implementação

### Interfaces Principais

#### 1. Pydantic Schemas para Prompts

Local: `openmemory/api/app/routers/specs.py` (junto com outros schemas existentes).

```python
class KanbanPromptUpdate(BaseModel):
    prompt: Optional[str] = None
    is_enabled: Optional[bool] = None

class KanbanPromptRead(BaseModel):
    column_status: str
    label: str
    prompt: Optional[str] = None
    is_enabled: bool
    updated_at: Optional[datetime] = None
    updated_by: Optional[str] = None
```

#### 2. Cache Manager em `mcp_server.py`

Local: `openmemory/api/app/mcp_server.py`

```python
# Global state
_kanban_prompts_cache: dict[str, dict] = {}
_kanban_prompts_cache_loaded: datetime | None = None
_KANBAN_PROMPTS_TTL_SECONDS = 600  # 10 minutos

def _kanban_prompts_cache_expired() -> bool:
    if _kanban_prompts_cache_loaded is None:
        return True
    return (datetime.utcnow() - _kanban_prompts_cache_loaded).total_seconds() > _KANBAN_PROMPTS_TTL_SECONDS

def _load_kanban_prompts_cache(db: Session) -> None:
    rows = db.query(KanbanColumnPrompt).all()
    _kanban_prompts_cache.clear()
    for r in rows:
        _kanban_prompts_cache[r.column_status] = {
            "prompt": r.prompt,
            "is_enabled": r.is_enabled,
        }
    _kanban_prompts_cache_loaded = datetime.utcnow()
```

#### 3. Injeção no Payload MCP

A função `enrich_status_payload` em `kanban_pipeline.py` será estendida (não substituída) para incluir `column_prompt`:

```python
def enrich_status_payload(payload: dict[str, Any], status: str, db: Session | None = None) -> dict[str, Any]:
    out = dict(payload)
    kanban_info = guide_for(status)
    
    # Injeta column_prompt do cache (se disponível e habilitado)
    prompt_data = _kanban_prompts_cache.get(status)
    if prompt_data and prompt_data.get("is_enabled") and prompt_data.get("prompt"):
        kanban_info["column_prompt"] = prompt_data["prompt"]
    else:
        kanban_info["column_prompt"] = None
    
    out["kanban"] = kanban_info
    return out
```

**Nota:** O `db` será opcional para compatibilidade com chamadas existentes de `mcp_server.py`. O cache é lido em vez do banco para manter a compatibilidade.

### Modelos de Dados

#### Nova Tabela: `kanban_column_prompts`

| Coluna | Tipo | Restrição | Descrição |
|--------|------|-----------|-----------|
| `column_status` | `VARCHAR(100)` | PK, NOT NULL | Status do pipeline (`tasks`, `em_andamento`, etc.) |
| `prompt` | `TEXT` | NOT NULL | Texto livre do prompt (pode ser vazio via `CHECK (length(prompt) <= 5000)`) |
| `is_enabled` | `BOOLEAN` | NOT NULL, DEFAULT `TRUE` | Se o prompt está ativo |
| `updated_at` | `TIMESTAMPTZ` | NOT NULL, DEFAULT `NOW()` | Última atualização |
| `updated_by` | `VARCHAR(255)` | NULL | Identificador do último editor (opcional) |

**Comentário:** `Prompts de especificação por coluna do pipeline Kanban`

**Constraint adicional (nova decisão):** `CHECK (length(prompt) <= 5000)` para prevenir prompts excessivamente longos que confundam o agente.

#### Migration Alembic

Arquivo: `openmemory/api/alembic/versions/o0d1e2f3g4h5_add_kanban_column_prompts.py`

- Já criada (referência: conversation).
- Usa `ON CONFLICT DO UPDATE WHERE kanban_column_prompts.prompt IS NULL` para seed apenas onde não existe prompt (não sobrescreve customizações).
- `down_revision = "n9c0d1e2f3g4"` (ajustar para o último revision atual).

### Endpoints de API

Local: `openmemory/api/app/routers/specs.py`

| Método | Caminho | Descrição | Auth |
|--------|---------|-----------|------|
| `GET` | `/kanban-prompts` | Retorna todos os prompts (lista ordenada por `column_status`) | Admin panel auth |
| `GET` | `/kanban-prompts/{status}` | Retorna prompt de uma coluna específica | Admin panel auth |
| `PUT` | `/kanban-prompts/{status}` | Atualiza prompt (`prompt`, `is_enabled`) | Admin panel auth |
| `POST` | `/kanban-prompts/init` | Seed inicial para todos os status do pipeline | Admin panel auth |

#### Detalhes do `PUT /kanban-prompts/{status}`

**Request body:**

```json
{
  "prompt": "Texto livre do prompt (até 5000 chars)",
  "is_enabled": true
}
```

**Response 200:**

```json
{
  "column_status": "em_andamento",
  "label": "Em andamento",
  "prompt": "Texto livre do prompt",
  "is_enabled": true,
  "updated_at": "2026-08-09T00:00:00Z",
  "updated_by": "admin-user"
}
```

**Validações:**

- `column_status` deve ser um valor válido do `TaskCardStatus` enum.
- Se `prompt` for fornecido, máximo 5000 caracteres.
- Se `prompt` for `null` ou vazio string, `is_enabled` é automaticamente `false`.

**Ação pós-save:** Invalida o cache em memória (`_kanban_prompts_cache.clear()`).

### Modelo do Banco de Dados (SQL)

```sql
CREATE TABLE kanban_column_prompts (
    column_status VARCHAR(100) PRIMARY KEY,
    prompt TEXT NOT NULL,
    is_enabled BOOLEAN NOT NULL DEFAULT TRUE,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_by VARCHAR(255),
    CONSTRAINT chk_prompt_length CHECK (LENGTH(prompt) <= 5000)
);

COMMENT ON TABLE kanban_column_prompts IS 'Prompts de especificação por coluna do pipeline Kanban';
```

---

## Pontos de Integração

### 1. `kanban_pipeline.py` — `enrich_status_payload`

- **Modificação:** adicionar parâmetro opcional `db` e lógica de injeção de `column_prompt`.
- **Compatibilidade:** chamadas existentes sem `db` continuam funcionando (cache lido global).
- **Arquivo:** `openmemory/api/app/utils/kanban_pipeline.py`

### 2. `mcp_server.py` — Tools MCP

Cinco ferramentas usam `enrich_status_payload`:

| Ferramenta | Linha aproximada |
|------------|------------------|
| `create_task` | ~1360 |
| `claim_task` | ~1394 |
| `release_task` | ~1449 |
| `update_task_status` | ~1521 |
| `get_task` | ~1630 |

**Ação:** nenhuma mudança de assinatura é necessária. O cache é lido como state global, não via parâmetro.

### 3. Admin UI — Sidebar e Rotas

- **Sidebar:** `openmemory/ui/components/admin/AdminSidebar.tsx` — adicionar item ao `NAV_ITEMS`.
- **Rota:** `openmemory/ui/app/admin/kanban-prompts/page.tsx` — nova página do Next.js.

---

## Análise de Impacto

| Componente | Tipo de Impacto | Descrição e Risco | Ação Necessária |
|------------|-----------------|-------------------|-----------------|
| `kanban_pipeline.py` | Modificado | `enrich_status_payload` ganha lógica de `column_prompt`. Risco baixo — additive, `COLUMN_GUIDE` intacto. | Estender função com parâmetro opcional, injetar `column_prompt`. |
| `mcp_server.py` | Modificado | Novo state global (`_kanban_prompts_cache`), nova função de load/invalidation. Risco baixo — isolated, não afeta outras tools. | Adicionar cache e funções auxiliares. |
| `specs.py` | Modificado | 4 novos endpoints REST. Risco baixo — additive, prefixo existente `/api/v1/specs/`. | Adicionar endpoints, schemas, lógica de persistência. |
| `AdminSidebar.tsx` | Modificado | Novo item de menu. Risco nulo — additive, sem mudança de comportamento existente. | Adicionar entrada em `NAV_ITEMS`. |
| `admin/kanban-prompts/page.tsx` | Novo | Página admin com grade de edição inline. Risco baixo — nova rota, sem impacto em outras páginas. | Criar componente React com textarea + toggle + botão salvar. |
| PostgreSQL | Modificado | Nova tabela `kanban_column_prompts`. Risco nulo — additive, migration Alembic. | Migration (já existe). |
| Backup (`pg_dump`) | Não modificado | Já captura todas as tabelas PostgreSQL. Risco nulo. | Nenhuma ação. |
| `install.py` | Modificado | Mensagem pós-update informando nova aba. Risco nulo — apenas `print()`. | Verificar existência da tabela e exibir mensagem. |
| Testes (pytest) | Novo | Testes unitários para novos endpoints e cache. Risco nulo. | Adicionar `tests/test_kanban_prompts.py`. |

---

## Abordagem de Testes

### Testes Unitários

**Arquivo:** `openmemory/api/tests/test_kanban_prompts.py`

**Cobertura:**

1. **Endpoints REST:**
   - `GET /kanban-prompts` retorna todos os prompts com labels corretos.
   - `GET /kanban-prompts/{status}` retorna prompt correto ou 404 para status inválido.
   - `PUT /kanban-prompts/{status}` atualiza prompt, valida limite de 5000 caracteres, atualiza cache.
   - `PUT /kanban-prompts/{status}` com prompt vazio → `is_enabled` = `false`.
   - `POST /kanban-prompts/init` seed apenas para status do pipeline (`TaskCardStatus`).

2. **Cache em memória:**
   - `_kanban_prompts_cache_expired()` retorna `True` se nunca carregado.
   - `_kanban_prompts_cache_expired()` retorna `False` dentro de 10 minutos.
   - `_kanban_prompts_cache_expired()` retorna `True` após 10 minutos.
   - `PUT` invalida cache (clear).

3. **Injeção no payload:**
   - `enrich_status_payload` com prompt habilitado → `kanban.column_prompt` contêm o texto.
   - `enrich_status_payload` com prompt desabilitado → `kanban.column_prompt` é `null`.
   - `enrich_status_payload` com prompt vazio → `kanban.column_prompt` é `null`.

### Testes de Integração

1. **Pipeline completo:** seed → PUT → GET verifica consistência.
2. **Cache TTL:** simular passage de tempo (mock `datetime.utcnow`) para verificar invalidação.
3. **Migração:** verificar que `o0d1e2f3g4h5` cria tabela e seed corretamente via `alembic upgrade head`.

---

## Sequenciamento de Desenvolvimento

### Ordem de Construção

1. **Tabela + Migration** — `kanban_column_prompts` + seed via Alembic. Sem dependências.
2. **Endpoints REST** — GET/PUT em `specs.py`. Depende apenas do passo 1 (tabela existe).
3. **Cache em `mcp_server.py`** — `_load_kanban_prompts_cache`, `_kanban_prompts_cache_expired`. Depende do passo 2 (endpoints populam cache).
4. **Injeção em `kanban_pipeline.py`** — `enrich_status_payload` com `column_prompt`. Depende do passo 3 (cache disponível).
5. **Admin UI** — Sidebar + página `/admin/kanban-prompts`. Depende do passo 2 (endpoints REST existem).
6. **Testes unitários** — Cobertura para todos os componentes acima. Sem dependências (mockable).
7. **Mensagem em `install.py`** — Verifica existência da tabela e imprime mensagem. Sem dependências.

### Dependências Técnicas

- **Nenhuma dependência bloqueante externa.** Tudo é additive dentro do OpenMemory.
- **Alembic:** migração existente precisa do `down_revision` correto (ajustar para o último revision atual do chain).
- **Docker:** `install.py --update` executa `alembic upgrade head` automaticamente.

---

## Monitoramento e Observabilidade

### Métricas

- **Nenhuma métrica nova necessária no MVP.** A feature é simples o suficiente para ser observada via logs e comportamento.

### Logs

- **Erro no cache:** log `WARNING` se `_load_kanban_prompts_cache` falhar (DB indisponível).
- **PUT error:** logs de erro já existentes no FastAPI (409, 422, etc.).
- **Seed migration:** log de info se o seed injetar novas linhas (não overwrite).

### Campos Estruturados

- `updated_by` na tabela permite auditoria básica de quem editou cada prompt.

---

## Considerações Técnicas

### Decisões-Chave

1. **Cache com TTL de 10 minutos.**
   - **Decisão:** cache em memória com TTL de 10 minutos (`_KANBAN_PROMPTS_TTL_SECONDS = 600`).
   - **Justificativa:** single-instance no deploy atual; TTL reduz carga no banco sem staleness crítico.
   - **Trade-offs:**staleness até 10 minutos; se multi-instância futura, requer broadcast de invalidação.
   - **Alternativas rejeitadas:**
     - Sem cache (leitura direta): mais consistente, mas SELECT extra a cada `update_task_status`.
     - Invalidação imediata: zero staleness, mas risco de race condition entre PUT e leitura.

2. **Sem validação de sanitização no texto livre.**
   - **Decisão:** prompts são texto livre, sem sanitização ou escape.
   - **Justificativa:** o admin é o único editor; o texto é injetado como dado JSON no MCP, não como HTML.
   - **Trade-offs:** admin pode escrever qualquer texto; sem proteção contra prompts mal-formados.
   - **Alternativas rejeitadas:**
     - Sanitização HTML: desnecessária (MCP é JSON, não HTML).
     - Validação de estrutura: vai contra requisito de "texto livre" do PRD.

3. **Sem botão "Reset para padrão".**
   - **Decisão:** não há restauração automática para o valor seedado.
   - **Justificativa:** se o admin quer restaurar, pode reescrever manualmente; complexidade adicional não justificada.
   - **Trade-offs:** admin perde prompt customizado se quiser "voltar ao padrão" — deve lembrar ou copiar de `COLUMN_GUIDE`.
   - **Alternativas rejeitadas:**
     - Botão de reset: adiciona endpoint e UI complexity.
     - Histórico de versões: fora de escopo do MVP (Fase 2 do PRD).

4. **Limite de 5000 caracteres.**
   - **Decisão:** `CHECK (length(prompt) <= 5000)` no banco.
   - **Justificativa:** limita prompts excessivamente longos que confundiriam o agente; 5000 chars = ~1000 palavras, suficiente para instruções detalhadas.
   - **Trade-offs:** limita prompts muito longos (ex.: templates completos com exemplos).
   - **Alternativas rejeitadas:**
     - 2000 caracteres (sugestão PRD): muito restritivo para instruções complexas.
     - Sem limite: risco de prompts confusos ou maliciosos.

5. **Saudação de `install.py --update`.**
   - **Decisão:** verificar existência da tabela via `pg_isready` + `psql` e imprimir mensagem informativa.
   - **Justificativa:** informa ao operador que a feature foi implantada; não bloqueia o update.
   - **Trade-offs:** dependência de `docker compose exec` que pode falhar silenciosamente (try/except).
   - **Alternativas rejeitadas:**
     - Flag no `.env`: menos discoverable, requer edição manual.
     - Endpoint health check: mais complexo, requer deploy prévio.

### Riscos Conhecidos

| Risco | Probabilidade | Mitigação |
|-------|---------------|-----------|
| Cache staleness entre instâncias | Baixa (single-instance atual) | Se multi-instância futura: broadcast via Redis/pub-sub. |
| Migration com `down_revision` incorreto | Baixa | Verificar chain de migrations antes de aplicar. |
| Prompt muito longo confunde o agente | Média | Limite de 5000 chars + documentação sobre boas práticas. |
| Admin edita prompt que quebra fluxo do agente | Baixa | Prompt é texto livre — admin responsável; Fase 2 pode adicionar templates seguros. |

---

## Registros de Decisão de Arquitetura

### ADR-003: TTL do cache em memória dos prompts de coluna

**Status**: Aceito  
**Data**: 2026-08-09

**Contexto**

O `mcp_server.py` precisa entregar prompts de coluna na resposta MCP. Os prompts são editados pelo admin via API e precisam refletir sem redeploys. A pergunta é: ler do banco a cada chamada ou usar cache com TTL?

**Decisões**

1. **Cache em memória com TTL de 10 minutos** (`_KANBAN_PROMPTS_TTL_SECONDS = 600`).
2. **Invalidação por PUT** — ao atualizar um prompt, limpar o cache (`_kanban_prompts_cache.clear()`).
3. **Re-carregamento automático** — ao expirar o TTL, a próxima chamada a `enrich_status_payload` recarrega do banco.
4. **Sem invalidação distribuída** — o deploy atual é single-instance; se houver multi-instância no futuro, adicionar broadcast via Redis/pub-sub.

**Alternativas Consideradas**

### Alternativa 1: Sem cache (leitura direta do banco)

- **Descrição:** cada `update_task_status` faz SELECT na tabela `kanban_column_prompts`.
- **Prós:** zero staleness; sem lógica de cache.
- **Contras:** SELECT extra a cada movimento de card; carga maior no PostgreSQL.
- **Por que rejeitada:** overhead desnecessário em single-instance; cache com TTL é suficiente.

### Alternativa 2: Invalidação imediata (sem TTL)

- **Descrição:** cache válido até PUT invalidar.
- **Prós:** zero staleness se ninguém reiniciar a API.
- **Contras:** se a API reiniciar, cache vazio até próximo boot; se dois admin editarem simultaneamente, race condition.
- **Por que rejeitada:** TTL é fallback seguro para reinício e race conditions.

**Consequências**

**Positivas:**
- Staleness máximo de 10 minutos — aceitável para contexto de uso.
- Invalidação por PUT garante reflexão rápida após edição.
- Re-carregamento automático no boot garante disponibilidade mesmo sem PUT anterior.

**Negativas:**
- Se multi-instância futura, cada instância terá cache independente até broadcast ser adicionado.
- Admin pode editar e não ver efeito imediato em cards já movimentados (até 10 min).

**Riscos:**
- Multi-instância sem broadcast → inconsistência entre instâncias. Mitigado por deploy atual ser single-instance.

---

### ADR-004: UI inline editing na aba Prompts de Coluna

**Status**: Aceito  
**Data**: 2026-08-09

**Contexto**

Como a interface administrativa deve apresentar os prompts para edição? Modal? Accordion? Tabela com campos inline?

**Decisão**

**Tabela com campo editável inline:**
- Cada linha mostra: label da coluna, status interno, toggle de ativação (`is_enabled`), textarea para o prompt.
- Botão "Salvar" por linha.
- Indicador visual de estado (salvo/editando/erro).
- Contador de caracteres (até 5000) ao lado do textarea.

**Alternativas Consideradas**

### Alternativa 1: Editor modal/full-screen

- **Descrição:** ao clicar em uma coluna, abre painel lateral com textarea.
- **Prós:** mais espaço para escrever.
- **Contras:** mais cliques; menos visibilidade geral.
- **Por que rejeitada:** inline editing é mais rápido para 5 colunas (tabela cabe na tela).

### Alternativa 2: Lista colapsável (accordion)

- **Descrição:** cada coluna expandida mostra textarea.
- **Prós:** visualmente limpa.
- **Contras:** pode pesar se muitas colunas no futuro; mais scroll.
- **Por que rejeitada:** tabela inline é mais direta para edição em lote.

**Consequências**

**Positivas:**
- Editor rápido: abrir admin → editar → salvar em segundos.
- Contador de caracteres ajuda admin a ficar dentro do limite.
- Toggle `is_enabled` por linha permite ativar/desativar sem apagar o texto.

**Negativas:**
- Textarea inline pode ser menor que em modal — mas 5000 chars caem em textarea com scroll.

---

### ADR-005: Ausência de validação de sanitização no texto livre dos prompts

**Status**: Aceito  
**Data**: 2026-08-09

**Contexto**

Os prompts são texto livre que o admin pode escrever. Devemos sanitizar/validar o conteúdo antes de salvar ou injetar na resposta MCP?

**Decisão**

**Sem sanitização, sem validação de conteúdo:**
- Texto salvo é exatamente o texto injetado no JSON do MCP.
- Limite apenas de tamanho (5000 chars via `CHECK` no banco).
- O admin é o único editor; a responsabilidade pela qualidade do prompt é do admin.

**Alternativas Consideradas**

### Alternativa 1: Sanitização HTML

- **Descrição:** escapar tags HTML no texto antes de salvar.
- **Prós:** previene XSS se o prompt for exibido em HTML.
- **Contras:** desnecessário — o prompt é injetado como JSON no MCP, não renderizado em HTML.
- **Por que rejeitada:** over-engineering; MCP é JSON, não HTML.

### Alternativa 2: Validação de estrutura

- **Descrição:** exigir formato específico (ex.: checklist com marcadores).
- **Prós:** prompts consistentes.
- **Contras:** vai contra requisito "texto livre" do PRD; limita criatividade do admin.
- **Por que rejeitada:** requisito explícito de texto livre sem estrutura fixa.

**Consequências**

**Positivas:**
- Máxima flexibilidade para o admin.
- Zero complexidade de sanitização.
- Prompt é JSON-safe por padrão (FastAPI serializa como JSON).

**Negativas:**
- Admin pode escrever qualquer texto — sem proteção contra prompts mal-formados ou confusos.
- Se no futuro o prompt for renderizado em HTML, sanitização será necessária.

**Riscos:**
- Prompt mal-intencionado ou confuso pode prejudicar o agente. Mitigado por admin ser interno e responsável pela qualidade.

---

## ADRs de Produto

Os ADRs de produto (negócio) desta feature estão no documento `adrs` do workspace kanban-column-prompts:

- [ADR-001: Armazenamento de prompts em banco de dados com leitura em runtime](adrs/adr-001.md) — armazenamento em PostgreSQL, endpoints REST, cache em memória.
- [ADR-002: Escopo global dos prompts](adrs/adr-002.md) — prompts globais para todos os boards Planka.
- [ADR-003: Trigger apenas em `update_task_status`](adrs/adr-003.md) — prompts só aparecem ao mover card.
- [ADR-004: Texto livre sem estrutura fixa](adrs/adr-004.md) — campo de texto livre.
- [ADR-005: Permissão de edição](adrs/adr-005.md) — qualquer admin pode editar.
- [ADR-006: Backup automático via `pg_dump`](adrs/adr-006.md) — prompts incluídos automaticamente.
