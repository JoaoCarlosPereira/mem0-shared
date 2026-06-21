#!/usr/bin/env python3
"""Instalador multiplataforma da Memória Central Compartilhada.

Roda em Linux, macOS e Windows (só precisa de Python 3.8+ e Docker). Dois modos:

  • local      — 1 máquina/dev: API/MCP + Qdrant + SQLite (docker-compose.yml).
                 Operação simples; inferência local (Ollama/llama.cpp) ou API.
  • production — stack de escala (docker-compose.scale.yml): PostgreSQL + PgBouncer
                 + Redis + Qdrant + workers (write/governance) + Traefik + observa-
                 bilidade (Prometheus/Grafana) + backup (MinIO). Pronto para um time.

Faz, ponta a ponta (modo produção):
  1. Pré-requisitos (Docker + Docker Compose v2) e arquivos .env.
  2. Resolve LLM + embedder INDEPENDENTES (Ollama local e/ou API remota), testando
     a conexão das APIs; ajusta MEM0_LOCAL_ONLY conforme o egress.
  3. Coleta segredos (PostgreSQL/Grafana/MinIO/API_KEY/auth de equipe).
  4. Sobe a infra base, roda migrations Alembic em container, sobe o stack completo
     e valida GET /health via proxy.

Uso:
  python install.py                                   # interativo (pergunta o modo)
  python install.py --mode production                 # produção, interativo
  python install.py --mode local --ollama-url http://192.168.0.10:11434
  python install.py --llm llama3.1:latest --embedder nomic-embed-text --yes
  # LLM no Ollama + embedder numa API remota (papéis independentes):
  python install.py --yes --llm llama3.1:latest --llm-backend ollama \\
      --embedder text-embedding-3-small --embedder-backend api \\
      --embedder-api-url https://api.openai.com/v1 --embedder-api-key SEU_TOKEN
  # produção não-interativa com segredos:
  python install.py --mode production --yes \\
      --llm llama3.1:8b --embedder nomic-embed-text \\
      --postgres-password '...' --grafana-password '...' \\
      --minio-secret-key '...' --auth-mode enforce --auth-tokens 'time-a:tok1,time-b:tok2'
  python install.py --data-dir /srv/mem0-data         # relocaliza os dados (Qdrant)
  python install.py --skip-models                     # mantém modelos do .env atual

Atualização (preserva memórias):
  python install.py --update                          # atualiza no lugar, mantém dados/.env
  python install.py --update --no-pull                # rebuild sem 'git pull' (código atual)
  python install.py --update --mode production        # força o modo (senão é autodetectado)

  O --update faz: git pull (best-effort) → rebuild das imagens → migrations
  aditivas (produção) → recria os containers no lugar. NUNCA remove volumes,
  então Qdrant + SQLite/PostgreSQL e os segredos do .env permanecem intactos.
"""

import argparse
import getpass
import ipaddress
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent
COMPOSE_DIR = ROOT / "openmemory"


# --------------------------------------------------------------------------- #
# Saída (texto simples para compatibilidade com qualquer terminal)
# --------------------------------------------------------------------------- #
def log(msg):  print("\n==> " + msg)
def ok(msg):   print("  [ok] " + msg)
def warn(msg): print("  [!] " + msg)
def die(msg):  print("  [x] " + msg, file=sys.stderr); sys.exit(1)


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def run(args, **kwargs):
    """Run a subprocess, raising a friendly error on non-zero exit."""
    try:
        return subprocess.run(args, **kwargs)
    except FileNotFoundError:
        die(f"Comando não encontrado: {args[0]}")


