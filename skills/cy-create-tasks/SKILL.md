---
name: cy-create-tasks
description: Decompõe PRD e TechSpec em tarefas detalhadas em PT-BR, com enriquecimento via exploração do código. Lê PRD/TechSpec e grava a lista mestra (document_type="tasks") e cada tarefa como TaskCard no Mem0 Shared via MCP. Sempre mantém o quadro Kanban sincronizado a cada criação/mudança. Use quando existir PRD/TechSpec e precisar de tarefas executáveis. Não use para PRD, TechSpec ou execução direta de tarefas.
argument-hint: "[feature-name-or-slug] [workspace-id?]"
---

# Criar Tarefas

Decomponha requisitos em TaskCards detalhados e acionáveis, com enriquecimento informado pela codebase.

<HARD-GATE>
**KANBAN:** O quadro SpecWorkspace Shared é a fonte de verdade. Toda tarefa que você criar ou alterar DEVE aparecer no Kanban via MCP (`create_task`, e depois `claim_task` / `update_task_status` durante a execução). Nunca deixe o plano apenas no chat ou em markdown local. Consulte `../cy-create-prd/references/kanban-shared-obrigatorio.md`.
**PIPELINE:** Cards DEVEM percorrer `tasks` → `em_andamento` → `revisao_codigo` → `fase_teste` → `concluido`. Nunca pule para `concluido` sem passar por revisão de código ou fase de testes.
**FIDELIDADE:** Decomponha fielmente o PRD/TechSpec. NÃO invente tarefas, requisitos ou comportamentos não especificados. Se faltar contexto, pare e exija atualização da especificação correspondente.
**MCP `kanban`:** Após cada create/claim/update, leia `kanban.do_now` na resposta e execute essa coluna antes de avançar.
**ÍNDICE DE CARDS:** `list_tasks` é a descoberta técnica primária. Após criar os cards, mantenha a coluna `Card ID` do documento `tasks` preenchida para rastreabilidade humana, auditoria e handoff; ela não é o único índice operacional.
NÃO escreva `_tasks.md` / `task_NN.md` locais como registro do sistema.
</HARD-GATE>

## Quadro Kanban Shared (obrigatório)

Ao usar esta skill e em qualquer execução posterior das tarefas:

1. Cards nascem no backlog com `create_task` (coluna `tasks`) — um card por tarefa aprovada. Em seguida, os `task_id` retornados vão para a coluna `Card ID` do documento `tasks` (índice obrigatório).
2. Antes de implementar: `claim_task` → `em_andamento`.
3. Ao terminar a implementação: `update_task_status` → **`revisao_codigo`** (obrigatório; não pular).
4. Após review ok: `update_task_status` → **`fase_teste`** (obrigatório; rodar testes nesta fase).
5. Só com evidência de teste APROVADA: `update_task_status` → **`concluido`**.
6. Bloqueios: `is_blocked=true` + `block_reason` + `add_spec_comment` na mesma interação.
7. Após criar todos os cards: `update_spec_workspace_status(workspace_id, "ativo")` e confirmar o quadro ao usuário.

Lei de ferro: **nenhuma atividade sem atualizar o quadro na mesma interação.**  
Lei de ferro 2: **nunca concluir sem ter passado por revisão de código e fase de testes no Kanban.**

## Entradas Obrigatórias

- Nome da feature, do qual se deriva o **slug** do `SpecWorkspace` (não um diretório local).
- `project_id` (nome do projeto/repositório atual; "default" se nenhum estiver claramente definido).
- No workspace, ao menos um dos documentos `prd` ou `techspec` gravado — lido via `read_spec_document`, **não** de arquivos locais.

## Fluxo de Trabalho

1. Carregar registro de tipos.
   - Ler `.docs/config.toml`.
   - Se contiver `[tasks].types`, usar essa lista como valores permitidos de `type`.
   - Caso contrário, usar os padrões embutidos: `frontend`, `backend`, `docs`, `test`, `infra`, `refactor`, `chore`, `bugfix`.

