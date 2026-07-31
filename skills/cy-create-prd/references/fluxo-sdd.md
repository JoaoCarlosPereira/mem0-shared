# Fluxo SDD — Spec-Driven Development

Documentação do fluxo de trabalho Spec-Driven Development (SDD) usando as skills `cy-*`, na ordem em que são executadas e o motivo de cada etapa.

---

## Regra obrigatória — Quadro Kanban Shared

**Iron law:** a cada atividade (criar workspace, gravar PRD/TechSpec/tasks, claim, bloqueio, mudança de coluna, conclusão), o agente **DEVE** atualizar o quadro/workspace no Mem0 Shared via MCP **na mesma interação**. Chat e arquivos locais não substituem o Kanban.

**Pipeline de card (sem pular):** `tasks` → `em_andamento` → `revisao_codigo` → `fase_teste` → `concluido`. Proibido concluir sem revisão de código e fase de testes no quadro.

Ferramentas: `create_spec_workspace`, `update_spec_workspace_status`, `create_task`, `claim_task`, `release_task`, `update_task_status`, `add_spec_comment`.

Detalhes e anti-padrões: [`kanban-shared-obrigatorio.md`](kanban-shared-obrigatorio.md).

---

## Visão Geral do Fluxo

```
IDEIA
  │
  ▼
[1] cy-create-prd ─────────────────────────────► SpecDocument prd (+ ADRs embutidos) no Shared
     (O QUÊ e POR QUÊ — foco no produto/negócio)  + status workspace
  │
  ▼
[2] cy-create-techspec ────────────────────────► SpecDocument techspec (+ ADRs) no Shared
     (O COMO — foco técnico, arquitetura, design) + workspace ativo
  │
  ▼
[3] cy-create-tasks ───────────────────────────► SpecDocument tasks + TaskCards no Kanban
     (Decomposição em tarefas executáveis)         (coluna backlog)
  │
  ▼
[4] cy-execute-task ───────────────────────────► Código + pipeline Kanban MCP
     claim → em_andamento → revisao_codigo → fase_teste → concluido
     │
     ├── [4a] cy-workflow-memory / mem0 ───────► decisões duráveis
     │
     ├── [4b] cy-final-verify (em fase_teste) ─► evidência → só então concluido
     │
     ├── [5] cy-review-round ──────────────────► cards em revisao_codigo + comments
     │
     └── [6] cy-fix-reviews ────────────────────► em_andamento → pipeline de novo
  │
  ▼
[7] encerramento ──────────────────────────────► update_spec_workspace_status concluido
```

---

## Detalhamento de Cada Etapa

### [1] cy-create-prd — Product Requirements Document

**Quando usar:** Ao iniciar uma nova feature, produto ou ideia. É a primeira etapa do fluxo.

**O que faz:**
- Explora o códigobase e o mercado para entender o contexto
- Faz perguntas interativas ao usuário (uma por mensagem, com opções múltiplas) para definir escopo e intenções
- Apresenta 2-3 abordagens de produto com trade-offs
- Cria ADRs (Architecture Decision Records) para decisões de produto
- Gera o `_prd.md` com: Visão Geral, Objetivos, Histórias de Usuário, Funcionalidades Principais, Experiência do Usuário, Plano de Entrega por Fases, Métricas de Sucesso, Riscos e Mitigações

**Por que usar primeiro:** Porque é fundamental definir **O QUÊ** e **POR QUÊ** antes de discutir **O COMO**. Isso evita viciar a discussão em implementação prematuramente e garante que a solução resolve o problema real do usuário.

**Artefatos gerados (Mem0 Shared via MCP):**
- Documento `prd` no SpecWorkspace — requisitos + ADRs de produto embutidos (texto completo)
- *(Legado)* `.docs/tasks/<slug>/_prd.md` / `adrs/*.md` locais — não são fonte de verdade no Shared; links `adrs/*.md` na UI 404

---

### [2] cy-create-techspec — Technical Specification

**Quando usar:** Após o PRD estar aprovado. Transforma requisitos de negócio em design técnico.

**O que faz:**
- Lê o PRD (e TechSpec existente) via MCP, extrai ADRs embutidos e explora a arquitetura do códigobase
- Faz perguntas técnicas interativas (arquitetura, data models, APIs, testing)
- Cria ADRs técnicos em memória e os embute no TechSpec (texto completo)
- Grava o TechSpec via MCP com: Arquitetura do Sistema, Modelos de Dados, Design de APIs, Interfaces Principais, Sequenciamento de Desenvolvimento, Requisitos de Teste, ADRs

