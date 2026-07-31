# Prompt — evolução do servidor Mem0 (SpecWorkspace / Kanban) para suportar handoff

> Cole este prompt no agente que for evoluir o servidor Mem0. Ele descreve lacunas
> **verificadas em 31/07/2026** contra o servidor em produção na rede local, não suposições.

---

## Situação em 31/07/2026 — o que já foi endereçado em outro lugar

Este documento é **backlog**, não plano de execução imediato. Duas frentes já mexeram em
território vizinho e é preciso não reimplementar o que já existe nem creditar a elas mais do
que de fato entregam.

### PR #19 — melhorias na busca de memórias

Mexe no caminho de leitura de `search_memory`: over-fetch de candidatos antes do ranqueamento,
`rerank` ligado e reportado, score efetivo exposto, dedup semântica opcional na escrita e
famílias de projeto (`MEM0_PROJECT_GROUPS`).

**Não fecha nenhuma das sete lacunas abaixo.** O que ele faz é tornar o *paliativo* da lacuna 5
confiável: a memória-ponteiro que o cliente grava passa a ser encontrada de forma estável a
partir de qualquer repositório da família, porque a busca de memórias deixou de truncar
candidatos antes de aplicar os boosts e passou a tratar repositórios irmãos como um assunto só.

Verificado no código, para não superestimar o alcance:

- `search_specs` (`app/utils/spec_search.py`) **reaproveita** `rank_search_results`, então em tese
  herdaria o boost de família. Na prática **não herda**: quando recebe `project_id`, a função
  aplica um pós-filtro de projeto exato (`spec_search.py`, normalização + comparação de
  igualdade) **antes** de ranquear, e o irmão já foi descartado quando o boost roda.
- `list_spec_workspaces` não passa por nenhum código tocado pelo #19.

**Oportunidade barata identificada nessa verificação:** tornar aquele pós-filtro de projeto do
`search_specs` ciente de família, reusando `projects_in_group`. É uma linha, resolve metade da
lacuna 5 para a busca de specs, e não estava previsto neste documento. Não foi feito.

### PR #21 — descoberta de specs e cards nas skills `cy-*`

Contorna as lacunas 2 e 5 **no cliente**, sem tocar no servidor: a lista mestra de tarefas ganhou
uma coluna `Card ID` que passa a ser o único índice de cards existente, e o `cy-execute-task`
para e pede ao usuário quando esse índice não existe, em vez de adivinhar.

É contorno, não correção. Enquanto o servidor não tiver `list_tasks`, o índice depende de a skill
ter rodado corretamente na criação — se alguém criar cards por fora, eles continuam invisíveis.

### Consequência para as prioridades abaixo

A ordem de prioridade do documento **não muda**. As lacunas 1 e 2 seguem sendo as que importam e
seguem intocadas. O que mudou é que a lacuna 5 dói menos hoje do que doía quando este documento
foi escrito, e que o item `find_spec_workspaces` pode ser reavaliado à luz do
`MEM0_PROJECT_GROUPS` que já existe no servidor — talvez baste aceitar família ali em vez de
criar ferramenta nova.

---

## Contexto

O Mem0 Shared expõe, via MCP, um SpecWorkspace com documentos versionados (`prd`, `techspec`,
`tasks`, `adrs`) e um Kanban de `TaskCard` com as colunas
`tasks → em_andamento → revisao_codigo → fase_teste → concluido`.

As skills `cy-*` (fluxo Spec-Driven Development) usam isso como fonte de verdade. O escrita
funciona bem: workspace idempotente por `(project_id, slug)`, documentos com concorrência otimista
que devolve `conflict` em vez de sobrescrever, `claim_task` com exclusividade real, e o bloco
`kanban` com `do_now` guiando a próxima transição. Isso está sólido.

**O problema é a leitura.** Todo o desenho assume que o agente que cria o trabalho é o mesmo que o
executa. No momento em que uma feature precisa ser repassada a outro desenvolvedor — que é a razão
de existir um quadro compartilhado — o modelo não fecha.

