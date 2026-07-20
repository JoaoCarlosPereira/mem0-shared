# Protocolo de Perguntas

> **Idioma:** faça todas as perguntas ao usuário e escreva todos os artefatos em **PT-BR**.

Protocolo estruturado de brainstorming para criação de PRD. Siga estas fases e regras para conduzir a conversa da ideia ao documento.

## Fases

### 1. Descoberta

Colete o contexto inicial sobre a ideia ou o espaço do problema.
- Qual é o problema ou oportunidade central?
- Quem são os usuários afetados?
- O que motivou esta iniciativa?

### 2. Entendimento

Aprofunde requisitos e restrições.
- O QUE os usuários precisam especificamente?
- POR QUE isso gera valor de negócio?
- QUEM são os usuários-alvo e quais são seus fluxos atuais?
- Quais são os critérios de sucesso?
- Quais restrições são conhecidas (cronograma, orçamento, conformidade)?

### 3. Opções

Apresente abordagens de produto para avaliação do usuário.
- Ofereça 2–3 abordagens distintas com trade-offs claros.
- Comece pela abordagem recomendada e explique o porquê.
- Cada abordagem deve diferir em escopo, faseamento ou estratégia.
- Aguarde a escolha do usuário antes de prosseguir.

### 4. Refinamento

Refine a abordagem escolhida com follow-ups direcionados.
- Esclareça limites de escopo.
- Confirme faseamento e prioridade das funcionalidades.
- Valide critérios de sucesso e métricas.
- Resolva perguntas em aberto restantes.

### 4b. Validação Incremental do Design

Apresente o design do produto seção a seção para aprovação do usuário.
- Escale cada seção à sua complexidade.
- Apresente uma seção por vez; pergunte se está correta antes da próxima.
- Aplique YAGNI: questione cada funcionalidade quanto à necessidade no MVP.
- Esteja pronto para revisar qualquer seção antes de avançar.

### 5. Criação

Gere o documento PRD com o contexto reunido.
- Leia e preencha o modelo de PRD.
- Cada seção deve refletir decisões confirmadas.
- Itens não resolvidos vão para Perguntas em Aberto.

## Regras

### Perguntas Interativas
- Toda pergunta DEVE usar a ferramenta de pergunta interativa do runtime — a que pausa até o usuário responder.
- Não emita perguntas como texto simples e continue gerando.
- Se não houver ferramenta, apresente a pergunta como mensagem completa e pare.

### Limites de Perguntas
- Apenas uma pergunta por mensagem.
- Prefira múltipla escolha quando as opções forem predetermináveis.
- Aguarde a resposta antes da próxima pergunta.

### Portões de Progressão
- Complete pelo menos uma rodada de Entendimento antes de apresentar Opções.
- Tenha clareza sobre propósito, restrições e critérios de sucesso antes das abordagens.
- Obtenha aprovação da abordagem antes do Refinamento.

### Limites de Foco
- Perguntas devem focar em O QUE, POR QUE e QUEM.
- Nunca pergunte COMO, ONDE ou QUAL em relação à implementação técnica.
- Tópicos proibidos: bancos de dados, APIs, estrutura de código, frameworks, estratégias de teste, padrões de arquitetura, infraestrutura de deploy.

### Princípio YAGNI
- Remova funcionalidades não essenciais durante o refinamento.
- Questione cada funcionalidade: o MVP precisa disso?
- Adie nice-to-haves para fases posteriores.
- Prefira escopo menor e bem definido a amplitude ambiciosa.

### Anti-padrão: pular brainstorming em funcionalidades "simples"
Todo PRD passa pelo protocolo completo, independentemente da simplicidade percebida.