**Por que usar agora:** Porque o TechSpec é o contrato entre o produto (PRD) e a implementação. Define **O COMO** técnico sem entrar na granularidade de tarefas. Serve como referência para decompor em tarefas.

**Artefatos gerados (Mem0 Shared via MCP):**
- Documento `techspec` no SpecWorkspace — especificação técnica + ADRs técnicos embutidos
- *(Legado)* `.docs/tasks/<name>/adrs/adr-NNN.md` locais — fora do Shared; não gravar no fluxo atual

---

### [3] cy-create-tasks — Task Decomposition

**Quando usar:** Após o TechSpec estar aprovado. Decompõe o trabalho em tarefas independentes.

**O que faz:**
- Lê PRD, TechSpec, ADRs e explora o códigobase para enriquecer o contexto
- Decompõe o TechSpec em tarefas **independentes e executáveis**
- Cada tarefa tem: título, tipo, complexidade (low/medium/high/critical), dependências, e checklist de subtarefas
- Enriquece cada tarefa com: Visão Geral, Requisitos, Detalhes de Implementação, Arquivos Relevantes, Arquivos Dependentes, Entregáveis, Testes, Critérios de Sucesso
- Gera `_tasks.md` (lista mestra em tabela) e `task_01.md`, `task_02.md`, etc.
- Roda validação automática (`compozy tasks validate`)

**Por que usar agora:** Porque tarefas bem estruturadas permitem que cada uma seja implementada de forma independente, com escopo claro e critérios de aceite definidos. A decomposição correta evita tarefas gigantes ("mega-tasks") e dependências circulares.

**Artefatos gerados (Mem0 Shared via MCP):**
- Documento `tasks` no SpecWorkspace — lista mestra em tabela, **com a coluna `Card ID`** preenchida
  após a criação dos cards. Esse documento é o **único índice de cards que existe**: nenhuma
  ferramenta MCP lista os cards do quadro (ver [`kanban-shared-obrigatorio.md`](kanban-shared-obrigatorio.md),
  "Limitações da plataforma").
- Um `TaskCard` por tarefa no Kanban, na coluna `tasks` (backlog), com o corpo enriquecido em
  `description`.
- Memória-ponteiro nos projetos dos repositórios envolvidos, se ainda não gravada
  (ver [`ponteiro-de-spec.md`](ponteiro-de-spec.md)).

---

### [4] cy-execute-task — Execução + Kanban MCP

**Quando usar:** Para cada `TaskCard` no quadro Shared, respeitando dependências.

**Pipeline obrigatório de colunas (não pular):**

`tasks` → `claim_task` → `em_andamento` → `revisao_codigo` → `fase_teste` → `concluido`

**O que faz (sincronizar o quadro a CADA passo):**
1. **Ler quadro** — `list_spec_workspaces` / board do workspace; escolher card no backlog
2. **Claim** — `claim_task(task_id)` → `em_andamento` **antes** de editar código
3. **Implementar** — escopo do card; card permanece em `em_andamento`
4. **Revisão de código** — ao terminar a implementação, `update_task_status` → **`revisao_codigo`**; fazer self-review (ou peer); anotar achados com `add_spec_comment`. **Proibido** ir para `concluido` daqui.
5. **Fase de testes** — após review ok, `update_task_status` → **`fase_teste`**; executar testes/lint relevantes **nesta** coluna; registrar evidência (comando + exit code). **Proibido** concluir sem esta fase.
6. **Concluir** — só com evidência APROVADA em `fase_teste`: `update_task_status` → **`concluido`**
7. **Bloqueio / retrabalho** — se review ou teste falhar: voltar a `em_andamento` ou marcar `is_blocked` + comentário; **não** saltar para `concluido`
8. **Release** — se abandonar: `release_task` (volta ao backlog)

**Por que assim:** review e teste são colunas visíveis do contrato da equipe. Concluir direto de `em_andamento` esconde risco e quebra o Kanban.

**Artefatos:**
- `TaskCard` no Mem0 Shared (coluna e bloqueio atualizados em cada transição)
- Comentários via `add_spec_comment` (review notes + evidência de teste)
- Código no repositório; memórias duráveis via mem0 MCP (não substituem o quadro)

---

### [4a] cy-workflow-memory — Memória (mem0 Shared)

**Quando usar:** Durante a execução, ao tomar decisões duráveis ou aprender algo reutilizável.

**O que faz:**
- Grava decisões/aprendizados no OpenMemory local (MCP mem0), com `project` adequado
- **Não** substitui atualização do Kanban — memória e quadro são ortogonais

