# Modelo de Arquivo de Issue

> **Idioma:** escreva título, `## Comentário de Review` e `## Triagem` em **português brasileiro (PT-BR)**.

Use esta estrutura exata para cada arquivo de issue. O arquivo é parseado por `reviews.ReadReviewEntries()` e `prompt.ParseReviewContext()`.

## Formato

```
---
status: pending
file: path/to/file.go
line: 42
severity: critical|high|medium|low
author: claude-code
provider_ref:
---

# Issue NNN: <título conciso do problema em PT-BR>

## Comentário de Review

<descrição detalhada em PT-BR: por que é um problema,
sugestão de correção e snippet de código se útil>

## Triagem

- Decisão: `NÃO REVISADO`
- Notas:
```

## Definição dos Campos

- **NNN**: Número do issue com três dígitos (001, 002, ...).
- **status**: Começa como `pending`, depois `valid` ou `invalid`, e termina como `resolved` (valores em inglês por compatibilidade com o parser).
- **title**: Resumo em uma linha. Máximo 72 caracteres, em PT-BR.
- **file**: Caminho relativo à raiz do repositório. Use `unknown` apenas para issues puramente arquiteturais sem arquivo específico.
- **line**: Número da linha. Use `0` quando não houver linha específica.
- **severity**: Exatamente um de `critical`, `high`, `medium`, `low`.
- **author**: Sempre `claude-code` em rounds manuais.
- **provider_ref**: Sempre vazio em rounds manuais.

## Compatibilidade com o Parser

- O frontmatter YAML deve ser válido e parseável por `prompt.ParseReviewContext()`.
- Nomes de arquivo devem seguir `issue_NNN.md` para `prompt.ExtractIssueNumber()`.

## Regras

- Um problema por arquivo.
- O Comentário de Review deve ser acionável: problema claro e sugestão concreta de correção.
- Snippets com menos de 15 linhas.
- Título descritivo e curto em PT-BR.
  Bom: "Verificação de nil ausente antes de acesso ao map em resolveConfig".
  Ruim: "Problema no código".
