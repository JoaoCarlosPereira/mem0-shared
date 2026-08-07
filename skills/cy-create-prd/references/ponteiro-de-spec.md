# Memória-ponteiro de spec — regra obrigatória

Uma spec que ninguém acha é uma spec que não existe. Este documento define como tornar um
`SpecWorkspace` descobrível por quem **não** o criou.

## O problema

Memórias e specs são **dois armazéns separados** no Mem0:

- `search_memory` / `list_memories` → memórias. **Nunca** devolvem specs.
- `search_specs` → specs, mas **somente de workspaces com status `concluido`** (a indexação semântica
  acontece na transição para `concluido`). Durante todo o desenvolvimento a spec é invisível aqui.
- `list_spec_workspaces(slug=<slug>)` → procura o workspace globalmente pelo slug; `project_id` pode ser usado como filtro adicional.

O `project_id` do mem0 segue o **nome do diretório de trabalho**. Consequência prática: um agente
rodando dentro de `<repo-do-microsserviço>` chama `list_spec_workspaces("<repo-do-microsserviço>")`,
recebe `[]`, e conclui que não há spec — quando na verdade o workspace está sob o `project_id` do
diretório-mãe ou de outro repositório da feature.

Isso é silencioso: não dá erro, devolve lista vazia. O agente segue adiante sem contexto.

## A regra

Ao criar um `SpecWorkspace`, gravar uma **memória-ponteiro** com `add_memories` em **cada projeto
mem0 onde alguém vai efetivamente trabalhar** na feature.

Obrigatório sempre que o `project_id` do workspace for **diferente** do nome do diretório em que o
implementador vai atuar — o que é a norma em features multi-repositório.

## Conteúdo mínimo do ponteiro

1. Identificação da tarefa/feature (código do Redmine, nome).
2. As coordenadas: `project_id`, `slug`, `workspace_id`.
3. O **aviso da pegadinha**: que `list_spec_workspaces` com o nome deste diretório retorna vazio, e
   que é preciso usar o `project_id` do workspace ou o `workspace_id` direto.
4. Que `search_specs` não encontra enquanto o workspace não estiver `concluido`.
5. Como carregar o contexto: `read_spec_document(workspace_id, "prd" | "techspec" | "tasks" | "adrs")`.
6. **O que a feature muda naquele repositório especificamente** — é o que faz o ponteiro valer a
   leitura, em vez de ser só um endereço.

## Modelo

```
PONTEIRO DE SPEC — <TAREFA/FEATURE>. Registrado em <data>.

As specs SDD desta tarefa não estão neste projeto mem0 nem em arquivos locais versionados.
Estão no SpecWorkspace do Mem0 Shared, sob outro project_id:

- project_id = <project_id do workspace>
- slug = <slug>
- workspace_id = <uuid>

ATENÇÃO: o project do mem0 segue o nome do diretório de trabalho. Trabalhando em
<este-diretório>, list_spec_workspaces("<este-diretório>") retorna VAZIO. Use
list_spec_workspaces("<project_id do workspace>") ou o workspace_id acima direto.
search_specs também não encontra, porque só indexa workspaces concluídos.

COMO CARREGAR O CONTEXTO:
read_spec_document(workspace_id="<uuid>", document_type="prd" | "adrs" | "techspec" | "tasks")

O QUE ESTA TAREFA MUDA NESTE REPOSITÓRIO:
<resumo específico — arquivos, endpoints, telas, pontos de registro>
```

## Manutenção

- Atualizar o ponteiro se o `slug` ou o `workspace_id` mudar.
- Ao encerrar a feature (`update_spec_workspace_status(..., "concluido")`), o `search_specs` passa a
  encontrá-la; o ponteiro continua útil como atalho e como registro do que mudou em cada repo.
- Não duplicar o conteúdo da spec dentro da memória. O ponteiro aponta; a spec é a fonte de verdade.
  Memória é extraída e reformulada pelo servidor — não serve como cópia fiel de documento.
