# Modelo de Arquivo de Tarefa

> **Idioma:** escreva todo o conteúdo de `task_*.md` e `_tasks.md` em **português brasileiro (PT-BR)**.

Use esta estrutura para cada arquivo de tarefa individual. O arquivo deve começar com frontmatter YAML contendo os metadados parseáveis.

```markdown
---
status: pending
title: [Título da tarefa]
type: [um de frontend, backend, docs, test, infra, refactor, chore, bugfix, ou override de [tasks].types no .docs/config.toml]
complexity: [low, medium, high, critical]
dependencies:
  - task_01
  - task_02
---

# Tarefa N: [Título]

## Visão Geral
[2–3 frases: o que a tarefa realiza e por que importa no contexto do projeto.]

<critical>
- SEMPRE LEIA o PRD e o TechSpec antes de começar
- CONSULTE O TECHSPEC para detalhes de implementação — não duplique aqui
- FOQUE NO "O QUÊ" — descreva o que precisa ser feito, não como
- MINIMIZE CÓDIGO — mostre código só para ilustrar estrutura atual ou áreas problemáticas
- TESTES OBRIGATÓRIOS — toda tarefa DEVE incluir testes nos entregáveis
</critical>

<requirements>
- [Requisito 1 — requisito técnico específico]
- [Requisito 2 — ex.: "DEVE autenticar usuários via tokens JWT"]
- [Requisito 3]
</requirements>

## Subtarefas
- [ ] N.1 [Descrição — O QUÊ realizar]
- [ ] N.2 [Descrição]
- [ ] N.3 [Descrição]

## Detalhes de Implementação
[Caminhos de arquivos a criar ou alterar, pontos de integração e dependências.
Referencie a seção de implementação do TechSpec para padrões e interfaces.]

### Arquivos Relevantes
- `caminho/arquivo` — [motivo breve]

### Arquivos Dependentes
- `caminho/dependencia` — [motivo breve]

### ADRs Relacionados
- [ADR-NNN: Título](../adrs/adr-NNN.md) — Relevância para esta tarefa

## Entregáveis
- [Saída concreta 1]
- [Saída concreta 2]
- Testes unitários com cobertura >= 80% **(OBRIGATÓRIO)**
- Testes de integração para [funcionalidade] **(OBRIGATÓRIO)**

## Testes
- Testes unitários:
  - [ ] [Caso 1 — ex.: "Caminho feliz: entrada válida retorna saída esperada"]
  - [ ] [Caso 2 — ex.: "Erro: entrada inválida retorna erro descritivo"]
  - [ ] [Casos de borda e condições limite]
- Testes de integração:
  - [ ] [Caso — ex.: "Fluxo ponta a ponta da requisição à resposta"]
- Meta de cobertura: >= 80%
- Todos os testes devem passar

## Critérios de Sucesso
- Todos os testes passando
- Cobertura de testes >= 80%
- [Resultado mensurável 1]
- [Resultado mensurável 2]
```

## Diretrizes

- Toda tarefa deve ser implementável de forma independente quando suas dependências estiverem concluídas.
- Toda tarefa DEVE incluir seção Testes e itens de teste nos Entregáveis.
- Nunca crie tarefas dedicadas exclusivamente a testes.
- Subtarefas descrevem O QUÊ, não COMO.
- Minimize código nas tarefas.
- Detalhes de implementação devem referenciar o TechSpec em vez de duplicá-lo.
