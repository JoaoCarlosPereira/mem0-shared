# Autenticação Google e Identidade Usuário/Máquina/Agente — Lista de Tarefas

## Tarefas

| # | Título | Status | Complexidade | Dependências |
|---|--------|--------|--------------|--------------|
| 01 | Modelos e migração Alembic de identidade (machines, agent_tokens, link_audit_logs, colunas em users) | completed | medium | — |
| 02 | Endpoints /auth/google e /auth/me — validação do ID token Google e JWT de sessão | completed | medium | task_01 |
| 03 | AuthMiddleware unificado (session/agent_token/team/legacy) e mascaramento de token em logs | completed | high | task_01, task_02 |
| 04 | Endpoints do token de agente — gerar, consultar e revogar | completed | medium | task_01, task_03 |
| 05 | Onboarding backend — vínculo máquina→conta, conflito e resolução dinâmica | completed | high | task_01, task_02 |
| 06 | Provision com ?token= embutido na URL MCP | completed | low | task_04 |
| 07 | UI — NextAuth, tela de login, middleware de proteção e Bearer no axios | completed | high | task_02 |
| 08 | UI — wizard de onboarding de primeiro login | completed | medium | task_05, task_07 |
| 09 | UI — painel de instalação de agentes | completed | medium | task_04, task_06, task_07 |
| 10 | Infra — envs/secrets Google+JWT no compose e mascaramento no Traefik | completed | low | task_03 |
| 11 | Integração MCP com identidade e testes E2E de regressão | completed | medium | task_03, task_04, task_05, task_06 |
