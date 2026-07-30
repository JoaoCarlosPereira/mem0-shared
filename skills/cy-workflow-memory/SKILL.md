---
name: cy-workflow-memory
description: Mantém memória de workflow durável via mem0 MCP (OpenMemory local) e, opcionalmente, arquivos memory/ em PT-BR entre execuções. Use junto de cy-execute-task. Não substitui o Kanban Shared. Não use para correção de reviews ou preferências globais fora do fluxo SDD.
---

# Memória de Workflow (mem0 + opcional local)

Mantenha memória de workflow durável para execuções Spec/Kanban. **Colunas do Kanban continuam sendo a fonte de verdade do status da tarefa** — memória nunca substitui `claim_task` / `update_task_status`.

<HARD-GATE>
**KANBAN FIRST:** Status do trabalho = quadro Shared. Memória guarda decisões/aprendizados apenas.
**MEM0:** Prefira OpenMemory local MCP (`add_memories` / `search_memory`) com `project` obrigatório (ex.: nome do repo). Não envie memórias para a nuvem mem0.ai.
`MEMORY.md` local / `memory/*.md` são espelhos opcionais quando o caller ainda passa esses caminhos.
</HARD-GATE>

## Entradas Obrigatórias

- Id `project` para mem0 (obrigatório ao usar MCP).
- Opcional: diretório de memória de workflow / `MEMORY.md` compartilhado / caminho de memória da tarefa (legado Compozy).
- Opcional: sinal de compactação para arquivos locais.

## Fluxo de Trabalho

1. Carregar memória antes de editar código.
   - `search_memory` (`project` obrigatório) para decisões/convenções/anti-padrões relevantes à tarefa.
   - Se o caller fornecer caminhos locais de memória, leia-os como contexto adicional.
   - Se MCP indisponível e caminhos locais foram fornecidos, continue com arquivos locais e anote a limitação.
   - Se nem MCP nem caminhos existirem, pule com elegância (não invente arquivos).

2. Manter memória atualizada enquanto a tarefa roda.
   - Em decisões não óbvias, aprendizados duráveis ou erros que mudam o plano: `add_memories` (1–3 memórias concisas) e/ou atualize memória local da tarefa se existirem caminhos.
   - Promova à memória compartilhada (mem0 e/ou `MEMORY.md`) só fatos duráveis entre tarefas.
   - Mantenha passos de debug locais da tarefa fora da memória compartilhada.

3. Encerrar a execução de forma limpa.
   - Atualize memória **antes** de afirmar conclusão — mas só após (ou junto com) a atualização de coluna do Kanban daquela fase.
   - Não escreva "status: concluído" na memória como substituto de `update_task_status(..., "concluido")`.
   - Compacte arquivos locais somente quando o caller solicitar (`references/memory-guidelines.md`).

## Regras Críticas

- Não invente histórico, decisões ou status Kanban que não aconteceram.
- Não copie blocos grandes de código ou stack traces para a memória.
- Não duplique fatos óbvios do PRD/TechSpec/card Shared ou do repo.
- Não use memória para pular `revisao_codigo` / `fase_teste`.
- Mantenha memória compartilhada durável; mantenha memória da tarefa operacional.

## Teste de Decisão de Promoção

Antes de promover notas locais da tarefa para mem0 compartilhado / `MEMORY.md`:

1. Outra tarefa precisará disso para evitar um erro?
2. É durável entre execuções?
3. NÃO está já óbvio nas specs Shared ou no repositório?

Os três devem ser sim.

## Política de Idioma — PT-BR

Memórias e notas em **português brasileiro (PT-BR)**. Preserve termos técnicos do projeto quando já estabelecidos.

## Tratamento de Erros

- Se add/search no mem0 falhar, reporte e continue o trabalho Kanban/código — não bloqueie atualização do quadro por falha de memória.
- Se caminhos locais do caller estiverem ausentes, não adivinhe caminhos alternativos.
- Se memória conflitar com o repo ou specs Shared, confie no repo + documentos Shared e corrija a memória.
