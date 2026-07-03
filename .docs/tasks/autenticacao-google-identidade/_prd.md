# PRD — Autenticação Google e Identidade Usuário/Máquina/Agente

## Visão Geral

O OpenMemory (rede interna de memórias compartilhadas para agentes de IA) identifica hoje quem lê e grava memórias apenas pelo nome da máquina. Isso identifica o computador, não a pessoa: a troca de máquina quebra a continuidade, a auditoria não é confiável e não há vínculo claro entre pessoa, conta e agentes instalados.

Esta funcionalidade introduz **login com conta Google** na UI (restrito ao domínio Google Workspace da empresa), um **modelo de identidade com três conceitos separados — Usuário (pessoa), Máquina (computador) e Agente (processo local)** — e um **token de vínculo por usuário** para que os agentes locais se autentiquem sem depender apenas do hostname.

É para toda a equipe interna que usa a rede de memórias. O valor está na rastreabilidade (saber quem leu e gravou o quê), na continuidade da identidade ao trocar de máquina e na organização do acervo por pessoa real, sem descartar a base legada.

## Objetivos

- Identificar pessoas reais (não máquinas) em toda operação nova de leitura e gravação de memórias.
- Preservar 100% das memórias legadas, vinculando-as ao usuário correto após a migração voluntária.
- Eliminar a criação de usuários duplicados quando alguém troca de máquina.
- Disponibilizar trilha de auditoria por pessoa + credencial + máquina + agente (Fase 2).
- Marco-alvo do MVP: login obrigatório na UI, onboarding de primeiro login e token de agente funcionais.

## Histórias de Usuário

**Persona principal — membro da equipe (desenvolvedor/analista que usa agentes de IA):**

- Como membro da equipe, quero entrar na UI com minha conta Google corporativa para que o sistema saiba quem eu sou sem eu criar mais uma senha.
- Como membro da equipe, no primeiro login quero informar minha máquina atual e minha equipe para que minhas memórias antigas continuem associadas a mim.
- Como membro da equipe, quero gerar um token no painel de instalação para que meus agentes locais gravem e leiam memórias em meu nome.
- Como membro da equipe, quero revogar e regenerar meu token quando trocar de máquina, reinstalar o agente ou suspeitar de vazamento, sem perder meu histórico.
- Como membro da equipe, ao trocar de computador quero apenas vincular a máquina nova à minha conta, mantendo minha identidade e memórias.

**Persona secundária — todos os usuários (papel administrativo):**

- Como usuário autenticado, quero ver e resolver conflitos de vínculo (ex.: duas contas disputando a mesma máquina) para que a migração não crie associações erradas.
- Como usuário autenticado, quero consultar quem leu e gravou memórias (Fase 2) para entender o uso da rede.

**Caso de borda — usuário legado que não migrou:**

- Como usuário que ainda não migrou, quero que meus agentes continuem funcionando como hoje, sem interrupção, até eu decidir migrar.

## Funcionalidades Principais

### F1. Login com Google na UI (MVP)

Toda a UI passa a exigir autenticação com conta Google antes de qualquer acesso. Apenas contas do domínio Google Workspace da empresa são aceitas; contas de fora do domínio são recusadas com mensagem clara. O sistema captura automaticamente nome, e-mail, identificador único da conta e foto/avatar (quando disponível). A identidade retornada pelo Google é validada no backend — o sistema não confia em dados enviados pelo frontend.

### F2. Onboarding de primeiro login com vínculo ao legado (MVP)

No primeiro acesso, o usuário informa a máquina que utiliza atualmente e escolhe seu grupo/equipe. O sistema verifica se existe usuário legado associado àquele nome de máquina e propõe o vínculo; ao confirmar, as memórias existentes daquela máquina passam a pertencer à identidade Google, sem duplicar usuários. O vínculo é registrado com data e autor (auditável). Se a máquina informada já estiver vinculada a outra conta Google, o vínculo automático é bloqueado e o caso vira um conflito pendente (F5).

### F3. Painel de instalação/configuração de agentes com token (MVP)

