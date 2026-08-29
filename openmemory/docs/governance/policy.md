# Governança e Retenção de Memórias

## Política Global
As memórias no OpenMemory estão sujeitas a uma política global de governança para manter a qualidade, evitar o acúmulo infinito de dados não utilizados e evitar duplicatas.

### Tempo de Vida e Inatividade
- `ttl_max_age_days`: 365 dias. É a idade máxima natural de uma memória ativa.
- `ttl_idle_days`: 180 dias. Uma memória só é considerada para limpeza (TTL prune) se não for acessada há pelo menos 180 dias.
- `quarantine_window_days`: 30 dias. Memórias descartadas pelos processos de governança ficam em quarentena por 30 dias, podendo ser revertidas.

### Deduplicação
- `similarity_score` na detecção de duplicatas:
  O job de deduplicação varre as memórias buscando duplicatas idênticas (ou quase idênticas) para reduzir dados redundantes.
  Ele exige que a similaridade seja igual ou maior que 0.99 (`similarity_score >= 0.99`) para mover a duplicata automaticamente para a quarentena.
  Isso protege memórias semelhantes que possuem nuances ou atualizações complementares de serem erroneamente identificadas como duplicatas exatas, a menos que a política determine ação obrigatória (max_memories_action="enforce").

## Proteção de Dados (Fail-Closed)
Por design, todos os procedimentos de exclusão massiva e baseados em ID via API/MCP são proibidos (fail-closed).
As flags de ambiente (`MEM0_ALLOW_MEMORY_DELETE`, `MEM0_ALLOW_BULK_DELETE`) **não devem** estar ativadas em produção. Quando detectadas ativadas num ambiente de produção, um alerta nível `CRITICAL` será disparado no log da aplicação. 

O expurgo natural (após a quarentena) obedece à mesma proteção e depende de autorização explícita via `MEM0_ALLOW_GOVERNANCE_PURGE` ou das próprias flags de exclusão em massa.
