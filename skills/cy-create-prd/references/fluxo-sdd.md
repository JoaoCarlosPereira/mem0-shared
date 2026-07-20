# Fluxo SDD — Spec-Driven Development

Documentação do fluxo de trabalho Spec-Driven Development (SDD) usando as skills `cy-*`, na ordem em que são executadas e o motivo de cada etapa.

---

## Visão Geral do Fluxo

```
IDEIA
  │
  ▼
[1] cy-create-prd ─────────────────────────────► _prd.md + ADRs
     (O QUÊ e POR QUÊ — foco no produto/negócio)
  │
  ▼
[2] cy-create-techspec ────────────────────────► _techspec.md + ADRs
     (O COMO — foco técnico, arquitetura, design)
  │
  ▼
[3] cy-create-tasks ───────────────────────────► _tasks.md + task_01.md ...
     (Decomposição em tarefas executáveis independentes)
  │
  ▼
[4] cy-execute-task ───────────────────────────► Código implementado
     (Implementação de cada tarefa individualmente)
     │
     ├── [4a] cy-workflow-memory ───────────────► MEMORY.md + memory/*.md
     │    (Persiste decisões e aprendizados entre tarefas)
     │
     └── [4b] cy-final-verify ─────────────────► Relatório de verificação
          (Prova que o código está correto antes de concluir)
  │
  ▼
[5] cy-review-round ───────────────────────────► reviews-NNN/issue_*.md
     (Auditoria de qualidade da implementação completa)
  │
  ▼
[6] cy-fix-reviews ────────────────────────────► Issues corrigidos
     (Correção em lote dos problemas encontrados na review)
  │
  ▼
[7] cy-final-verify ───────────────────────────► Relatório final
     (Verificação pós-correções antes do merge/PR)
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

**Artefatos gerados:**
- `.docs/tasks/<slug>/_prd.md` — documento principal de requisitos
- `.docs/tasks/<slug>/adrs/adr-NNN.md` — registros de decisões de produto

---

### [2] cy-create-techspec — Technical Specification

**Quando usar:** Após o PRD estar aprovado. Transforma requisitos de negócio em design técnico.

**O que faz:**
- Lê o `_prd.md`, ADRs existentes e explora a arquitetura do códigobase
- Faz perguntas técnicas interativas (arquitetura, data models, APIs, testing)
- Cria ADRs para decisões técnicas (padrão arquitetural, tecnologias escolhidas, modelo de dados)
- Gera o `_techspec.md` com: Arquitetura do Sistema, Modelos de Dados, Design de APIs, Interfaces Principais, Sequenciamento de Desenvolvimento, Requisitos de Teste

**Por que usar agora:** Porque o TechSpec é o contrato entre o produto (PRD) e a implementação. Define **O COMO** técnico sem entrar na granularidade de tarefas. Serve como referência para decompor em tarefas.

**Artefatos gerados:**
- `.docs/tasks/<name>/_techspec.md` — especificação técnica
- `.docs/tasks/<name>/adrs/adr-NNN.md` — ADRs técnicos adicionais

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

**Artefatos gerados:**
- `.docs/tasks/<name>/_tasks.md` — lista mestra de tarefas
- `.docs/tasks/<name>/task_01.md` ... `task_N.md` — especificações individuais de cada tarefa

---

### [4] cy-execute-task — Task Execution

**Quando usar:** Para cada tarefa listada em `_tasks.md`, executada sequencialmente (respeitando dependências).

**O que faz:**
1. **Ground in context** — Lê task spec, PRD, TechSpec, ADRs e verifica conflitos
2. **Build checklist** — Extrai entregáveis e critérios de aceite em checklist numerado
3. **Implement** — Implementa a tarefa mantendo escopo rigoroso
4. **Validate** — Roda testes e validações da tarefa + executa `cy-final-verify`
5. **Update tracking** — Atualiza checkboxes e status no task file e `_tasks.md`
6. **Commit** — Cria commit local (se auto-commit habilitado) ou deixa diff pronto

**Por que executar assim:** Porque cada tarefa é implementada de forma autônoma, mas com contexto completo do PRD/TechSpec. O checklist garante que nada é esquecido e a verificação obrigatória evita claims de conclusão sem prova.

**Artefatos atualizados:**
- `task_*.md` — status atualizado para "completed"
- `_tasks.md` — tabela de status atualizada
- `memory/*.md` e `MEMORY.md` — via `cy-workflow-memory`

---

### [4a] cy-workflow-memory — Workflow Memory

**Quando usar:** Automaticamente durante `cy-execute-task`, antes de editar código e antes de concluir.

**O que faz:**
- Mantém **memória compartilhada** (`MEMORY.md`) — decisões e aprendizados duráveis que afetam múltiplas tarefas
- Mantém **memória da tarefa** (`memory/<task>.md`) — detalhes operacionais locais de cada execução
- Promove fatos da tarefa para memória compartilhada apenas se: (1) outra tarefa precisa, (2) é durável, (3) não é óbvio do repositório
- Compacta arquivos quando necessário para manter clareza

**Por que usar:** Porque o contexto de desenvolvimento se acumula entre tarefas. Sem memória, a próxima execução da tarefa repetiria os mesmos erros ou redescobriria as mesmas decisões. A separação shared vs. task-local mantém o contexto organizado.

**Artefatos gerenciados:**
- `memory/MEMORY.md` — memória compartilhada entre tarefas
- `memory/<task>.md` — memória específica de cada tarefa

---

### [4b] cy-final-verify — Verificação Antes da Conclusão

**Quando usar:** Antes de qualquer claim de conclusão, commit, PR ou handoff. É usada dentro do `cy-execute-task` e no final do fluxo.

**O que faz:**
- Exige evidência fresca de verificação — nunca confia em "deveria funcionar"
- Roda o pipeline completo de verificação (formatting, linting, tests, build)
- Exige que a verificação seja proporcional ao claim (narrow claim = narrow verify; broad claim = full pipeline)
- Gera relatório estruturado em PT-BR com: Afirmação, Comando executado, Exit code, Resumo, Veredito APROVADO/REPROVADO

**Por que usar:** Porque a iron law do fluxo é clara: "NO COMPLETION CLAIMS WITHOUT FRESH VERIFICATION EVIDENCE". Claims sem verificação são dishonesty, não efficiency. O relatório estruturado garante que toda conclusão é auditável.

**Artefatos gerados:**
- Relatório de verificação citado na resposta (em PT-BR)

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