2. Carregar contexto (PRD/TechSpec via MCP — ADR-002).
   - Derivar o slug a partir do nome da feature; determinar o `project_id` (nome do projeto/repositório, "default" se nenhum).
   - Resolver o workspace por `list_spec_workspaces(slug=<slug>)` antes de criar. Se houver exatamente um resultado, usá-lo; se houver múltiplos, pedir ao usuário para escolher; se não houver, criar com `project_id`, `slug` e `name`.
     - **Se você criou o workspace aqui** (não apenas resolveu um existente), gravar a memória-ponteiro conforme `../cy-create-prd/references/ponteiro-de-spec.md`.
     - Não criar workspace duplicado apenas porque a busca filtrada pelo projeto atual voltou vazia.
     - Nesta skill, criar um workspace vazio normalmente indica erro de contexto: sem `prd` nem `techspec` não há o que decompor. Confirme com o usuário antes de seguir.
   - Ler o PRD via `read_spec_document(workspace_id, document_type="prd")` e a TechSpec via `read_spec_document(workspace_id, document_type="techspec")`.
   - Ler ADRs via `read_spec_document(workspace_id, document_type="adrs")` (fonte de verdade). Complementar com seções legadas embutidas no PRD/TechSpec se o doc `adrs` ainda estiver vazio. **NÃO** confiar em `.docs/tasks/<name>/adrs/*.md` local.
   - Se qualquer ferramenta MCP falhar (serviço indisponível), PARAR e reportar claramente — NÃO ler/escrever `_prd.md`/`_techspec.md`/arquivos de tarefa locais como fallback (ADR-002/ADR-007).
   - Se a TechSpec estiver ausente (`found=false`):
     - Avisar o usuário de que as tarefas serão de nível mais alto sem orientação de implementação da TechSpec.
     - Derivar tarefas dos requisitos funcionais e histórias de usuário do PRD em vez das seções de implementação da TechSpec.
     - Durante o enriquecimento, confiar mais na exploração da codebase para preencher `## Detalhes de Implementação`, `### Arquivos Relevantes` e `### Arquivos Dependentes`.
     - Marcar `<requirements>` com requisitos comportamentais derivados do PRD em vez de requisitos técnicos derivados da TechSpec.
     - Destacar explicitamente lacunas de detalhe de implementação no corpo da tarefa em vez de inventar especificidades.
   - Se nem o PRD nem a TechSpec forem encontrados no workspace, parar e pedir ao usuário para criar pelo menos um primeiro (via `cy-create-prd`/`cy-create-techspec`).
   - Disparar uma chamada Agent tool para explorar a codebase em busca de arquivos a criar ou modificar, padrões de teste e convenções de código.

3. Decompor em tarefas.
   - Decompor seções de implementação da TechSpec em tarefas granulares e independentemente implementáveis.
   - **Cada tarefa DEVE ser independentemente implementável quando todas as suas dependências declaradas forem atendidas.** Nenhuma tarefa pode exigir trabalho não declarado de outra tarefa. Se duas tarefas compartilham acoplamento forte, ou fundi-las ou extrair a parte compartilhada em uma tarefa de dependência.
   - **Sem dependências circulares.** Se a tarefa A depende da tarefa B, a tarefa B NÃO deve depender da tarefa A (direta ou transitivamente).
   - Cada tarefa deve ter: título, type, complexity e dependencies.
   - Atribuir complexity usando estes critérios:
     - `low`: Mudança em arquivo único, sem novas interfaces, sem concorrência, lógica direta.
     - `medium`: 2-4 arquivos, pode introduzir nova interface ou struct, pontos de integração limitados.
     - `high`: 5+ arquivos, novo subsistema ou refactor significativo, múltiplos pontos de integração, concorrência envolvida.
     - `critical`: Mudança transversal afetando muitos pacotes, alto risco de regressão, exige coordenação com outras tarefas.
   - Quando uma tarefa implementa diretamente ou é restrita por um ADR específico, incluir a referência do ADR na seção "ADRs Relacionados" da tarefa em Detalhes de Implementação.
   - Embutir requisitos de teste em toda tarefa. Nunca criar tarefas separadas dedicadas exclusivamente a testes.
   - Seguir a estrutura definida em `references/task-template.md`.
   - Consultar `references/task-context-schema.md` para definições de campos de metadados.

4. Apresentar decomposição de tarefas para aprovação interativa **em PT-BR**.
   - Mostrar todas as tarefas com: títulos, descrições, ratings de complexidade e cadeias de dependência.
   - Aguardar feedback do usuário antes de prosseguir.
   - Se o usuário solicitar alterações, revisar a decomposição e apresentar novamente.
   - Iterar até o usuário aprovar explicitamente.

