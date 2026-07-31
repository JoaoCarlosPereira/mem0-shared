---
name: cy-final-verify
description: Exige evidência de verificação fresca antes de concluir no Kanban Shared (coluna fase_teste → concluido); relatório em PT-BR. Use antes de update_task_status concluido, commit, PR ou handoff. Não use em planejamento inicial ou antes de haver passo concreto de verificação.
---

# Verificação Antes da Conclusão

## Visão Geral

Declarar trabalho concluído sem verificação é desonestidade, não eficiência.

**Princípio central:** Evidência antes de afirmações, sempre.

**Violar a letra desta regra é violar o espírito desta regra.**

## A Lei de Ferro

```
NENHUMA AFIRMAÇÃO DE CONCLUSÃO SEM EVIDÊNCIA DE VERIFICAÇÃO FRESCA
```

Se o comando de verificação não foi executado na mensagem atual, o resultado não pode ser afirmado.

## Kanban Shared (obrigatório)

Esta skill é o gate da coluna **`fase_teste`**. Integração com o quadro Mem0 Shared:

1. O card **deve** já estar em `fase_teste` (`update_task_status`) antes de rodar a verificação de "tarefa concluída".
2. Com veredito **APROVADO**: chamar `update_task_status(task_id, "concluido", expected_version=...)` na **mesma** interação (ou imediatamente após o relatório).
3. Com veredito **REPROVADO**: **não** mover para `concluido`; manter `fase_teste` com `is_blocked=true` + motivo **ou** voltar a `em_andamento` / `revisao_codigo` conforme o tipo de falha; comentar no card via `add_spec_comment`.
4. **Proibido** usar esta skill para justificar `concluido` vindo de `em_andamento` sem ter passado por `revisao_codigo` e `fase_teste` (ver `../cy-create-prd/references/kanban-shared-obrigatorio.md`).

Se não houver `task_id` (verificação avulsa de commit/PR), ainda assim produza o Relatório de Verificação; ao existir card Shared, o Kanban prevalece como status oficial.

## A Função Gate

```
ANTES de afirmar qualquer status ou expressar satisfação:

1. IDENTIFICAR: Qual comando comprova esta afirmação?
2. EXECUTAR: Rodar o comando COMPLETO (fresco, integral)
3. LER: Saída completa, checar exit code, contar falhas
4. VERIFICAR: A saída confirma a afirmação?
   - Se NÃO: Declarar o status real com evidência
   - Se SIM: Declarar a afirmação COM evidência
5. SÓ ENTÃO: Fazer a afirmação

Pular qualquer passo = mentir, não verificar
```

## Escopo da Verificação

Alinhe o escopo da verificação ao escopo da afirmação:

- **Afirmação estreita** (ex.: "este teste passa"): Execute o teste específico.
- **Afirmação ampla** (ex.: "tarefa concluída", "pronto para commit"): Execute o **pipeline completo de verificação** — formatação, lint, todos os testes e build. Se o projeto define um comando gate único (ex.: `make verify`), execute-o.

Uma verificação estreita não sustenta uma afirmação ampla. Rodar só `make test` não justifica "tarefa concluída". Rodar só o linter não justifica "pronto para commit". O escopo da verificação deve ser igual ou mais amplo que o da afirmação.

**Em dúvida, rode o pipeline completo.** Verificar demais perde minutos. Verificar de menos perde horas.

**Pipeline verde ≠ requisitos atendidos.** Um build verde prova que o código compila, passa no lint e nos testes existentes. Não prova que a implementação corresponde aos requisitos. Para afirmações de "tarefa concluída" ou "requisitos atendidos", verifique também os entregáveis contra a especificação original — linha a linha, não por suposição.

## Falhas Comuns

| Afirmação              | Exige                              | Insuficiente                    |
| ---------------------- | ---------------------------------- | ------------------------------- |
| Testes passam          | Saída do comando de teste: 0 falhas | Execução anterior, "deve passar" |
| Linter limpo           | Saída do linter: 0 erros           | Checagem parcial, extrapolação  |
| Build ok               | Comando de build: exit 0           | Linter ok, logs parecem bons    |
| Bug corrigido          | Teste do sintoma original: passa   | Código alterado, assumiu fix    |
| Teste de regressão ok  | Ciclo vermelho-verde verificado    | Teste passa uma vez             |
| Agente concluiu        | Diff no VCS mostra alterações      | Agente reporta "sucesso"        |
| Requisitos atendidos   | Checklist linha a linha            | Testes passando                 |

## Sinais de Alerta

- Usar "deve", "provavelmente" ou "parece que"
- Expressar satisfação antes da verificação
- Prestes a commitar, dar push ou abrir PR sem verificação
- Confiar no relatório de sucesso de outro agente
- Depender de verificação parcial
- Pensar "só desta vez"
- Qualquer redação que implique sucesso sem evidência atual

## Prevenção de Racionalização

