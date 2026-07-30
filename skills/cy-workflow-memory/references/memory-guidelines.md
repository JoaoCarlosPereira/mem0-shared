# Diretrizes de Memória de Workflow

> **Idioma:** PT-BR. Preferir **mem0 MCP** (OpenMemory local) para memória durável. Arquivos `MEMORY.md` / `memory/` são espelho opcional.
> **Kanban:** status da tarefa = colunas Shared (`claim_task` / `update_task_status`), nunca só estes arquivos.

Use estas regras para manter a memória do workflow útil entre execuções de tarefas do SpecWorkspace.

## Papéis dos Arquivos

### Memória compartilhada: `MEMORY.md`

Use para contexto que deve sobreviver a várias tarefas e várias execuções.

Mantenha:
- estado atual do workflow que afeta mais de uma tarefa
- decisões técnicas ou de produto duráveis
- aprendizados reutilizáveis
- riscos em aberto ou notas de handoff

Evite:
- rascunhos passo a passo
- trechos grandes de código
- fatos já explícitos em `_prd.md`, `_techspec.md`, `_tasks.md` ou no repositório

### Memória da tarefa atual: `memory/<nome do arquivo da tarefa>`

Use para contexto específico da tarefa em execução.

Mantenha:
- snapshot do objetivo atual
- decisões importantes locais à tarefa
- aprendizados e correções locais
- arquivos ou superfícies tocadas
- notas prontas para a próxima execução

Evite:
- resumos cross-task que pertencem ao `MEMORY.md`
- repetição da especificação da tarefa
- transcripts longos de comandos

## Regras de Promoção

Promova do arquivo da tarefa para `MEMORY.md` apenas quando o item for:
- durável entre execuções
- útil para outra tarefa
- capaz de evitar repetir erros ou redescoberta

Deixe na memória da tarefa quando for:
- operacional só para a tarefa atual
- temporário
- detalhado demais para reuso no workflow inteiro

## Regras de Compactação

Quando a compactação for necessária:
- preserve estado atual, decisões duráveis, aprendizados, riscos e handoffs
- remova repetição, notas obsoletas, transcripts longos e fatos deriváveis
- reescreva para clareza, não para completude
- prefira bullets factuais curtos a narrativas longas

## Seções Padrão

### `MEMORY.md`

- `## Estado Atual`
- `## Decisões Compartilhadas`
- `## Aprendizados Compartilhados`
- `## Riscos em Aberto`
- `## Handoffs`

### `memory/<nome da tarefa>`

- `## Snapshot do Objetivo`
- `## Decisões Importantes`
- `## Aprendizados`
- `## Arquivos / Superfícies`
- `## Erros / Correções`
- `## Pronto para Próxima Execução`