def have_docker_compose():
    r = run(["docker", "compose", "version"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return r.returncode == 0


def detect_lan_ip():
    """Return the primary private IPv4 of this host, or None."""
    import socket
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
        if ipaddress.ip_address(ip).is_private:
            return ip
    except OSError:
        pass
    return None


def discovery_base_url(port, explicit=None):
    """Build the URL advertised to remote agents (/discovery, /provision)."""
    if explicit:
        return explicit.rstrip("/")
    ip = detect_lan_ip()
    if ip:
        return f"http://{ip}:{port}"
    warn("Não detectei IP LAN; usando localhost (agentes em outras máquinas precisarão ajustar).")
    return f"http://localhost:{port}"


def set_env(file_path, key, value):
    """Idempotently set KEY=VALUE in a .env file (replace or append)."""
    lines = []
    if file_path.exists():
        lines = file_path.read_text(encoding="utf-8").splitlines()
    prefix = key + "="
    replaced = False
    for i, line in enumerate(lines):
        stripped = line.lstrip("# ").rstrip()
        if stripped.startswith(prefix) or line.startswith(prefix):
            lines[i] = f"{key}={value}"
            replaced = True
            break
    if not replaced:
        lines.append(f"{key}={value}")
    file_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _get_json(url):
    with urllib.request.urlopen(url, timeout=5) as resp:
        return json.loads(resp.read().decode("utf-8"))


def detect_ollama_models(ollama_url):
    """Query Ollama GET /api/tags and return the installed model names (or [])."""
    try:
        data = _get_json(ollama_url.rstrip("/") + "/api/tags")
    except Exception:
        return []
    names = []
    for m in data.get("models", []):
        name = m.get("name") or m.get("model")
        if name:
            names.append(name)
    return names


def detect_llamacpp_models(llamacpp_url):
    """Query the llama.cpp OpenAI-compatible GET /v1/models (or [] if down)."""
    base = llamacpp_url.rstrip("/")
    if not base.endswith("/v1"):
        base += "/v1"
    try:
        data = _get_json(base + "/models")
    except Exception:
        return []
    names = []
    for m in (data.get("data") or data.get("models") or []):
        name = m.get("id") or m.get("name") or m.get("model")
        if name:
            names.append(name)
    return names


def select_source(sources, labels, title="Como informar os modelos:"):
    """Prompt to choose how to provide a model (local backend or remote API)."""
    print(f"  {title}")
    for i, name in enumerate(sources, start=1):
        print(f"    {i}. {labels.get(name, name)}")
    choice = input("  Selecione (número ou nome): ").strip()
    if choice.isdigit():
        idx = int(choice) - 1
        if 0 <= idx < len(sources):
            return sources[idx]
    if choice in sources:
        return choice
    return sources[0]


def prompt_remote_api_role(role, default_url, default_model, default_key):
    """Pergunta URL + modelo + token de um endpoint OpenAI-compatível para UM papel.

    ``default_*`` pré-preenchem os campos (ex.: reaproveitar a API já configurada
    para o outro papel). Retorna (base_url, model, api_key).
    """
    print(f"  API remota para {role} (compatível com OpenAI):")
    if default_url:
        base_url = input(f"    Base URL [{default_url}]: ").strip() or default_url
    else:
        base_url = input("    Base URL (ex.: https://api.openai.com/v1): ").strip()
    while not base_url:
        base_url = input("    Base URL (obrigatória): ").strip()

    if default_model:
        model = input(f"    Modelo {role} [{default_model}]: ").strip() or default_model
    else:
        model = input(f"    Modelo {role}: ").strip()
    while not model:
        model = input(f"    Modelo {role} (obrigatório): ").strip()

    if default_key:
        key_in = input("    Token/API key [Enter = mesmo do anterior]: ").strip()
        api_key = key_in or default_key
    else:
        api_key = input("    Token/API key (Enter se não houver): ").strip()
    return base_url, model, (api_key or "").strip()


def _local_spec(backend, model, args, llamacpp_container_url, ollama_explicit):
    """Monta o spec de um papel servido por backend LOCAL (ollama ou llama.cpp)."""
    if backend == "llamacpp":
        # llama.cpp fala via provider openai apontando para o servidor local.
        v1 = llamacpp_container_url.rstrip("/")
        if not v1.endswith("/v1"):
            v1 += "/v1"
        return {"provider": "openai", "model": model, "base_url": v1,
                "api_key": (args.api_key or "").strip() or None,
                "ollama_url": None, "is_api": False, "label": "llama.cpp"}
    return {"provider": "ollama", "model": model, "base_url": None,
            "api_key": (args.api_key or "").strip() or None,
            "ollama_url": args.ollama_url if ollama_explicit else None,
            "is_api": False, "label": "Ollama"}


def _http(url, headers=None, data=None, timeout=15):
    """HTTP GET (ou POST se ``data``). Retorna (status, body_bytes).

    Levanta urllib.error.URLError em falha de conexão; HTTPError vira (code, body).
    """
    req = urllib.request.Request(url, data=data, headers=headers or {},
                                 method="POST" if data else "GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return getattr(resp, "status", resp.getcode()), resp.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


def _short(body):
    try:
        return body.decode("utf-8", "replace").strip()[:200]
    except Exception:
        return ""


def test_remote_api(base_url, api_key, model, role):
    """Testa um endpoint OpenAI-compatível para UM papel. Retorna (ok, mensagem).

    ``role`` é 'llm' ou 'embedder'. Tenta GET /models (conexão + autenticação, sem
    custo de tokens) e confere o modelo na lista. Se o provedor não expõe /models
    (404/405), faz um probe real no endpoint do papel (/chat/completions para LLM,
    /embeddings para embedder).
    """
    base = (base_url or "").rstrip("/")
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    # 1. Conexão + autenticação via GET /models.
    try:
        status, body = _http(base + "/models", headers=headers)
    except Exception as e:
        return False, f"não foi possível conectar a {base} ({e})."

    if status in (401, 403):
        return False, f"autenticação recusada (HTTP {status}) — verifique o token."
    if status == 200:
        try:
            ids = [m.get("id") for m in (json.loads(body).get("data") or [])]
        except Exception:
            ids = []
        if ids and model not in ids:
            warn(f"Conexão OK, mas o modelo '{model}' não aparece no /models "
                 "(a lista pode estar incompleta).")
        return True, f"conexão e autenticação OK ({len(ids)} modelos visíveis)."
    if status not in (404, 405):
        return False, f"GET /models retornou HTTP {status}: {_short(body)}"

    # 2. /models indisponível → probe real no endpoint do papel.
    if role == "embedder":
        path, payload = "/embeddings", {"model": model, "input": "ping"}
    else:
        path, payload = "/chat/completions", {
            "model": model,
            "messages": [{"role": "user", "content": "ping"}],
            "max_tokens": 1,
        }
    try:
        s, b = _http(base + path, headers=headers, data=json.dumps(payload).encode("utf-8"))
    except Exception as e:
        return False, f"falha no {path} ({e})."
    if s != 200:
        return False, f"{path} retornou HTTP {s}: {_short(b)}"
    return True, f"{path} respondeu 200."


def select_model(models, role):
    """Prompt for a model by number or name; return the chosen name."""
    choice = input(f"  Selecione o modelo de {role} (número ou nome): ").strip()
    if choice.isdigit():
        idx = int(choice) - 1
        if 0 <= idx < len(models):
            return models[idx]
    return choice


def resolve_role(role, available, args, labels, llamacpp_container_url,
                 ollama_explicit, api_defaults):
    """Resolve interativamente a origem de UM papel (LLM ou embedder).

    Cada papel pode vir de um backend local detectado (Ollama/llama.cpp), de
    nomes locais à mão, ou de uma API remota compatível com OpenAI — de forma
    independente do outro papel. ``api_defaults`` pré-preenche a URL/token quando
    o outro papel já configurou uma API. Retorna um spec dict.
    """
    sources = (list(available) + ["api"]) if available else ["api", "manual"]
    log(f"Seleção do modelo de {role}")
    src = sources[0] if len(sources) == 1 \
        else select_source(sources, labels, title=f"Origem do {role}:")

    if src == "api":
        base_url, model, key = prompt_remote_api_role(
            role, api_defaults.get("base_url") or args.api_url,
            args.llm if role == "LLM" else args.embedder,
            api_defaults.get("api_key"))
        return {"provider": "openai", "model": model, "base_url": base_url,
                "api_key": key, "ollama_url": None, "is_api": True,
                "label": "API remota"}

    if src == "manual":
        backend = args.backend if args.backend in ("ollama", "llamacpp") else "ollama"
        model = input(f"  Nome do modelo {role}: ").strip()
        return _local_spec(backend, model, args, llamacpp_container_url, ollama_explicit)

    models = available[src]
    ok(f"Backend {labels[src]} — modelos detectados:")
    for i, name in enumerate(models, start=1):
        print(f"    {i}. {name}")
    model = select_model(models, role)
    return _local_spec(src, model, args, llamacpp_container_url, ollama_explicit)


def spec_from_flags(role, args, llamacpp_container_url, ollama_explicit):
    """Monta o spec de um papel a partir das flags (modo não-interativo --yes).

    Backend por papel: --llm-backend/--embedder-backend, com fallback para
    --backend. URL/token por papel: --{role}-api-url/--{role}-api-key, com
    fallback para --api-url/--api-key.
    """
    key = "llm" if role == "LLM" else "embedder"
    model = args.llm if role == "LLM" else args.embedder
    if not model:
        die(f"--yes exige --{key} (nome do modelo de {role}).")
    backend = getattr(args, f"{key}_backend") or args.backend
    if backend in ("auto", None):
        backend = "ollama"  # nomes informados → assume Ollama por padrão
    if backend == "api":
        url = getattr(args, f"{key}_api_url") or args.api_url
        if not url:
            die(f"backend api para {role} com --yes exige --{key}-api-url (ou --api-url).")
        tok = getattr(args, f"{key}_api_key") or args.api_key
        return {"provider": "openai", "model": model, "base_url": url,
                "api_key": (tok or "").strip(), "ollama_url": None,
                "is_api": True, "label": "API remota"}
    return _local_spec(backend, model, args, llamacpp_container_url, ollama_explicit)


def write_role_env(compose_env, prefix, spec):
    """Grava as variáveis de UM papel (prefix = 'LLM' ou 'EMBEDDER') no .env."""
    set_env(compose_env, f"{prefix}_MODEL", spec["model"])
    set_env(compose_env, f"{prefix}_PROVIDER", spec["provider"])
    if spec["provider"] == "openai":
        # provider openai exige key não-vazia — placeholder quando não há token.
        set_env(compose_env, f"{prefix}_BASE_URL", (spec["base_url"] or "").rstrip("/"))
        set_env(compose_env, f"{prefix}_API_KEY", spec["api_key"] or "sk-no-key")
    else:  # ollama
        set_env(compose_env, f"{prefix}_API_KEY", spec["api_key"] or "")


def host_is_local(url):
    """Espelha o guard MEM0_LOCAL_ONLY do servidor (app/utils/memory.py).

    Loopback, host.docker.internal, *.local/*.internal, IPs RFC1918/loopback/
    link-local e nomes de serviço de uma palavra (exceto nuvens conhecidas) são
    locais. URL vazia (provider openai sem base_url → api.openai.com) é pública.
    """
    if not url:
        return False
    host = (urlsplit(url).hostname or "").lower()
    if not host:
        return False
    if host in ("localhost", "host.docker.internal"):
        return True
    if host.endswith(".local") or host.endswith(".internal"):
        return True
    try:
        ip = ipaddress.ip_address(host)
        return ip.is_loopback or ip.is_private or ip.is_link_local
    except ValueError:
        pass
    _CLOUD = frozenset({"openai", "anthropic", "gemini", "groq", "together",
                        "azure", "cohere", "mistral", "replicate", "huggingface"})
    if "." not in host:
        return host not in _CLOUD
    return False


def container_host_url(url):
    """Reescreve localhost/127.0.0.1 para host.docker.internal (alcançável do
    container). Mantém esquema e porta."""
    if not url:
        return url
    parts = urlsplit(url)
    host = (parts.hostname or "").lower()
    if host in ("localhost", "127.0.0.1"):
        netloc = "host.docker.internal" + (f":{parts.port}" if parts.port else "")
        return parts._replace(netloc=netloc).geturl()
    return url


def read_env(file_path, key):
    """Lê o valor atual de KEY num .env (ou None)."""
    if not file_path.exists():
        return None
    prefix = key + "="
    for line in file_path.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if s.startswith(prefix):
            return s[len(prefix):]
    return None


def configure_storage(data_dir, interactive, compose_env):
    """Decide onde Qdrant + SQLite persistem e grava no .env do compose (task_11).

    ``data_dir`` vazio/None mantém o padrão (volumes Docker gerenciados); um
    caminho relocaliza ambos os stores sob ``<dir>/qdrant`` e ``<dir>/db``. No
    modo interativo (``interactive``), pergunta quando nenhum caminho foi dado —
    Enter mantém o padrão. Retorna o caminho-base absoluto ou ``None`` (padrão).
    """
    if not data_dir and interactive:
        resp = input(
            "  Onde salvar as memórias (Qdrant + SQLite)?\n"
            "  [Enter] = volumes Docker gerenciados (padrão) | ou informe um caminho: "
        ).strip()
        data_dir = resp or None

    if not data_dir:
        # Padrão: volumes nomeados gerenciados pelo Docker; SQLite em ./api.
        set_env(compose_env, "QDRANT_STORAGE", "mem0_storage")
        set_env(compose_env, "SQLITE_STORAGE", "mem0_db")
        set_env(compose_env, "DATABASE_URL", "sqlite:////usr/src/openmemory/openmemory.db")
        ok("Armazenamento: volumes Docker gerenciados (padrão).")
        return None

    base = Path(data_dir).expanduser().resolve()
    qdrant_dir = base / "qdrant"
    db_dir = base / "db"
    for d in (qdrant_dir, db_dir):
        try:
            d.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            die(f"Não foi possível criar {d}: {e}")
    # .as_posix() mantém o caminho compatível com a interpolação do compose
    # (inclusive drive-letter no Windows, ex.: C:/dados/qdrant).
    set_env(compose_env, "QDRANT_STORAGE", qdrant_dir.as_posix())
    set_env(compose_env, "SQLITE_STORAGE", db_dir.as_posix())
    set_env(compose_env, "DATABASE_URL", "sqlite:////data/openmemory.db")
    ok(f"Armazenamento: {base} (Qdrant em ./qdrant, SQLite em ./db).")
    return str(base)


def wait_for_discovery(api_port, timeout):
    """Poll GET /discovery until it returns the expected JSON, or time out."""
    # 127.0.0.1 (não 'localhost'): no Linux 'localhost' pode resolver para ::1
    # (IPv6) primeiro, mas o Docker publica a porta em IPv4 — o urllib não cai
    # pro IPv4 sozinho e a sonda falharia mesmo com o serviço no ar.
    url = f"http://127.0.0.1:{api_port}/discovery"
    deadline = time.time() + timeout
    required = ("transport", "base_url", "route_template", "fields")
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=5) as resp:
                body = json.loads(resp.read().decode("utf-8"))
            if all(k in body for k in required):
                return True
        except Exception:
            pass
        time.sleep(3)
    return False


def _probe_health(port):
    """Uma requisição a /health. Retorna (ok, detalhe). ok=True só em 2xx."""
    url = f"http://127.0.0.1:{port}/health"
    try:
        with urllib.request.urlopen(url, timeout=5) as resp:
            body = resp.read().decode("utf-8", "replace")
            return (200 <= resp.status < 300), f"HTTP {resp.status}: {body[:400]}"
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")
        return False, f"HTTP {e.code}: {body[:400]}"
    except Exception as e:
        return False, f"sem resposta ({e})"


def wait_for_health(port, timeout):
    """Poll GET /health (via proxy) até responder 2xx. Retorna (ok, detalhe)."""
    deadline = time.time() + timeout
    detail = "sem resposta"
    while time.time() < deadline:
        okp, detail = _probe_health(port)
        if okp:
            return True, detail
        time.sleep(3)
    return False, detail


def docker_api_version():
    """Versão da API do Docker daemon (ex.: '1.51'), ou None se indisponível."""
    try:
        r = subprocess.run(["docker", "version", "--format", "{{.Server.APIVersion}}"],
                           capture_output=True, text=True, timeout=10)
        return r.stdout.strip() or None
    except Exception:
        return None


def wait_for_pgbouncer(compose_file, attempts=60):
    """Aguarda o PgBouncer aceitar conexões (pg_isready dentro do container)."""
    for _ in range(attempts):
        r = run(["docker", "compose", "-f", compose_file, "exec", "-T", "pgbouncer",
                 "pg_isready", "-h", "127.0.0.1", "-p", "5432"],
                cwd=str(COMPOSE_DIR),
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if r.returncode == 0:
            return True
        time.sleep(2)
    return False


# --------------------------------------------------------------------------- #
# Atualização in-place (preserva memórias) — flag --update
# --------------------------------------------------------------------------- #
def _compose_has_running(compose_file, service=None):
    """True se o projeto tem container(es) em execução para ``compose_file``.

    Com ``service``, checa apenas aquele serviço. Usa ``ps -q`` (lista só os
    containers em execução do projeto) e considera não-vazio = no ar.
    """
    cmd = ["docker", "compose", "-f", compose_file, "ps", "-q"]
    if service:
        cmd.append(service)
    try:
        r = subprocess.run(cmd, cwd=str(COMPOSE_DIR),
                           capture_output=True, text=True, timeout=30)
    except Exception:
        return False
    return r.returncode == 0 and bool(r.stdout.strip())


def detect_installed_mode():
    """Detecta o modo instalado pelos containers em execução.

    Produção tem precedência (o stack de escala inclui serviços que o local não
    tem). Retorna 'production', 'local' ou None se nada estiver no ar.
    """
    if _compose_has_running(SCALE_COMPOSE, "pgbouncer"):
        return "production"
    if _compose_has_running("docker-compose.yml", "openmemory-mcp"):
        return "local"
    # Fallback: qualquer container do projeto via scale/local compose.
    if _compose_has_running(SCALE_COMPOSE):
        return "production"
    if _compose_has_running("docker-compose.yml"):
        return "local"
    return None


def git_pull():
    """Atualiza o código com 'git pull --ff-only' (best-effort).

    Não é fatal: se não for um repositório git, não houver git, a árvore estiver
    suja ou o fast-forward falhar, avisa e segue com o código já presente (o
    usuário pode ter atualizado manualmente).
    """
    if not (ROOT / ".git").exists():
        warn("Diretório não é um repositório git — pulando 'git pull' "
             "(atualize o código manualmente se necessário).")
        return
    if not shutil.which("git"):
        warn("git não encontrado no PATH — pulando 'git pull'.")
        return
    log("Atualizando o código (git pull --ff-only)")
    r = run(["git", "pull", "--ff-only"], cwd=str(ROOT))
    if r.returncode != 0:
        warn("'git pull --ff-only' não aplicou (árvore com alterações locais, "
             "sem upstream configurado ou divergência). Seguindo com o código "
             "atual — atualize manualmente se quiser a versão mais nova.")
    else:
        ok("Código atualizado para a versão mais recente.")


def run_update(args, mode):
    """Atualiza uma instalação existente para a versão nova, PRESERVANDO os dados.

    Garantias:
      • Nenhum volume é removido (Qdrant, SQLite/PostgreSQL e segredos do .env
        permanecem intactos) — nunca usamos 'down', '-v' nem 'volume rm'.
      • O .env não é reescrito: modelos, storage e segredos atuais são mantidos.
      • Reconstrói as imagens com o código novo e recria os containers no lugar.
      • Produção: aplica migrations aditivas (alembic upgrade head) sem tocar nos
        dados. Local: o schema novo é materializado no startup (create_all).
    """
    compose_file = SCALE_COMPOSE if mode == "production" else "docker-compose.yml"

    def dc(*a, **k):
        return run(["docker", "compose", "-f", compose_file, *a],
                   cwd=str(COMPOSE_DIR), **k)

    log(f"Atualização in-place (modo: {mode})")
    ok("As memórias e segredos são preservados: nenhum volume será removido e o "
       ".env atual é mantido.")

    # 1. Código novo (opcional) ----------------------------------------------
    if not args.no_pull:
        git_pull()
    else:
        log("'git pull' pulado (--no-pull): usando o código já presente.")

    # 2. Reconstrói as imagens com o código novo ------------------------------
    log("Reconstruindo as imagens (docker compose build --pull)")
    if dc("build", "--pull").returncode != 0:
        die("Falha ao reconstruir as imagens. Nenhum dado foi alterado.")
    ok("Imagens reconstruídas com a versão nova.")

    # 3. Produção: infra base + migrations aditivas ---------------------------
    if mode == "production":
        log("Garantindo a infraestrutura base no ar (postgres, pgbouncer, redis, qdrant)")
        if dc("up", "-d", "postgres", "pgbouncer", "redis", "mem0_store").returncode != 0:
            die("Falha ao subir a infraestrutura base.")
        log("Aguardando o PgBouncer aceitar conexões")
        if not wait_for_pgbouncer(compose_file):
            dc("logs", "--tail", "60", "postgres", "pgbouncer")
            die("PgBouncer não ficou pronto a tempo.")
        ok("PgBouncer pronto.")
        log("Aplicando migrations novas (alembic upgrade head) — aditivo, preserva os dados")
        if dc("run", "--rm", "--no-deps", "openmemory-mcp",
              "alembic", "upgrade", "head").returncode != 0:
            die("Falha ao aplicar as migrations. Os dados NÃO foram alterados.")
        ok("Schema do PostgreSQL atualizado (dados preservados).")

    # 4. Recria os containers com a versão nova (volumes preservados) ---------
    log("Recriando os containers com a versão nova (docker compose up -d)")
    if mode == "production":
        # Stack completo (mesmo conjunto do install de produção).
        if dc("up", "-d").returncode != 0:
            die("Falha ao recriar os containers do stack de produção.")
        port = int(args.proxy_port)
    else:
        # Local: recria os serviços atuais; só inclui a UI se já estava no ar
        # (ou se --with-ui foi pedido), sem forçar quem não a usa.
        services = ["mem0_store", "openmemory-mcp"]
        if args.with_ui or _compose_has_running(compose_file, "openmemory-ui"):
            services.append("openmemory-ui")
        if dc("up", "-d", *services).returncode != 0:
            die("Falha ao recriar os containers locais.")
        port = int(args.api_port)

    # 5. Validação ------------------------------------------------------------
    if mode == "production":
        log(f"Aguardando GET /health via proxy (até {args.timeout}s)")
        healthy, detail = wait_for_health(port, args.timeout)
        if not healthy:
            warn(f"Última resposta de /health: {detail}")
            dc("logs", "--tail", "60", "openmemory-mcp")
            die("/health não respondeu saudável a tempo (os dados estão preservados).")
        ok(f"/health saudável ({detail}).")
    else:
        log(f"Aguardando GET /discovery (até {args.timeout}s)")
        if not wait_for_discovery(port, args.timeout):
            dc("logs", "--tail", "40", "openmemory-mcp")
            die("/discovery não respondeu a tempo (os dados estão preservados).")
        ok("/discovery respondeu 200 com os campos esperados.")

    log("Atualização concluída 🎉 — versão nova no ar, memórias intactas.")
    if mode == "production":
        print(f"""
  Proxy MCP:  http://localhost:{port}
  Health:     http://localhost:{port}/health
  Dados preservados: Qdrant + PostgreSQL (volume mem0_pgdata) + segredos do .env.""")
    else:
        print(f"""
  API/MCP:    http://localhost:{port}
  Descoberta: http://localhost:{port}/discovery
  Dados preservados: Qdrant + SQLite (conforme QDRANT_STORAGE/SQLITE_STORAGE do .env).""")
    return 0


def run_update_entry(args):
    """Valida pré-requisitos, descobre o modo instalado e dispara run_update."""
    log("Verificando pré-requisitos (atualização)")
    if not shutil.which("docker"):
        die("Docker não encontrado. Instale o Docker.")
    if not have_docker_compose():
        die("Docker Compose v2 não encontrado (use 'docker compose').")

    api_env = COMPOSE_DIR / "api" / ".env"
    compose_env = COMPOSE_DIR / ".env"
    if not api_env.exists() and not compose_env.exists():
        die("Nenhuma instalação anterior encontrada (openmemory/.env e api/.env "
            "ausentes). Rode a instalação normal antes de usar --update.")

    mode = args.mode or detect_installed_mode()
    if mode is None:
        die("Não detectei containers em execução para inferir o modo. "
            "Informe --mode local|production junto com --update.")

    needed = SCALE_COMPOSE if mode == "production" else "docker-compose.yml"
    if not COMPOSE_DIR.is_dir() or not (COMPOSE_DIR / needed).is_file():
        die(f"{needed} não encontrado em {COMPOSE_DIR}.")
    ok(f"Pré-requisitos OK (modo: {mode}).")
    return run_update(args, mode)


# --------------------------------------------------------------------------- #
# Resolução de modelos (compartilhada entre local-first e produção)
# --------------------------------------------------------------------------- #
def resolve_specs(args, llamacpp_container_url, ollama_explicit):
    """Detecta backends locais, resolve LLM + embedder (por papel) e testa as
    APIs remotas. Retorna (llm_spec, emb_spec)."""
    log("Detectando modelos locais (Ollama + llama.cpp)")
    available = {}
    if args.backend in ("auto", "ollama"):
        m = detect_ollama_models(args.ollama_url)
        if m:
            available["ollama"] = m
    if args.backend in ("auto", "llamacpp"):
        m = detect_llamacpp_models(args.llamacpp_url)
        if m:
            available["llamacpp"] = m

    labels = {"ollama": "Ollama", "llamacpp": "llama.cpp",
              "api": "API remota (compatível com OpenAI)",
              "manual": "Modelos locais (informar nomes manualmente)"}

    # LLM e embedder são resolvidos de forma INDEPENDENTE: cada um pode usar um
    # backend local (Ollama/llama.cpp) ou uma API remota — inclusive combinando.
    if args.yes:
        llm_spec = spec_from_flags("LLM", args, llamacpp_container_url, ollama_explicit)
        emb_spec = spec_from_flags("embedder", args, llamacpp_container_url, ollama_explicit)
    else:
        llm_spec = resolve_role("LLM", available, args, labels,
                                llamacpp_container_url, ollama_explicit, {})
        api_defaults = {"base_url": llm_spec["base_url"], "api_key": llm_spec["api_key"]} \
            if llm_spec["is_api"] else {}
        emb_spec = resolve_role("embedder", available, args, labels,
                                llamacpp_container_url, ollama_explicit, api_defaults)

    if not llm_spec["model"]:
        die("Modelo LLM não definido.")
    if not emb_spec["model"]:
        die("Modelo embedder não definido.")

    # API remota: só prossegue se o endpoint do papel responder (conexão + auth).
    for role, spec in (("llm", llm_spec), ("embedder", emb_spec)):
        if spec["is_api"]:
            log(f"Testando conexão com a API ({role})")
            ok_conn, msg = test_remote_api(spec["base_url"], spec["api_key"],
                                           spec["model"], role)
            if not ok_conn:
                die(f"Teste de conexão da API ({role}) falhou: {msg}")
            ok(msg)
    return llm_spec, emb_spec


# --------------------------------------------------------------------------- #
# Produção (stack de escala — docker-compose.scale.yml)
# --------------------------------------------------------------------------- #
SCALE_COMPOSE = "docker-compose.scale.yml"


def write_inference_scale(compose_env, llm_spec, emb_spec, args):
    """Grava a inferência por papel no .env do stack de escala e ajusta
    MEM0_LOCAL_ONLY. No scale, Ollama usa OLLAMA_LLM_URL/OLLAMA_EMBED_URL (URLs
    alcançáveis de dentro do container). Retorna True se houver egress público."""
    public = False
    role_url_key = {"LLM": "OLLAMA_LLM_URL", "EMBEDDER": "OLLAMA_EMBED_URL"}
    for prefix, spec in (("LLM", llm_spec), ("EMBEDDER", emb_spec)):
        set_env(compose_env, f"{prefix}_MODEL", spec["model"])
        set_env(compose_env, f"{prefix}_PROVIDER", spec["provider"])
        if spec["provider"] == "openai":
            base = (spec["base_url"] or "").rstrip("/")
            key = spec["api_key"] or "sk-no-key"
        else:  # ollama — URL alcançável de dentro do container
            base = container_host_url(spec.get("ollama_url") or args.ollama_url)
            key = spec["api_key"] or ""
        # Importante: o compose já dá default a OLLAMA_LLM_URL/OLLAMA_EMBED_URL
        # (host.docker.internal) e o servidor prefere essas vars sobre *_BASE_URL
        # (memory.py). Por isso gravamos AMBAS apontando para a URL efetiva — senão
        # um provider openai (API) seria sobrescrito pelo default do Ollama.
        set_env(compose_env, role_url_key[prefix], base)
        set_env(compose_env, f"{prefix}_BASE_URL", base)
        set_env(compose_env, f"{prefix}_API_KEY", key)
        if not host_is_local(base):
            public = True
    # MEM0_LOCAL_ONLY=0 só quando há egress público (a inicialização do cliente
    # seria recusada com =1). Caso contrário mantém o fail-closed (=1).
    set_env(compose_env, "MEM0_LOCAL_ONLY", "0" if public else "1")
    return public


def configure_storage_scale(data_dir, interactive, compose_env):
    """Define onde o Qdrant persiste (PostgreSQL usa o volume mem0_pgdata)."""
    if not data_dir and interactive:
        resp = input(
            "  Onde salvar os vetores do Qdrant?\n"
            "  [Enter] = volume Docker gerenciado (padrão) | ou informe um caminho: "
        ).strip()
        data_dir = resp or None
    if not data_dir:
        set_env(compose_env, "QDRANT_STORAGE", "mem0_storage")
        ok("Qdrant: volume Docker gerenciado. PostgreSQL: volume mem0_pgdata.")
        return None
    qdir = Path(data_dir).expanduser().resolve() / "qdrant"
    try:
        qdir.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        die(f"Não foi possível criar {qdir}: {e}")
    set_env(compose_env, "QDRANT_STORAGE", qdir.as_posix())
    ok(f"Qdrant em {qdir}. PostgreSQL: volume mem0_pgdata.")
    return str(qdir.parent)


def _ask_hidden(prompt):
    try:
        return getpass.getpass(prompt).strip()
    except Exception:
        return input(prompt).strip()


# Caracteres seguros num userinfo de URL sem precisar de percent-encoding. As
# strings de conexão do Postgres/PgBouncer são montadas como URL no compose
# (postgres://user:senha@host/db); símbolos como @ : / # % espaço quebram o
# parse e o PgBouncer nunca conecta. Validamos para falhar cedo, com mensagem.
_URL_SAFE = set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-._~!*+=")


def _ensure_url_safe(label, value, interactive, hidden=False):
    """Garante que ``value`` não tem caracteres que quebrem a URL de conexão.
    Interativo: re-pergunta até ficar válido. Não-interativo: aborta."""
    while True:
        bad = sorted({c for c in (value or "") if c not in _URL_SAFE})
        if not bad:
            return value
        shown = " ".join(repr(c) for c in bad)
        msg = (f"{label} contém caracteres que quebram a URL de conexão do "
               f"PgBouncer: {shown}. Use apenas letras, números e - . _ ~ ! * + =")
        if not interactive:
            die(msg)
        warn(msg)
        value = (_ask_hidden(f"  {label} (novo valor): ") if hidden
                 else input(f"  {label} (novo valor): ").strip())


def collect_secrets(args, compose_env, interactive):
    """Resolve e grava os segredos de produção no .env (prompt/flags/env, com os
    valores atuais como default). Não gera automaticamente. Retorna o dict."""
    defaults = {"POSTGRES_USER": "mem0", "POSTGRES_DB": "openmemory",
                "POSTGRES_PASSWORD": "mem0", "GRAFANA_PASSWORD": "mem0",
                "S3_ACCESS_KEY": "minioadmin", "S3_SECRET_KEY": "minioadmin",
                "API_KEY": "", "AUTH_MODE": "warn"}
    cur = {k: (read_env(compose_env, k) or v) for k, v in defaults.items()}
    flags = {"POSTGRES_USER": args.postgres_user, "POSTGRES_DB": args.postgres_db,
             "POSTGRES_PASSWORD": args.postgres_password,
             "GRAFANA_PASSWORD": args.grafana_password,
             "S3_ACCESS_KEY": args.minio_access_key,
             "S3_SECRET_KEY": args.minio_secret_key,
             "API_KEY": args.server_api_key, "AUTH_MODE": args.auth_mode}
    for k, v in flags.items():
        if v:
            cur[k] = v

    if interactive:
        log("Segredos de produção (Enter mantém o valor atual)")
        cur["POSTGRES_USER"] = input(f"  Usuário PostgreSQL [{cur['POSTGRES_USER']}]: ").strip() or cur["POSTGRES_USER"]
        cur["POSTGRES_DB"] = input(f"  Banco PostgreSQL [{cur['POSTGRES_DB']}]: ").strip() or cur["POSTGRES_DB"]
        cur["POSTGRES_PASSWORD"] = _ask_hidden("  Senha PostgreSQL [Enter mantém]: ") or cur["POSTGRES_PASSWORD"]
        cur["GRAFANA_PASSWORD"] = _ask_hidden("  Senha admin Grafana [Enter mantém]: ") or cur["GRAFANA_PASSWORD"]
        cur["S3_ACCESS_KEY"] = input(f"  MinIO access key [{cur['S3_ACCESS_KEY']}]: ").strip() or cur["S3_ACCESS_KEY"]
        cur["S3_SECRET_KEY"] = _ask_hidden("  MinIO secret key [Enter mantém]: ") or cur["S3_SECRET_KEY"]
        api_in = input(f"  API_KEY do servidor (opcional) [{'definido' if cur['API_KEY'] else 'vazio'}]: ").strip()
        cur["API_KEY"] = api_in or cur["API_KEY"]
        am = input(f"  Auth de equipe off/warn/enforce [{cur['AUTH_MODE']}]: ").strip().lower()
        if am in ("off", "warn", "enforce"):
            cur["AUTH_MODE"] = am

    # Credenciais embutidas na URL de conexão (Postgres/PgBouncer) não podem ter
    # caracteres que quebrem o parse — valida (re-pergunta no interativo).
    cur["POSTGRES_USER"] = _ensure_url_safe("Usuário PostgreSQL", cur["POSTGRES_USER"], interactive)
    cur["POSTGRES_DB"] = _ensure_url_safe("Banco PostgreSQL", cur["POSTGRES_DB"], interactive)
    cur["POSTGRES_PASSWORD"] = _ensure_url_safe(
        "Senha PostgreSQL", cur["POSTGRES_PASSWORD"], interactive, hidden=True)

    for k, v in cur.items():
        set_env(compose_env, k, v)
    insecure = [k for k in ("POSTGRES_PASSWORD", "GRAFANA_PASSWORD", "S3_SECRET_KEY")
                if cur[k] in ("mem0", "minioadmin")]
    if insecure:
        warn("Segredos ainda no default inseguro: " + ", ".join(insecure)
             + " — troque antes de expor para 200 devs.")
    return cur


def write_auth_tokens(api_env, value):
    """Grava AUTH_TOKENS (pares team:tok,...) em api/.env. `@arquivo` lê de arquivo."""
    if value.startswith("@"):
        p = Path(value[1:]).expanduser()
        if not p.is_file():
            die(f"Arquivo de tokens não encontrado: {p}")
        value = ",".join(l.strip() for l in p.read_text(encoding="utf-8").splitlines() if l.strip())
    set_env(api_env, "AUTH_TOKENS", value)


def run_production(args, compose_env, api_env, llm_spec, emb_spec):
    """Sobe o stack de escala completo (PostgreSQL/PgBouncer/Redis/Qdrant/workers/
    proxy/observabilidade/backup), roda migrations e valida /health."""
    def dc(*a, **k):
        return run(["docker", "compose", "-f", SCALE_COMPOSE, *a],
                   cwd=str(COMPOSE_DIR), **k)

    # Inferência + fail-closed -----------------------------------------------
    if llm_spec and emb_spec:
        log(f"Gravando inferência e flags de produção em {compose_env.relative_to(ROOT)}")
        public = write_inference_scale(compose_env, llm_spec, emb_spec, args)
        if public:
            warn("MEM0_LOCAL_ONLY=0: o conteúdo das memórias SAIRÁ para a API externa escolhida.")
        else:
            ok("MEM0_LOCAL_ONLY=1: inferência local — memórias não saem da rede.")
        ok(f"LLM={llm_spec['label']}/{llm_spec['model']} | "
           f"embedder={emb_spec['label']}/{emb_spec['model']}")

    # Porta do proxy / descoberta --------------------------------------------
    set_env(compose_env, "PROXY_PORT", str(args.proxy_port))

    discovery_url = discovery_base_url(args.proxy_port, args.discovery_url)
    set_env(compose_env, "OPENMEMORY_DISCOVERY_BASE_URL", discovery_url)
    ok(f"URL de descoberta/provision: {discovery_url}")

    # Segredos ----------------------------------------------------------------
    secrets = collect_secrets(args, compose_env, interactive=not args.yes)
    if args.auth_tokens:
        write_auth_tokens(api_env, args.auth_tokens)
        ok("Tokens de equipe gravados em api/.env (AUTH_TOKENS).")
    if secrets["AUTH_MODE"] == "enforce" and not (args.auth_tokens or read_env(api_env, "AUTH_TOKENS")):
        warn("AUTH_MODE=enforce sem tokens definidos — TODOS os acessos serão negados. "
             "Defina --auth-tokens 'time:token,...'.")

    # DATABASE_URL explícito no .env: mata o warning do compose e habilita o
    # serviço de backup (pg_dump) — usa as credenciais já validadas acima.
    set_env(compose_env, "DATABASE_URL",
            f"postgresql://{secrets['POSTGRES_USER']}:{secrets['POSTGRES_PASSWORD']}"
            f"@pgbouncer:5432/{secrets['POSTGRES_DB']}")

    # DOCKER_API_VERSION: alinha o cliente docker do Traefik com o daemon. Sem
    # isso, daemons recentes recusam a API antiga do Traefik e ele não descobre
    # rotas (404 em tudo).
    api_ver = docker_api_version()
    if api_ver:
        set_env(compose_env, "DOCKER_API_VERSION", api_ver)
        ok(f"Docker API {api_ver} fixada para o Traefik.")
    else:
        warn("Não detectei a versão da API do Docker; usando o default do compose (1.44).")

    try:
        user = os.environ.get("USER") or os.environ.get("USERNAME") or getpass.getuser()
    except Exception:
        user = "openmemory"
    set_env(compose_env, "USER", user)

    # Armazenamento -----------------------------------------------------------
    log("Definindo o local de salvamento (Qdrant)")
    configure_storage_scale(args.data_dir, interactive=not args.yes, compose_env=compose_env)

    # Orquestração ------------------------------------------------------------
    log("Subindo infraestrutura base (PostgreSQL, PgBouncer, Redis, Qdrant)")
    if dc("up", "-d", "postgres", "pgbouncer", "redis", "mem0_store").returncode != 0:
        die("Falha ao subir a infraestrutura base.")
    log("Aguardando o PgBouncer aceitar conexões")
    if not wait_for_pgbouncer(SCALE_COMPOSE):
        warn("PgBouncer não respondeu — logs do postgres e do pgbouncer abaixo:")
        dc("ps")
        dc("logs", "--tail", "60", "postgres", "pgbouncer")
        die("PgBouncer não ficou pronto a tempo. Causas comuns: senha do Postgres "
            "com caractere especial; volume mem0_pgdata antigo com outra senha "
            "(docker volume rm openmemory_mem0_pgdata para recriar — apaga dados).")
    ok("PgBouncer pronto.")
    log("Construindo a imagem da API")
    if dc("build", "openmemory-mcp").returncode != 0:
        die("Falha ao construir a imagem da API.")
    log("Aplicando migrations (alembic upgrade head)")
    if dc("run", "--rm", "--no-deps", "openmemory-mcp", "alembic", "upgrade", "head").returncode != 0:
        die("Falha ao aplicar as migrations no PostgreSQL.")
    ok("Schema do PostgreSQL criado/atualizado.")
    log("Subindo o stack completo")
    if dc("up", "-d", "--build").returncode != 0:
        die("Falha ao subir o stack completo (docker compose up).")

    log(f"Aguardando GET /health via proxy (até {args.timeout}s)")
    healthy, detail = wait_for_health(args.proxy_port, args.timeout)
    if not healthy:
        warn(f"Última resposta de /health: {detail}")
        dc("ps")
        dc("logs", "--tail", "60", "openmemory-mcp")
        die("/health não respondeu saudável a tempo (veja a resposta e os logs acima).")
    ok(f"/health saudável ({detail}).")

    log("Instalação de PRODUÇÃO concluída 🎉")
    print(f"""
  Proxy MCP:  http://localhost:{args.proxy_port}
  Descoberta: http://localhost:{args.proxy_port}/discovery
  Health:     http://localhost:{args.proxy_port}/health
  Qdrant:     http://localhost:6333
  Prometheus: http://localhost:9090
  Grafana:    http://localhost:3001  (admin / senha configurada)

  Stack: PostgreSQL + PgBouncer + Redis + Qdrant + workers (write/governance)
         + Traefik + observabilidade + backup (MinIO).
  Auth de equipe: AUTH_MODE={secrets['AUTH_MODE']} (defina tokens com --auth-tokens).

  Rota MCP (preencha hostname e project):
    /mcp/{{client_name}}/sse/{{hostname}}      (SSE)
    /mcp/{{client_name}}/http/{{hostname}}     (Streamable HTTP)""")
    return 0


def select_mode(args):
    """Decide entre instalação local-first e produção (escala)."""
    if args.mode in ("local", "production"):
        return args.mode
    if args.yes:
        return "local"  # compatibilidade: não-interativo sem --mode = local-first
    print("\n  Tipo de instalação:")
    print("    1. Local-first — 1 máquina/dev: SQLite + Qdrant (simples)")
    print("    2. Produção    — escala p/ time: PostgreSQL + Redis + workers + "
          "proxy + observabilidade + backup")
    c = input("  Selecione [1]: ").strip().lower()
    return "production" if c in ("2", "production", "prod", "producao", "produção") else "local"


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
def parse_args(argv):
    p = argparse.ArgumentParser(
        description="Instalador rápido local-first (multiplataforma).")
    p.add_argument("--backend", choices=("auto", "ollama", "llamacpp", "api"), default="auto",
                   help="Backend: auto (detecta locais), ollama, llamacpp ou "
                        "api (endpoint remoto compatível com OpenAI — use --api-url).")
    p.add_argument("--ollama-url", default=os.environ.get("OLLAMA_URL", "http://localhost:11434"),
                   help="Endpoint do Ollama para detecção (default http://localhost:11434).")
    p.add_argument("--llamacpp-url", default=os.environ.get("LLAMACPP_URL", "http://localhost:8080"),
                   help="Endpoint do servidor llama.cpp para detecção (default http://localhost:8080).")
    p.add_argument("--api-url", default=os.environ.get("API_BASE_URL"),
                   help="Base URL do endpoint remoto compatível com OpenAI "
                        "(backend api). Ex.: https://api.openai.com/v1")
    p.add_argument("--llm", help="Nome do modelo LLM (não-interativo; exige --embedder e --yes).")
    p.add_argument("--embedder", help="Nome do modelo embedder (idem).")
    p.add_argument("--api-key", default=None,
                   help="Token/API key do backend (LLM + embedder). "
                        "Vazio/omitido = sem token (Ollama não exige).")
    # Overrides por papel (não-interativo): permitem mixar, ex. Ollama no LLM e
    # API remota no embedder. Sem fallback → herdam --backend/--api-url/--api-key.
    p.add_argument("--llm-backend", choices=("ollama", "llamacpp", "api"), default=None,
                   help="Backend só do LLM (sobrepõe --backend).")
    p.add_argument("--embedder-backend", choices=("ollama", "llamacpp", "api"), default=None,
                   help="Backend só do embedder (sobrepõe --backend).")
    p.add_argument("--llm-api-url", default=None, help="Base URL da API só do LLM.")
    p.add_argument("--embedder-api-url", default=None, help="Base URL da API só do embedder.")
    p.add_argument("--llm-api-key", default=None, help="Token da API só do LLM.")
    p.add_argument("--embedder-api-key", default=None, help="Token da API só do embedder.")
    p.add_argument("--data-dir", default=None,
                   help="Diretório no host para salvar as memórias (Qdrant + SQLite). "
                        "Vazio/omitido = volumes Docker gerenciados (padrão).")
    p.add_argument("--yes", "-y", action="store_true", help="Não-interativo (usa --llm/--embedder).")
    p.add_argument("--skip-models", action="store_true", help="Não mexe nos modelos do .env.")
    # --- Atualização in-place (preserva memórias) -----------------------------
    p.add_argument("--update", action="store_true",
                   help="Atualiza a instalação existente para a versão nova "
                        "(git pull + rebuild + migrations) PRESERVANDO as memórias "
                        "e o .env. Não toca em volumes nem re-pergunta modelos/segredos.")
    p.add_argument("--no-pull", action="store_true",
                   help="No --update, não executa 'git pull' (usa o código já presente).")
    p.add_argument("--with-ui", action="store_true", help="Também sobe a UI (porta 3000) — só no modo local.")
    p.add_argument("--api-port", default=os.environ.get("API_PORT", "8765"))
    p.add_argument("--timeout", type=int, default=int(os.environ.get("TIMEOUT", "180")))
    # --- Modo de instalação ---------------------------------------------------
    p.add_argument("--mode", choices=("local", "production"), default=None,
                   help="local (SQLite+Qdrant, 1 máquina) ou production (stack de "
                        "escala completo). Omitido = pergunta (ou local com --yes).")
    p.add_argument("--proxy-port", default=os.environ.get("PROXY_PORT", "8765"),
                   help="Porta do reverse proxy (Traefik) no modo produção.")
    p.add_argument("--discovery-url", default=os.environ.get("OPENMEMORY_DISCOVERY_BASE_URL"),
                   help="URL base anunciada em /discovery e /provision (default: IP LAN desta máquina).")
    # Segredos de produção (prompt quando interativo; senão usa flag/env/default).
    p.add_argument("--postgres-user", default=os.environ.get("POSTGRES_USER"))
    p.add_argument("--postgres-password", default=os.environ.get("POSTGRES_PASSWORD"))
    p.add_argument("--postgres-db", default=os.environ.get("POSTGRES_DB"))
    p.add_argument("--grafana-password", default=os.environ.get("GRAFANA_PASSWORD"))
    p.add_argument("--minio-access-key", default=os.environ.get("S3_ACCESS_KEY"))
    p.add_argument("--minio-secret-key", default=os.environ.get("S3_SECRET_KEY"))
    p.add_argument("--server-api-key", default=os.environ.get("API_KEY"),
                   help="Valor de API_KEY exigido pelo servidor (opcional).")
    p.add_argument("--auth-mode", choices=("off", "warn", "enforce"), default=None,
                   help="Auth de equipe na borda (produção). Default: warn.")
    p.add_argument("--auth-tokens", default=None,
                   help="Tokens de equipe 'time:token,...' (ou @arquivo) p/ produção.")
    return p.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    raw_argv = argv if argv is not None else sys.argv
    # URLs foram dadas explicitamente (≠ default)?
    ollama_explicit = ("--ollama-url" in raw_argv) or bool(os.environ.get("OLLAMA_URL"))
    llamacpp_explicit = ("--llamacpp-url" in raw_argv) or bool(os.environ.get("LLAMACPP_URL"))
    # URL que o container usa p/ alcançar o backend no host (localhost não serve
    # de dentro do container): usa a informada ou o host.docker.internal.
    llamacpp_container_url = args.llamacpp_url if llamacpp_explicit else "http://host.docker.internal:8080"

    # Atualização in-place: preserva memórias e .env, não pergunta nada do fluxo
    # de instalação (modelos/segredos/storage). Curto-circuita aqui.
    if args.update:
        return run_update_entry(args)

    mode = select_mode(args)

    # 1. Pré-requisitos -------------------------------------------------------
    log("Verificando pré-requisitos")
    if not shutil.which("docker"):
        die("Docker não encontrado. Instale o Docker.")
    if not have_docker_compose():
        die("Docker Compose v2 não encontrado (use 'docker compose').")
    needed = SCALE_COMPOSE if mode == "production" else "docker-compose.yml"
    if not COMPOSE_DIR.is_dir() or not (COMPOSE_DIR / needed).is_file():
        die(f"{needed} não encontrado em {COMPOSE_DIR}.")
    ok(f"Docker e Docker Compose v2 disponíveis (modo: {mode}).")

    # 2. Arquivos .env --------------------------------------------------------
    log("Preparando arquivos de ambiente")
    api_env = COMPOSE_DIR / "api" / ".env"
    api_env_example = COMPOSE_DIR / "api" / ".env.example"
    compose_env = COMPOSE_DIR / ".env"
    if not api_env_example.is_file():
        die("openmemory/api/.env.example não encontrado.")
    if not api_env.exists():
        shutil.copy(api_env_example, api_env)
        ok(f"Criado {api_env.relative_to(ROOT)} a partir do exemplo.")
    else:
        ok(f"{api_env.relative_to(ROOT)} já existe (preservado).")
    compose_env.touch()

    # 3 + 4. Detecção/seleção de modelos (LLM + embedder, por papel) ---------
    llm_spec = emb_spec = None
    if args.skip_models:
        log("Detecção de modelos pulada (--skip-models): mantendo o .env atual.")
    else:
        llm_spec, emb_spec = resolve_specs(args, llamacpp_container_url, ollama_explicit)

    # 5. Produção: stack de escala completo (orquestração dedicada) ----------
    if mode == "production":
        return run_production(args, compose_env, api_env, llm_spec, emb_spec)

    # 5'. Local-first: grava a seleção e sobe o conjunto simples -------------
    if llm_spec and emb_spec:
        log(f"Gravando a seleção em {compose_env.relative_to(ROOT)}")
        write_role_env(compose_env, "LLM", llm_spec)
        write_role_env(compose_env, "EMBEDDER", emb_spec)
        # OLLAMA_BASE_URL é global: grava a URL explícita de qualquer papel Ollama.
        ollama_url = llm_spec.get("ollama_url") or emb_spec.get("ollama_url")
        if ollama_url:
            set_env(compose_env, "OLLAMA_BASE_URL", ollama_url)
        ok(f"LLM={llm_spec['label']}/{llm_spec['model']} | "
           f"embedder={emb_spec['label']}/{emb_spec['model']}")

    # USER / NEXT_PUBLIC_API_URL: ajudam a UI e silenciam avisos do compose.
    try:
        user = os.environ.get("USER") or os.environ.get("USERNAME") or getpass.getuser()
    except Exception:
        user = "openmemory"
    set_env(compose_env, "USER", user)
    discovery_url = discovery_base_url(args.api_port, args.discovery_url)
    set_env(compose_env, "OPENMEMORY_DISCOVERY_BASE_URL", discovery_url)
    ok(f"URL de descoberta/provision: {discovery_url}")
    set_env(compose_env, "NEXT_PUBLIC_API_URL", f"http://localhost:{args.api_port}")

    # Local de salvamento das memórias (Qdrant + SQLite) ---------------------
    log("Definindo o local de salvamento das memórias")
    configure_storage(args.data_dir, interactive=not args.yes, compose_env=compose_env)

    # Subir o conjunto --------------------------------------------------------
    services = ["mem0_store", "openmemory-mcp"]
    if args.with_ui:
        services.append("openmemory-ui")
    log("Subindo containers: " + " ".join(services))
    r = run(["docker", "compose", "up", "-d", "--build", *services], cwd=str(COMPOSE_DIR))
    if r.returncode != 0:
        die("Falha ao subir os containers (docker compose up).")

    # Validar a auto-descoberta ----------------------------------------------
    log(f"Aguardando GET /discovery (até {args.timeout}s)")
    if not wait_for_discovery(args.api_port, args.timeout):
        run(["docker", "compose", "logs", "--tail", "40", "openmemory-mcp"],
            cwd=str(COMPOSE_DIR))
        die("/discovery não respondeu a tempo.")
    ok("/discovery respondeu 200 com os campos esperados.")

    # Pronto ------------------------------------------------------------------
    log("Instalação local-first concluída 🎉")
    print(f"""
  API/MCP:    http://localhost:{args.api_port}
  Descoberta: http://localhost:{args.api_port}/discovery
  Qdrant:     http://localhost:6333""")
    if args.with_ui:
        print("  UI:         http://localhost:3000")
    print("""
  Rota MCP (preencha hostname e project):
    /mcp/{client_name}/sse/{hostname}      (SSE)
    /mcp/{client_name}/http/{hostname}     (Streamable HTTP)

  Os agentes na rede local podem se autoconfigurar via GET /discovery.""")
    return 0


if __name__ == "__main__":
    sys.exit(main())