Área na UI, disponível após login, onde o usuário gera seu token de vínculo (um por usuário, válido para todas as suas máquinas). O token é gerado pelo backend, imprevisível, exibido **uma única vez** com botão de copiar e instruções claras de configuração do agente local. O painel permite revogar e regenerar o token a qualquer momento; o token nunca aparece em logs de forma exposta.

### F4. Autenticação de agentes por token com convivência legada (MVP)

Agentes que enviam o token passam a ser identificados pela pessoa (usuário), com máquina e agente registrados em cada operação. Agentes sem token continuam funcionando no modo legado (identificação por hostname), por tempo indeterminado — a migração é voluntária e vale integralmente para novos usuários.

### F5. Detecção e resolução de conflitos de vínculo (Fase 2)

Quando duas contas Google tentam vincular a mesma máquina, ou uma máquina legada é disputada, o sistema bloqueia o vínculo automático e registra um conflito pendente. Qualquer usuário autenticado (todos têm papel administrativo) pode analisar e resolver o conflito pela UI, com registro de quem resolveu e quando. Inclui também o vínculo de máquinas adicionais à conta após o primeiro login.

### F6. Auditoria por identidade real (Fase 2)

As trilhas de leitura e gravação passam a registrar pessoa + credencial usada + máquina + agente + ação + alvo. Registros legados (só hostname) permanecem válidos e consultáveis. A UI de auditoria permite filtrar por pessoa, máquina, agente e período.

### F7. Visibilidade e maturidade do token (Fase 2)

O painel de tokens exibe data de criação e último uso ("last used"), permitindo regeneração sem downtime (criar o novo antes de revogar o antigo).

### F8. Métricas por pessoa e enforce por grupo (Fase 3)

As métricas de consumo (já existentes por projeto/agente/hostname) ganham a dimensão de pessoa autenticada. Opcionalmente, um grupo pode ativar o modo obrigatório: quando todos os membros migraram, conexões legadas daquele grupo passam a ser recusadas.

## Experiência do Usuário

**Fluxo de primeiro contato:**

1. O usuário acessa a UI e vê apenas a tela de login com o botão "Entrar com Google".
2. Autentica com a conta corporativa; contas fora do domínio veem mensagem de acesso negado.
3. No primeiro login, um assistente de boas-vindas pede: nome da máquina atual (com sugestão, se detectável) e grupo/equipe (lista dos grupos existentes).
4. Se houver usuário legado com aquela máquina, o sistema mostra um resumo ("Encontramos N memórias associadas a esta máquina — vincular à sua conta?") e o usuário confirma.
5. Ao final, o assistente leva ao painel de instalação de agentes, onde o token é gerado e as instruções de configuração são exibidas passo a passo.

**Uso regular:**

- Login persistente (sessão), com nome e avatar visíveis no cabeçalho da UI.
- Painel de instalação acessível a qualquer momento para consultar instruções, revogar ou regenerar o token.
- Troca de máquina: o usuário loga na UI da máquina nova, vincula a máquina à conta e configura o agente com seu token — sem criar novo usuário e sem perder histórico.

**Acessibilidade e clareza:** mensagens de erro específicas (domínio não permitido, máquina em conflito, token revogado), aviso explícito de que o token não será exibido novamente e confirmação antes de ações destrutivas (revogar token).

## Restrições Técnicas de Alto Nível

- A autenticação deve usar o login Google (OAuth/OpenID) com validação da identidade no backend; o identificador estável da conta Google é a chave da pessoa, não o e-mail.
- O domínio permitido deve ser configurável pelo operador do sistema.
- O token do agente é credencial sensível: armazenado de forma protegida (não em claro), nunca exposto em logs, revogável e regenerável.
- A base legada de usuários/máquinas e as memórias existentes não podem ser descartadas nem migradas de forma destrutiva.
- O sistema continua sendo de uso interno/local (LAN da empresa); não há requisito de exposição pública.
- Operações dos agentes não podem sofrer degradação perceptível pela validação do token.

## Fora de Escopo (Non-Goals)

