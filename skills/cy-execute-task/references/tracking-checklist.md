# Checklist de Rastreamento (Kanban MCP)

> **Idioma:** PT-BR. Fonte de verdade = quadro Mem0 Shared, não arquivos locais.

Aplique este checklist ao avançar um `TaskCard`:

1. Confirme `task_id` + `expected_version` atuais no board Shared.
2. **Claim** (`claim_task`) antes de qualquer edição de código → coluna `em_andamento`.
3. Ao terminar a implementação → `update_task_status(..., "revisao_codigo")` (obrigatório).
4. Após self-review / notes no card → `update_task_status(..., "fase_teste")` (obrigatório).
5. Rode `cy-final-verify` **com o card em `fase_teste`**; anote evidência (comando + exit code).
6. Só com veredito **APROVADO** → `update_task_status(..., "concluido")`.
7. **Nunca** pule `revisao_codigo` ou `fase_teste`. **Nunca** marque concluído só no chat.
8. Em bloqueio: `is_blocked=true` + `block_reason` + `add_spec_comment` na mesma interação.
9. Ao abandonar: `release_task` (volta a `tasks`), não invente coluna.
10. Releia a descrição do card e o TechSpec Shared antes de afirmar conclusão.