5. Persistir a lista mestra de tarefas via MCP.
   - Construir a lista mestra de tarefas em **PT-BR** usando exatamente este formato de tabela markdown e persisti-la como documento `tasks` do workspace com `write_spec_document(workspace_id, document_type="tasks", content=<table>, expected_version=<version|null>)`:
     ```markdown
     # [Nome da Feature] — Lista de Tarefas

     ## Tarefas

     | # | Título | Card ID | Estado no plano | Complexidade | Dependências |
     |---|--------|---------|-----------------|--------------|--------------|
     | 01 | [Título da tarefa] | — | tasks | [low/medium/high/critical] | [task_NN, ... ou —] |
     ```
   - A coluna **`Card ID`** nasce com `—` porque os cards só existem após o passo 6. Ela **DEVE** ser preenchida na regravação obrigatória descrita no fim do passo 6 — é o índice que torna os cards descobríveis. Ver "Índice de Card IDs" abaixo.
   - A numeração de tarefas (`task_01`, `task_02`, ...) deve ser sequencial e consistente entre o documento mestre `tasks` e os `TaskCard`s individuais criados no passo 6.
   - Guardar o `version` retornado por este `write_spec_document` — ele é o `expected_version` da regravação do passo 6.
   - **NÃO escrever nenhum arquivo local `_tasks.md` / `task_NN.md`.** O workspace shared é a única fonte de verdade (ADR-002).
   - **Conflito/indisponibilidade:** em `conflict=true`, reler e reconciliar antes de tentar novamente; em erro de ferramenta, PARAR e reportar — sem fallback local.

6. Enriquecer cada tarefa e criá-la como `TaskCard` via MCP.
   - O enriquecimento permanece um **processo local do agente** (exploração da codebase); apenas o resultado final é persistido via MCP. Não há operação MCP para exploração.
   - Processar tarefas em ordem de dependência (uma tarefa após todas de que depende) para que o quadro reflita a mesma ordem validada pela lógica anti-ciclo no passo 3.
   - Para cada tarefa, construir o corpo enriquecido completo localmente, depois criar o card com `create_task(workspace_id, title=<task title>, description=<full enriched body>, branch_ref=<optional>)`.
     - `create_task` persiste `title`, `description` e `branch_ref` apenas. Codificar os metadados restantes da tarefa **dentro de `description`** como cabeçalho de metadados, preservando os campos do template: `type`, `complexity` e `dependencies` (listar os números das tarefas de dependência, ex.: `Dependências: task_01, task_02`), seguidos do corpo completo da tarefa.
     - O card é criado na coluna `tasks` (backlog) por padrão — correto para um plano recém-gerado.
   - **Tratamento de falha parcial:** rastrear quais tarefas foram criadas com sucesso. Se um `create_task` (ou a gravação do passo 5) falhar no meio (Mem0 Shared indisponível), PARAR imediatamente e reportar ao usuário **exatamente quais tarefas já foram criadas** e quais restam, para que ele conheça o estado parcial preciso — NÃO inventar um arquivo fallback local.
   - Mapear a tarefa para requisitos do PRD e orientação da TechSpec.
   - Disparar uma chamada Agent tool para descobrir arquivos relevantes, arquivos dependentes, pontos de integração e regras do projeto para esta tarefa específica.
   - Preencher TODAS as seções do template de `references/task-template.md` em **PT-BR** no `description` do card. Todo corpo de tarefa DEVE conter cada uma das seções a seguir — omitir qualquer uma é falha:
     - `## Visão Geral`: o que a tarefa realiza e por quê, em 2–3 frases.
     - bloco `<critical>`: lembretes críticos padrão (ler PRD/TechSpec, consultar TechSpec, foco no O QUÊ, minimizar código, testes obrigatórios).
     - bloco `<requirements>`: requisitos técnicos numerados com linguagem DEVE/DEVE SER.
     - `## Subtarefas`: 3–7 itens de checklist descrevendo O QUÊ, não COMO.
     - `## Detalhes de Implementação`: caminhos de arquivos, pontos de integração. Referenciar TechSpec.
     - `### Arquivos Relevantes`: caminhos descobertos com motivos breves.
     - `### Arquivos Dependentes`: arquivos afetados com motivos breves.
     - `### ADRs Relacionados`: links `[ADR-NNN: Título](adrs/adr-NNN.md)` apontando ao documento shared `adrs` — nunca `../adrs/*.md` locais. Omitir se não houver.
     - `## Entregáveis`: saídas concretas e testes relevantes ao comportamento alterado.
     - `## Testes`: casos de teste específicos em checklist; integração quando houver fronteira integrada relevante.
     - `## Critérios de Sucesso`: resultados mensuráveis, testes relevantes passando e nenhuma regressão; use metas de cobertura somente quando o repositório as definir.
   - Reavaliar complexity com base nos achados da exploração antes de criar o card (metadados em `description`).
   - Se o enriquecimento falhar para uma tarefa (problema local de exploração, não erro MCP), reportar e continuar para a próxima; reportar todas essas falhas no final. Um erro MCP/de serviço, por outro lado, PARA a execução com o relatório de estado parcial acima.
   - **Guardar o `id` que cada `create_task` retorna**, associado ao número da tarefa (`task_01` → `<uuid>`). Sem isso o passo abaixo é impossível.

   **Índice de Card IDs para rastreabilidade.**

   Após criar todos os cards, regravar o documento `tasks` com a coluna `Card ID` preenchida. A descoberta operacional deve usar `list_tasks(workspace_id)`; o documento mestre é uma representação humana do plano e não prevalece sobre o card em caso de divergência.

   Se a regravação retornar `conflict=true`, reler o documento, mesclar os ids na versão atual e gravar de novo. Se falhar por indisponibilidade do MCP, parar e reportar o estado parcial; não criar fallback local.

