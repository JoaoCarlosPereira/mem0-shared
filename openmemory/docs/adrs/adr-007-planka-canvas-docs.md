# ADR-007: Canvas PLANKA na aba Documentações

**Status**: Aceito  
**Data**: 2026-08-03  
**Supersede parcialmente**: ADR-006 (cláusula “UI somente FastAPI / sem SPA PLANKA no browser”)

## Contexto

A entrega inicial (ADR-004/006) manteve o Kanban Spec em Next.js e usou o PLANKA só como sidecar de espelho. Na prática a aba `/docs` continuou visualmente e funcionalmente o quadro antigo (incluindo bugs de DnD). O produto desejado é **o PLANKA real** sob Documentações, com regras Spec (claim/pipeline/OCC) e tema Mem0.

React 18 (PLANKA) vs React 19 (OpenMemory UI) impede merge do client no bundle Next.

## Decisão

1. A página `/docs/[project]/[workspace]` exibe o **SPA PLANKA** (canvas same-origin) como quadro principal.
2. Shell Mem0 + trilho SDD (`prd`/`techspec`/`tasks`/`adrs`) permanecem no Next, fora do canvas.
3. Spec continua **SoT** para agentes (MCP/`/api/v1/specs`). Mutações humanas no canvas passam por bridge Spec (claim/release/status/OCC).
4. PLANKA é servido em path público `/planka` (`BASE_URL`/`BASE_PATH` no client). O reverse proxy **remove** o prefixo ao encaminhar ao Sails (padrão upstream); o browser continua pedindo `/planka/api` e `/planka/socket.io`.
5. Auth do canvas: JWT Mem0 (`AUTH_JWT_SECRET` / `NEXTAUTH_SECRET`) injetado no client embed (`mem0_token`).

## Consequências

- DnD nativo PLANKA substitui `dnd-kit` no canvas.
- Requer proxy Traefik/path estável, resync de boards e bridge Spec↔moves.
- Iframe/canvas isolado é aceito **somente** para isolamento de runtime React — não como “produto paralelo” na navegação.
