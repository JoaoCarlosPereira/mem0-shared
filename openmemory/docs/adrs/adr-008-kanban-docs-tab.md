# ADR-008: Kanban substitui a aba Documentações

**Status**: Aceito  
**Data**: 2026-08-03  
**Supersede parcialmente**: ADR-007 (trilho SDD + listagem Spec na UI)

## Contexto

A aba Documentações ainda listava workspaces Spec e exibia trilho SDD ao lado do canvas. O produto desejado é uma única aba **Kanban** com a home de projetos do SPA (rebrand, sem marca PLANKA), identidade do usuário Mem0 logado, e SDD só via MCP/API.

## Decisão

1. Sidebar: label **Kanban** (`href` permanece `/docs`).
2. `/docs` = iframe full-bleed da **home** do SPA (`GET /api/v1/specs/kanban-home` → raiz `/planka/?embed=1&mem0_token=…`).
3. Deep-link compartilhável: `/docs/boards/:boardId` (`GET /api/v1/specs/kanban-boards/:id` → `/planka/boards/:id?embed=1&mem0_token=…`). O iframe envia `postMessage` (`mem0-kanban` / `path`) e o shell atualiza a URL com `history.replaceState` (sem remount).
4. Rotas `/docs/[project]` e `/docs/[project]/[workspace]` redirecionam para `/docs` (sem UI SDD / create-task Spec).
5. Product name na UI: **Kanban**; idioma forçado **pt-BR**.
6. JWT de sessão UI → upsert `user_account` por e-mail (nome/foto/`language=pt-BR`/role admin) + **membership compartilhada** (project manager + board editor) em **todos** os projetos/quadros Spec. Ambiente Mem0 Shared: todos veem e editam todos os quadros. Bearer INTERNAL continua DEFAULT_ADMIN (mirror FK-safe).
7. Spec permanece **SoT** para agentes. `create_spec_workspace` / `create_workspace` chama `mirror_ensure_workspace` quando `PLANKA_MIRROR_SYNC=1`. Claim/status/release já disparam `mirror_task_status`.
8. Cada board Spec tem coluna **SDD** (PRD / TechSpec / ADRs / Tasks espelhados como cards) à esquerda das colunas de pipeline.
9. Agentes **não** chamam Sails direto — só MCP/REST Spec → mirror.

## Consequências

- Listagem Spec e trilho SDD saem da UI Next; no Kanban a coluna **SDD** espelha PRD/TechSpec/ADRs/Tasks.
- Escrita canônica dos docs continua Spec MCP/API (`write_spec_document` / `read_spec_document`).
- Cutover: `POST /admin/planka/resync` + rebuild `planka` / `openmemory-mcp` / `openmemory-ui` (sem tocar Qdrant).
- Deep-link legado: `GET .../planka-embed` permanece para ops.