7. Validar o plano.
   - As verificações anti-ciclo e de independência rodam no passo 3, antes de qualquer card ser criado (não há arquivos locais para lint com `compozy tasks validate`, que opera em `.docs/tasks/`).
   - Após a criação, confirmar o quadro via `list_tasks(workspace_id, include_description=true)`, `list_spec_workspaces(project_id)` e `read_spec_document(workspace_id, document_type="tasks")`: quantidade, títulos, descrições, ids e dependências devem corresponder ao plano.
   - **Conferir o índice:** reler o documento `tasks` e verificar que **nenhuma** linha ficou com `Card ID` = `—`. Se ficou, o índice está incompleto e a feature não é repassável — corrigir antes de reportar.
   - Chamar `update_spec_workspace_status(workspace_id, "ativo")` para que o painel do projeto mostre entrega ativa.
   - Reportar ao usuário (PT-BR) o workspace shared (project + slug), quantos `TaskCard`s foram criados, e lembrar que **toda** implementação deve seguir no quadro: `claim_task` → `em_andamento` → `revisao_codigo` → `fase_teste` → `concluido` (sem pular etapas; consulte `../cy-create-prd/references/kanban-shared-obrigatorio.md`).

## Anti-Padrões

NÃO produza tarefas com estes defeitos:

- **Mega-tarefas.** Se uma tarefa toca mais de 7 arquivos ou tem mais de 7 subtarefas, é ampla demais. Dividi-la em tarefas menores com dependências explícitas entre elas.
- **Duplicação da TechSpec.** NÃO copiar definições de interface, trechos de código ou diagramas arquiteturais da TechSpec para arquivos de tarefa. Referenciar a seção da TechSpec pelo nome em PT-BR (ex.: "Ver seção 'Interfaces Principais' do TechSpec") em vez de reproduzir seu conteúdo.
- **Casos de teste vagos.** NÃO escrever descrições de teste como "testar caminho feliz" sem detalhe. Cada caso de teste deve nomear a entrada, condição ou comportamento específico verificado (ex.: "POST /job/done com job ID inexistente retorna 404").
- **Quadro silencioso.** NÃO criar ou finalizar trabalho sem o card Kanban refletir o novo estado no Mem0 Shared na mesma interação.
- **Pular pipeline.** NÃO mover um card para `concluido` sem tê-lo movido explicitamente por `revisao_codigo` e depois `fase_teste` (atualizações MCP separadas, com evidência de review + testes).

## Política de Idioma — PT-BR

**Todos** os artefatos gerados ou enriquecidos por esta skill são em **português brasileiro (PT-BR)**:

| Artefato | Destino |
|----------|---------|
| PRD/TechSpec (entrada) | Mem0 Shared via `read_spec_document` |
| Lista mestra | Mem0 Shared via `write_spec_document` (document_type="tasks") |
| Tarefas | `TaskCard` no quadro via `create_task` (metadados no `description`) |

Regras:
- Apresente o breakdown de tarefas ao usuário em PT-BR antes da aprovação
- Leia PRD, TechSpec e ADRs (já em PT-BR) sem traduzir para inglês ao citar
- Os metadados lógicos mantêm nomes em inglês (`title`, `type`, `complexity`, `dependencies`) por compatibilidade editorial; no Shared eles vivem na `description` do card, não em frontmatter local
- Se criar ou alterar PRD/TechSpec/ADR durante o enriquecimento, use os modelos de `cy-create-prd` / `cy-create-techspec`

## Tratamento de Erros

- Se nem o PRD nem a TechSpec forem encontrados no workspace, parar e pedir ao usuário para criar pelo menos um primeiro.
- Se as ferramentas MCP (Mem0 Shared) estiverem indisponíveis, parar e reportar claramente — incluindo, durante a criação de cards, exatamente quais tarefas já foram criadas (estado parcial). Nunca escrever um arquivo fallback local (ADR-002/ADR-007).
- Se `write_spec_document` (documento mestre `tasks`) retornar `conflict=true`, reler e reconciliar antes de tentar novamente.
- Se o usuário rejeitar a decomposição de tarefas, incorporar todo o feedback antes de apresentar novamente.
- Se a exploração da codebase revelar limites de tarefa que não correspondem à TechSpec, anotar a discrepância e perguntar ao usuário como proceder.