Ferramentas hoje disponíveis: `create_spec_workspace`, `update_spec_workspace_status`,
`list_spec_workspaces`, `write_spec_document`, `read_spec_document`, `search_specs`, `create_task`,
`claim_task`, `release_task`, `update_task_status`, `add_spec_comment`.

---

## Lacunas verificadas

### 1. Não existe forma de ler um card — CRÍTICO

Nenhuma ferramenta devolve o conteúdo de um `TaskCard`. O corpo enriquecido da tarefa vive em
`description` e contém tudo que o implementador precisa: requisitos, subtarefas, arquivos
relevantes e dependentes, entregáveis, casos de teste e critérios de aceite.

Quem não chamou o `create_task` **não tem acesso a nada disso**. O card é gravável e movível, mas
não legível.

*Verificar durante a implementação:* se `claim_task` já devolve o corpo do card, isso não está
documentado na descrição da ferramenta e não serve para planejar antes do claim — o agente precisa
ler o card para decidir se pode assumi-lo.

### 2. Não existe forma de enumerar os cards — CRÍTICO

`list_spec_workspaces(project_id)` devolve `task_counts`, ou seja, **contagem por coluna**.
Confirmado em resposta real: `"task_counts": {}`.

Não existe `list_tasks`. O servidor **não expõe recursos MCP** (`ListMcpResources` retorna vazio).
E `claim_task` exige um `task_id`.

Resultado: não há caminho programático do `project_id` até um card. O `task_id` só chega ao agente
se um humano copiar da UI web.

### 3. Não existe forma de ler comentários

`add_spec_comment` escreve; nada lê. As notas de revisão de código e a evidência de teste que o
fluxo manda registrar no card **nunca podem ser recuperadas** por um agente. Isso inviabiliza o
ciclo revisão → correção pelo quadro e qualquer auditoria posterior.

### 4. `search_specs` ignora trabalho em andamento

A indexação semântica acontece na transição para `concluido`. Durante todo o desenvolvimento — o
período em que descobrir a spec importa — ela é invisível na busca.

### 5. Descoberta entre projetos é impossível

> **Parcialmente mitigada (31/07/2026).** A raiz continua aberta: `list_spec_workspaces` ainda
> exige `project_id` exato. Mas o paliativo de memória-ponteiro ficou confiável com o PR #19, e o
> PR #21 fez as skills exigirem um ponteiro por repositório em feature multi-repo. Ver a seção
> "Situação em 31/07/2026" no topo.

`list_spec_workspaces` exige o `project_id` exato. No cliente, o `project_id` segue o **nome do
diretório de trabalho**. Uma feature que toca quatro repositórios tem o workspace sob um único
`project_id`; nos outros três, a chamada devolve `[]`.

Isso é pior que um erro, porque é silencioso: o agente conclui que não há spec e segue sem contexto.
Pior ainda, uma skill que cria o workspace quando não encontra acaba criando um **segundo**
workspace, fragmentando a spec — PRD em um, TechSpec em outro, sem nenhum aviso.

### 6. Card criado por engano é permanente

Não há `delete_task` nem arquivamento de card. Um card de teste ou duplicado fica no quadro para
sempre. Isso desencoraja qualquer validação contra o servidor real.

### 7. Inconsistência de documentação

As descrições de `read_spec_document` e `write_spec_document` dizem
`document_type = prd/techspec/tasks`, mas **`adrs` funciona** (testado: gravado e lido de volta,
versão 1). Os tipos válidos deveriam estar declarados num único lugar autoritativo, incluindo o
alias `adr`.

---

## O que implementar

Ordem de prioridade. Os dois primeiros itens desbloqueiam o handoff; sem eles o resto é cosmético.

### `list_tasks(workspace_id, status=None, include_description=False)`

Lista os cards do workspace, opcionalmente filtrando por coluna.

Cada item deve trazer, no mínimo: `id`, `title`, `status`, `assignee`, `is_blocked`,
`block_reason`, `version`, `branch_ref`, `created_at`, `updated_at`.

