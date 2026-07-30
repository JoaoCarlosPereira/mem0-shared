# Critérios de Review

## Níveis de Severidade

### critical

Falhas de segurança, crashes, perda de dados, comportamento indefinido ou race conditions.
Issues que podem causar incidentes em produção ou comprometer dados do usuário.

Exemplos: bypass de autenticação, injeção SQL/comando, nil pointer dereference
em hot path, vazamento ilimitado de goroutines, escrita de dados sensíveis em logs.

### high

Bugs que afetam correção, gargalos de performance visíveis ao usuário ou
anti-padrões que prejudicam significativamente escalabilidade, confiabilidade ou usabilidade.
Precisam ser corrigidos antes do merge.

Exemplos: erro de lógica retornando resultados errados, loop O(n^2) sobre entrada
ilimitada, rollback de transação ausente, erro engolido silenciosamente em caminho
crítico, validação de entrada ausente em fronteira do sistema.

### medium

Preocupações de manutenibilidade, code smells, lacunas de cobertura de testes ou padrões
não idiomáticos que degradam a saúde de longo prazo. Não bloqueiam, mas devem ser tratados.

Exemplos: lógica duplicada entre pacotes, função com mais de 80 linhas e aninhamento profundo,
teste ausente para ramo de erro, context.Background() usado fora de main,
interface aceita mas só existe uma implementação.

### low

Melhorias menores, lacunas de documentação ou sugestões de nomenclatura. Aprimoramentos
opcionais que melhoram clareza.

Exemplos: nome de variável pouco claro, godoc ausente em função exportada,
conversão de tipo redundante, comentário levemente enganoso.

## Áreas de Avaliação

### 1. Segurança

- Falhas de autenticação e autorização.
- Lacunas de validação de entrada (injeção, path traversal, XSS).
- Segredos, tokens ou credenciais hardcoded.
- Uso incorreto de criptografia ou armazenamento inseguro.
- Exposição de dados sensíveis em logs ou mensagens de erro.

### 2. Correção

- Erros de lógica produzindo resultados errados.
- Bugs off-by-one e de condição de fronteira.
- Desreferências de ponteiro nil ou null.
- Caminhos de erro não tratados levando a falhas silenciosas.
- Type assertions ou conversões incorretas.

### 3. Concorrência

- Race conditions e sincronização ausente.
- Vazamentos de goroutine (sem caminho de shutdown ou cancelamento de context).
- Potencial de deadlock por ordem de locks.
- Uso incorreto de channels (send em channel fechado, blocking em unbuffered).
- `sync.WaitGroup` ausente para goroutines spawnadas.

### 4. Performance e Escalabilidade

- Problemas de complexidade algorítmica (O(n^2) onde O(n) bastaria).
- Vazamentos de recursos (file handles, HTTP bodies, conexões de banco).
- Crescimento ilimitado em slices, maps ou channels.
- Cache ausente para operações caras repetidas.
- I/O bloqueante em caminhos críticos sem timeout.

### 5. Tratamento de Erros

- Erros engolidos (atribuídos a `_` sem justificativa).
- Contexto de erro ausente (`fmt.Errorf("context: %w", err)`).
- `panic()` ou `log.Fatal()` em código de biblioteca ou handler.
- Tratamento amplo demais mascarando falhas específicas.
- Uso incorreto de `errors.Is()` ou `errors.As()`.

### 6. Qualidade de Código e Manutenibilidade

- Problemas de legibilidade (nomenclatura pouco clara, lógica profundamente aninhada).
- Duplicação de código entre funções ou pacotes.
- Funções excessivamente complexas que deveriam ser decompostas.
- Código morto ou exports não usados.
- Violações das convenções de código do projeto.

### 7. Testes

- Testes ausentes para caminhos críticos.
- Testes que verificam mocks em vez de comportamento.
- Padrões flaky (dependentes de tempo, dependentes de ordem).
- Cobertura inadequada de edge cases e caminhos de erro.
- `t.Parallel()` ausente para subtests independentes.

### 8. Arquitetura

- Dependências circulares entre pacotes.
- Violações de camada (ex.: pacote CLI importando detalhes internos de runtime).
- Abstrações vazadas expondo detalhes de implementação.
- Acoplamento forte impedindo testes independentes.
- Padrões inconsistentes na mesma área do codebase.

### 9. Operações

- Logging estruturado (`slog`) ausente ou insuficiente.
- Contexto de erro ausente para debug em produção.
- Valores de configuração hardcoded em vez de parametrizados.
- Tratamento de graceful shutdown ausente para processos long-running.
- Lacunas de observabilidade (sem métricas ou tracing em operações críticas).

## Abordagem de Review

- Leia PRD e TechSpec antes de revisar código para entender a intenção.
- Revise na ordem de severidade: critical primeiro, low por último.
- Foque em issues que importam. Ignore questões de estilo já pegas por linters.
- Forneça sugestões acionáveis: declare o problema e como seria o fix.
- Atribua severidade com base no impacto real, não em preocupação teórica.
- Crie um issue por arquivo por problema distinto.
- Se um problema abrange vários arquivos, crie um issue por arquivo afetado.
- Reconheça padrões bem implementados; não crie issues para eles.