---

### [4b] cy-final-verify — Verificação antes da conclusão

**Quando usar:** Antes de qualquer claim de conclusão no quadro (`concluido`), commit, PR ou handoff. O card **deve** já estar em `fase_teste`.

**O que faz:**
- Exige evidência fresca de verificação — nunca confia em "deveria funcionar"
- Só após APROVADO **e** card em `fase_teste`: `update_task_status(..., "concluido")` no Shared
- Claims de conclusão no chat **sem** ter passado por `revisao_codigo` + `fase_teste` = proibido

---

### [5] cy-review-round — Review de Código

**Quando usar:** Após todas as tarefas da feature serem implementadas, antes de abrir PR ou fazer merge.

**O que faz:**
- Lê PRD, TechSpec, Tarefas e ADRs para entender o contexto da implementação
- Identifica escopo da review via `git diff` ou paths fornecidos
- Faz review completa em 9 áreas: Security, Correctness, Concurrency, Performance, Error Handling, Code Quality, Testing, Architecture, Operations
- Prioriza: reviewa primeiro os arquivos core se houver mais de 15 arquivos
- Deduplica problemas (um issue por causa raiz, não por ocorrência)
- Gera `reviews-NNN/issue_*.md` para cada problema encontrado
- Gera recomendação de merge: "Precisa de correções", "Seguro para merge" ou "Limpo — pronto para merge"

**Por que usar agora:** Porque a review acontece quando tudo está implementado — é o momento certo para uma visão holística do código. A review valida contra os requisitos do PRD/TechSpec, não apenas contra estilo de código.

**Artefatos gerados:**
- `.docs/tasks/<name>/reviews-NNN/issue_001.md` ... `issue_NNN.md` — issues encontrados

---

### [6] cy-fix-reviews — Correção de Issues

**When usar:** Após a review round identificar issues que precisam de correção.

**O que faz:**
- Lê todos os issues da review e tria cada um como `valid` ou `invalid`
- Corrige issues na ordem de severidade (critical → high → medium → low)
- Implementa fixes production-quality com testes quando necessário
- Fecha issue files (`status: resolved`) após fix e verificação
- Mantém escopo restrito aos arquivos listados na review
- Roda `cy-final-verify` antes de qualquer commit

**Por que usar:** Porque resolve sistematicamente todos os problemas encontrados na review. A ordem por severidade garante que o mais impactante é corrigido primeiro, mesmo que o batch seja interrompido.

**Artefatos atualizados:**
- `reviews-NNN/issue_*.md` — status atualizado para `resolved`

---

### [7] cy-final-verify — Verificação Final (Pós-Correções)

**Quando usar:** Após `cy-fix-reviews` concluir, antes de criar PR ou fazer merge.

**O que faz:**
- Mesma função do passo [4b], mas com escopo mais amplo (valida toda a feature)
- Verifica que o diff corresponde às mudanças intencionais
- Confirma que nenhum arquivo não relacionado foi modificado
- Gera relatório final com veredito para handoff/merge

**Por que usar por último:** Porque é a última barreira antes do código ir para produção. Garante que todas as correções da review passaram pela verificação completa e que o diff está limpo.

---

## Regras Transversais do Fluxo

| Regra | Descrição |
|-------|-----------|
| **PT-BR em todos os artefatos** | Todos os documentos, perguntas e relatórios são em português brasileiro |
| **Uma pergunta por mensagem** | Perguntas interativas são feitas uma a uma, com opções múltiplas |
| **YAGNI rigoroso** | Remover toda abstração ou feature que não é estritamente necessária |
| **Draft then review** | Gerar rascunho completo, depois iterar com o usuário |
| **Verificação obrigatória** | Nenhuma conclusão sem evidência fresca de verificação |
| **ADRs para decisões** | Cada decisão significativa (produto ou técnica) é documentada como ADR |
| **Testes em todas as tarefas** | Nunca criar tarefas só para teste; testes embutidos em cada tarefa |
| **Tarefas independentes** | Cada tarefa é executável isoladamente quando dependências são atendidas |
| **Sem dependências circulares** | Se A depende de B, B não pode depender de A |

---

## Resumo do Fluxo em Uma Linha

```
PRD (o quê) → TechSpec (como) → Tasks (decompose) → Execute (implement)
           → Review (auditar) → Fix (corrigir) → Verify (provar)
```

Cada etapa alimenta a próxima, e a verificação (`cy-final-verify`) aparece como gate em múltiplos pontos para garantir qualidade contínua.
