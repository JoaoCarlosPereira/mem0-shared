# Modelo de PRD

> **Idioma:** escreva todo o conteúdo de `_prd.md` em **português brasileiro (PT-BR)**.

Use este modelo para estruturar cada Documento de Requisitos de Produto. Preencha cada seção com base no brainstorming. Deixe orientações de placeholder onde a informação for insuficiente e registre em Perguntas em Aberto.

## Visão Geral

Visão de alto nível da funcionalidade ou produto. Descreva:
- Qual problema resolve
- Para quem é
- Por que é valioso

## Objetivos

Objetivos específicos e mensuráveis:
- Métricas de sucesso e indicadores-chave de desempenho
- Objetivos de negócio e resultados esperados
- Cronogramas ou marcos-alvo

## Histórias de Usuário

Histórias organizadas por persona:
- Como [tipo de usuário], quero [ação] para que [benefício]
- Personas principais e seus fluxos
- Personas secundárias e casos de borda

## Funcionalidades Principais

Funcionalidades agrupadas por prioridade:
- Nome da funcionalidade: o que faz, por que é importante, comportamento de alto nível
- Requisitos funcionais de cada funcionalidade
- Interação entre funcionalidades

## Experiência do Usuário

Jornada do usuário do primeiro contato ao uso regular:
- Personas-chave e seus objetivos
- Fluxos principais passo a passo
- Considerações de UI/UX e acessibilidade
- Onboarding e descoberta

## Restrições Técnicas de Alto Nível

Limites que moldam o produto sem prescrever implementação:
- Integrações obrigatórias com sistemas existentes
- Mandatos de conformidade ou requisitos regulatórios
- Metas de desempenho na perspectiva do usuário
- Requisitos de privacidade e segurança de dados

NÃO inclua detalhes de implementação como bancos de dados específicos, frameworks, design de API ou padrões de arquitetura.

## Fora de Escopo (Non-Goals)

Funcionalidades explicitamente excluídas e limites:
- Funcionalidades adiadas para fases futuras
- Problemas adjacentes que não serão tratados
- Limites deste esforço

## Plano de Entrega por Fases

Entrega incremental com critérios de sucesso por fase:

### MVP (Fase 1)
- Funcionalidades principais incluídas
- Critérios de sucesso para avançar à Fase 2

### Fase 2
- Funcionalidades adicionais
- Critérios de sucesso para avançar à Fase 3

### Fase 3
- Conjunto completo de funcionalidades
- Critérios de sucesso de longo prazo

## Métricas de Sucesso

Medidas quantificáveis de sucesso:
- Métricas de engajamento do usuário
- Benchmarks de desempenho na perspectiva do usuário
- Indicadores de impacto no negócio
- Atributos de qualidade

## Riscos e Mitigações

Riscos não técnicos que podem afetar o produto:
- Riscos de adoção e estratégias de mitigação
- Riscos competitivos
- Restrições de cronograma e recursos
- Riscos de dependência de fatores externos

NÃO inclua riscos técnicos como complexidade arquitetural ou dívida técnica.

## Registros de Decisão de Arquitetura

ADRs documentando decisões tomadas no brainstorming:
- [ADR-NNN: Título](adrs/adr-NNN.md) — Resumo em uma linha da decisão

## Perguntas em Aberto

Itens pendentes que precisam de esclarecimento:
- Requisitos pouco claros
- Casos de borda que exigem input de stakeholders
- Dependências de decisões ainda não tomadas
