# Apresentação OpenMemory — Tópicos e Funcionalidades Críticas

Este documento resume as principais características, decisões arquiteturais e funcionalidades da plataforma **OpenMemory (Mem0 Shared)** para a apresentação de 13 de agosto de 2026.

---

## 1. Visão Geral do OpenMemory (Mem0 Shared)
* **O que é**: Uma camada de memória inteligente, persistente e centralizada para agentes de IA e LLMs.
* **Operação 100% Local (Local-First)**: Projetado para rodar inteiramente dentro da rede local (LAN), utilizando LLMs e embeddings locais (via Ollama ou llama.cpp), eliminando a dependência de serviços externos e assegurando a privacidade dos dados corporativos.
* **Monorepo Poliglota**: Centraliza o SDK em Python (`mem0`), o SDK em TypeScript (`mem0-ts`), CLIs em Python e Node, além do backend FastAPI e frontend Next.js.

---

## 2. Infraestrutura e Proteção Crítica de Memória (Fail-Closed)
* **Prevenção de Perdas de Dados**: O Qdrant armazena a coleção principal de vetores (`mem0_storage`). No passado, perdas de volume causaram perdas de memórias, cuja recuperação dependeu da fila PostgreSQL.
* **Guarda de Exclusão (`deletion_guard.py`)**: Por padrão, as variáveis de ambiente `MEM0_ALLOW_MEMORY_DELETE` e `MEM0_ALLOW_BULK_DELETE` são mantidas desativadas (`0`), bloqueando exclusões não autorizadas de forma fail-closed.
* **Comandos de Infraestrutura Proibidos**: Comandos como `docker compose down -v` ou `make down-clean` sem confirmação explícita do operador são proibidos em produção. Utiliza-se o script `openmemory/scripts/safe-stack-down.sh` para preservação dos volumes.

---

## 3. Fila de Escrita Assíncrona (`write_queue`)
* **Motivação**: O processo de extração de fatos e geração de embeddings por LLMs é síncrono e lento (pode demorar vários segundos).
* **Desacoplamento**: Operações de gravação (`add_memories`) retornam um ACK imediato para o agente (`status: queued`, `job_id`) e são registradas no banco.
* **Processamento Resiliente**: O `write_worker.py` consome e processa as tarefas em segundo plano. Jobs falhos entram em ciclos de retentativa automática e, se esgotados, são isolados em uma fila de quarentena.

---

## 4. Auto-Deduplicação Inteligente (`autodedup.py`)
* **O Problema**: Agentes de IA adicionam repetidamente os mesmos fatos ou paráfrases semelhantes, inflando a base vetorial e competindo por slots de relevância no contexto.
* **A Solução**: Detecção automatizada de quase duplicatas por similaridade de cosseno (padrão de limite em `0.95`).
* **Supersedes automático**: Caso uma nova memória semelhe-se a uma existente, o sistema marca a memória anterior como obsoleta (`supersedes`) vinculando o ID do novo registro.
* **Modos de Operação**: `off` (padrão), `report` (apenas logs) e `apply` (aplica a obsolescência ativa).

---

## 5. Governança, Quarentena e Consolidação Semântica
* **Estado de Quarentena**: Memórias expiradas, duplicadas ou que violam quotas são enviadas para `quarantined`. Elas deixam de aparecer nas consultas padrão, mas permanecem salvas para auditoria.
* **Políticas de Governança (`governance_policy.py`)**: Permite parametrizar TTL (Time-To-Live) das memórias, quotas máximas por projeto e a janela de purga final de registros sob quarentena (ex.: 30 dias).
* **Consolidação Semântica**: Periodicamente, jobs de consolidação aglutinam e mesclam memórias semelhantes, mantendo a melhor versão de cada fato e limpando o histórico redundante.

---

## 6. Modelo de Identidade Corporativa (Usuário/Máquina/Agente)
* **Autenticação Google**: Toda a interface web (Next.js) exige login com contas Google corporativas (restrito ao domínio Workspace da empresa).
* **Identidade em 3 Camadas**: Substitui a identificação puramente baseada em hostname.
  1. **Usuário (Pessoa)**: Identidade corporativa real.
  2. **Máquina (Computador)**: Permite auditar a origem física da chamada.
  3. **Agente (Processo Local)**: O script/agente específico em execução.
* **Token de Agente (`omtk_`)**: Geração e gestão de tokens na UI do usuário para que os agentes locais se autentiquem de forma segura e autônoma.
* **Convivência Legada**: Agentes antigos que operam por hostname continuam funcionando sem interrupções (migração voluntária).

---

## 7. Integração de Produto: Kanban (Planka)
* **Aba Kanban integrada**: O SPA Kanban (Planka) é exibido como iframe full-bleed dentro do painel Next.js (aba `/docs`).
* **Comunicação por postMessage**: O iframe sincroniza rotas e estados de deep-linking bidirecionalmente com a URL do Next.js via `postMessage` (`mem0-kanban`), usando `history.replaceState` para evitar remounts.
* **Coluna SDD (Software Design Document)**: Primeira coluna reservada nos quadros onde artefatos como PRD, TechSpec, ADRs e Tasks são sincronizados como cards.
* **Spec como Source of Truth (SoT)**: Agentes de IA interagem apenas via MCP/REST API do Spec. O sistema espelha as operações (status, claim, moves) para o banco do Planka (`PLANKA_MIRROR_SYNC=1`).

---

## 8. Loja Interna de Skills (AgentRegistry)
* **Catálogo de Skills (`/store`)**: Interface de descoberta e gerenciamento de servidores MCP e habilidades desenvolvidas pela equipe.
* **Publicação Simplificada**: As habilidades definidas sob `skills/` são empacotadas em `tar.gz` e publicadas por script CLI (`seed-mem0-skills.py`), ficando imediatamente disponíveis para download ou instalação por outros membros e agentes da equipe.

---

## Dicas para a Apresentação
1. **Destaque a Privacidade (Local-First)**: Explique o uso de Ollama local e vector store em LAN.
2. **Mostre a Resiliência da Fila**: Explique que escritas são assíncronas para não gargalar a IA em produção.
3. **Frise a Governança e Segurança**: Destaque a proteção do Deletion Guard contra remoções acidentais e o modelo de identidade real via Google corporativo.