**`version` é obrigatório no retorno.** `update_task_status` exige `expected_version`; sem ele na
listagem, todo avanço de coluna custa uma chamada extra de leitura.

`include_description=True` traz também o corpo, para o caso de o agente querer avaliar vários cards
sem N chamadas.

### `get_task(task_id)`

Card completo, incluindo `description` e `version`. É o que permite montar o checklist de execução.

### `list_spec_comments(target_type, target_id)`

Comentários de um workspace, documento ou card, em ordem cronológica, com autor e data. Espelha o
`add_spec_comment`.

### `find_spec_workspaces(slug=None, query=None, project_id=None)`

Descoberta entre projetos. Com `slug`, encontra o workspace em qualquer `project_id`. Isso resolve a
lacuna 5 na raiz, e torna desnecessário o paliativo de memória-ponteiro que o cliente usa hoje.

Alternativa mais barata, se preferir não criar ferramenta nova: aceitar `project_id=None` em
`list_spec_workspaces` para devolver todos, ou aceitar uma lista de `project_id`.

> **Reavaliar antes de implementar (31/07/2026).** O servidor já tem `MEM0_PROJECT_GROUPS`
> (PR #19) mapeando repositórios irmãos numa família. Aceitar família em `list_spec_workspaces` e
> no pós-filtro de `search_specs` provavelmente entrega o mesmo resultado com muito menos
> superfície nova do que uma ferramenta `find_spec_workspaces`. Decidir entre as duas antes de
> escrever código.

### `search_specs(query, project=None, statuses=None)`

Permitir incluir workspaces não concluídos. Padrão pode continuar sendo só `concluido` para
preservar o comportamento atual, mas o chamador precisa poder pedir o que está em andamento.

### `delete_task(task_id)` ou `archive_task(task_id)`

Remover ou arquivar card criado por engano. Arquivar é preferível a excluir, se houver histórico.

### Correção de documentação

Declarar os tipos de documento válidos (`prd`, `techspec`, `tasks`, `adrs`, alias `adr`) nas
descrições de `read_spec_document` e `write_spec_document`.

---

## Critérios de aceite

O objetivo é que um agente sem nenhuma informação passada por humano consiga trabalhar. Considere
pronto quando:

1. Partindo **apenas** de um `project_id`, o agente chega a um card assumível e ao seu corpo
   completo, sem intervenção humana e sem UI web.
2. Partindo **apenas** de um `slug`, o agente encontra o workspace independentemente do
   `project_id` sob o qual foi criado.
3. O agente lê de volta os comentários de revisão e a evidência de teste que ele mesmo gravou num
   card em sessão anterior.
4. Uma feature em andamento aparece em busca quando o chamador pede explicitamente por trabalho não
   concluído.
5. Um card criado por engano pode ser removido ou arquivado.
6. `list_tasks` devolve `version` suficiente para chamar `update_task_status` sem leitura extra.

---

## Não quebrar

- A concorrência otimista de `write_spec_document` e `update_task_status`: devolver `conflict` com o
  conteúdo/estado atual, nunca sobrescrever em silêncio.
- A exclusividade do `claim_task` (`claimed=false` + `current_assignee`).
- A idempotência de `create_spec_workspace` por `(project_id, slug)`.
- O bloco `kanban` com `column`, `means`, `do_now`, `next_column`, `next_action`, `pipeline` e
  `pipeline_rule` nas respostas de create/claim/release/update — o cliente depende dele para não
  pular coluna, e a rejeição `skip_pipeline` deve continuar valendo.
- A obrigatoriedade do pipeline: `em_andamento` só via `claim_task`, retorno a `tasks` só via
  `release_task`, e `concluido` somente a partir de `fase_teste`.

---

## Observação sobre prioridade

As lacunas 1 e 2 são as que importam. Enquanto o `task_id` e o corpo do card dependerem de alguém
copiar da UI, o quadro compartilhado funciona como painel de acompanhamento para humanos, mas não
como fila de trabalho para agentes — que é o que o fluxo SDD pressupõe.