| Desculpa                                | Realidade              |
| --------------------------------------- | ---------------------- |
| "Deve funcionar agora"                  | Rode a verificação     |
| "Estou confiante"                       | Confiança ≠ evidência  |
| "Só desta vez"                          | Sem exceções           |
| "Linter passou"                         | Linter ≠ compilador    |
| "Agente disse sucesso"                  | Verifique de forma independente |
| "Estou cansado"                         | Cansaço ≠ desculpa     |
| "Checagem parcial basta"                | Parcial não prova nada |
| "Palavras diferentes, regra não se aplica" | Espírito acima da letra |

## Quando Aplicar

Aplique esta skill antes de:

- qualquer afirmação de sucesso ou conclusão
- qualquer expressão de satisfação com o estado da implementação
- qualquer commit ou criação de PR
- qualquer handoff que implique correção
- **`update_task_status(..., "concluido")` no Kanban Shared** (card deve estar em `fase_teste`)
- avançar para a próxima tarefa com base em conclusão

## Gate Pré-Commit e Pré-PR

Commits e PRs são artefatos permanentes. Exigem o padrão mais alto de verificação.

**Antes de `git commit`:**
1. Execute o pipeline completo de verificação (ex.: `make verify`). Não um subconjunto. O pipeline completo.
2. Confirme zero erros, zero avisos, zero falhas de teste na saída.
3. Produza um Relatório de Verificação (veja template abaixo) com veredito PASS.
4. Só então execute `git commit`.

**Antes de criar um PR:**
1. Tudo acima, mais:
2. Verifique se o diff corresponde às alterações pretendidas (review de `git diff`).
3. Confirme que não há arquivos não relacionados staged.

Se o pipeline completo não passou nesta sessão após a última alteração de código, o commit ou PR não deve prosseguir.

## Template de Relatório de Verificação

A verificação só está completa quando o agente **cita a saída real do comando** na resposta. "Rodei e passou" não é evidência. Se a saída da verificação não for mostrada, a verificação não aconteceu.

Toda verificação deve ser reportada com esta estrutura **em PT-BR**. Não desvie.

```
RELATÓRIO DE VERIFICAÇÃO
------------------------
Afirmação: [O que está sendo afirmado — ex.: "testes passam", "build ok", "tarefa concluída"]
Comando: [Comando exato executado — ex.: `make verify`]
Executado: [Timestamp ou "agora, após todas as alterações"]
Código de saída: [0 ou diferente de zero]
Resumo da saída: [Linhas-chave — contagem de passes, erros, resultado do build]
Avisos: [Avisos encontrados, ou "nenhum"]
Erros: [Erros encontrados, ou "nenhum"]
Veredito: APROVADO ou REPROVADO
```

Se o veredito for REPROVADO, não use linguagem de conclusão. Declare o que falhou e o que falta (em PT-BR).

Se o veredito for APROVADO, a afirmação pode prosseguir — mas apenas a afirmação específica sustentada pela evidência. "Testes passam" não significa "build ok".

## Quando a Verificação Falha

Falha na verificação não é beco sem saída. É informação. Siga este protocolo:

1. **Leia a falha.** Identifique o erro exato: qual comando falhou, qual teste, qual regra de lint, qual erro de build. Cite as linhas relevantes da saída.
2. **Diagnostique a causa raiz.** Não adivinhe. Leia a mensagem de erro. Rastreie até a origem. Se várias coisas falharam, trate uma de cada vez começando pela primeira falha.
3. **Corrija a causa raiz.** Aplique a mudança mínima que trata o erro real. Não aplique workarounds, não suprima avisos, não pule checagens.
4. **Re-verifique do zero.** Execute o comando de verificação completo de novo. Não assuma que o fix funcionou. Não rode só o subconjunto que falhou antes.
5. **Reporte com evidência.** Use o Template de Relatório de Verificação. Se passar agora, a afirmação pode prosseguir. Se falhar de novo, volte ao passo 1.

**Nunca:**
- Afirmar sucesso parcial ("3 de 4 checagens passam, serve")
- Pular re-verificação após um fix ("corrigi o erro, então deve passar agora")
- Culpar a ferramenta ("o linter está errado") sem evidência de falso positivo
- Avançar para a próxima tarefa com verificação ainda falhando

Se o comando correto de verificação não estiver claro, identifique-o antes de qualquer afirmação de conclusão. Se só houver verificação parcial disponível, declare essa limitação explicitamente e evite linguagem de conclusão.

## Política de Idioma — PT-BR

Relatórios de verificação, mensagens ao usuário e comentários no card Shared são em **português brasileiro (PT-BR)**:

- Não reprove documentação por estar em português
- Não traduza PRD, TechSpec, ADRs ou cards Shared para inglês durante a verificação
- Status oficial da tarefa = coluna do Kanban MCP, não arquivos locais `.docs/tasks/`
- Saída de comandos do sistema pode permanecer no idioma da ferramenta; o **relatório interpretativo** ao usuário deve ser em PT-BR