- Outros provedores de identidade (Microsoft, GitHub, e-mail/senha) — apenas Google.
- Papéis e permissões granulares (viewer/editor/admin) — todos os usuários autenticados têm os mesmos poderes, incluindo administração.
- Permissões por memória ou por projeto (quem pode ler o quê) — a rede continua compartilhada como hoje.
- Bloqueio imediato de agentes legados — a convivência é indefinida; enforce só na Fase 3, por grupo e opt-in.
- Aprovação manual de novos usuários — qualquer conta do domínio entra automaticamente.
- Gestão do ciclo de vida de colaboradores (offboarding automático ao sair da empresa).
- Proteção contra ameaças externas à LAN — o foco é identificação e rastreabilidade, não perímetro de segurança.

## Plano de Entrega por Fases

### MVP (Fase 1)

- F1 Login com Google (domínio restrito) protegendo toda a UI.
- F2 Onboarding de primeiro login com vínculo ao usuário legado e escolha de grupo.
- F3 Painel de instalação de agentes com geração, exibição única, cópia, revogação e regeneração de token.
- F4 Agentes autenticando por token, com fallback legado intacto.
- Bloqueio de vínculo em conflito (sem tela de resolução — o conflito fica registrado).

**Critérios para avançar:** equipe consegue logar, migrar e operar agentes por token sem regressão no fluxo legado; nenhum usuário duplicado criado; memórias legadas acessíveis pelos donos corretos.

### Fase 2

- F5 Tela de resolução de conflitos e vínculo de máquinas adicionais.
- F6 Auditoria de leitura/escrita com pessoa + credencial.
- F7 Last-used e regeneração sem downtime.

**Critérios para avançar:** conflitos resolvíveis 100% pela UI; auditoria responde "quem leu/gravou o quê, quando, com qual credencial" para operações autenticadas.

### Fase 3

- F8 Métricas de consumo por pessoa e enforce opt-in por grupo.

**Critérios de longo prazo:** maioria da equipe migrada; grupos que desejarem operando 100% autenticados.

## Métricas de Sucesso

- **Adoção:** % da equipe com login realizado e token gerado (meta: maioria em 4 semanas após o MVP).
- **Migração:** % de usuários legados vinculados a contas Google; zero usuários duplicados criados por troca de máquina.
- **Rastreabilidade:** % das operações de memória atribuídas a pessoa autenticada (crescente por fase).
- **Continuidade:** zero perda de acesso a memórias legadas após vínculo; zero interrupção para quem não migrou.
- **Segurança operacional:** 100% dos tokens revogáveis pela UI; nenhum token exposto em logs.

## Riscos e Mitigações

- **Adoção lenta (migração voluntária):** painel de status de migração e comunicação interna; enforce por grupo na Fase 3 como acelerador.
- **Resistência ao login obrigatório na UI:** onboarding em poucos cliques com conta corporativa já existente (sem senha nova).
- **Vínculos incorretos na migração (máquina de outra pessoa):** confirmação explícita com resumo das memórias, bloqueio de conflitos e registro auditável de todo vínculo.
- **Dependência do Google como provedor único:** aceitável para uso interno; indisponibilidade do Google impede novos logins, mas agentes com token e o modo legado continuam operando.
- **Nomes de máquina ambíguos/duplicados na base legada:** o vínculo exige confirmação humana; casos ambíguos viram conflito pendente em vez de vínculo automático.

## Registros de Decisão de Arquitetura

- [ADR-001: Entrega incremental em 3 fases com convivência indefinida com o modelo legado](adrs/adr-001.md) — MVP com login + onboarding + token; auditoria e conflitos na Fase 2; métricas por pessoa e enforce por grupo na Fase 3.

## Perguntas em Aberto

- Qual o comportamento dos agentes ativos no momento da revogação do token (corte imediato vs. período de graça)?
- Uma pessoa com várias máquinas legadas: o MVP vincula apenas a máquina informada no primeiro login; as demais aguardam a Fase 2 — confirmar se isso atende os casos reais da equipe.
- Deve existir notificação (e-mail/aviso na UI) quando um token for revogado ou regenerado?
- O que fazer com usuários legados cuja máquina nunca for reivindicada por ninguém (memórias "órfãs")?
- Tempo de sessão da UI: login diário, semanal ou persistente até logout?
