#!/usr/bin/env python3
"""Instalador rápido LOCAL-FIRST da Memória Central Compartilhada (multiplataforma).

Roda em Linux, macOS e Windows (só precisa de Python 3.8+ e Docker). Equivalente
multiplataforma ao ``openmemory/install-local-first.sh``: sobe API/MCP + Qdrant em
container e usa um Ollama LOCAL para LLM/embeddings — operação 100% local, sem
dependência de serviços fora da rede (privacidade).

Faz, ponta a ponta:
  1. Verifica pré-requisitos (Docker + Docker Compose v2).
  2. Garante os arquivos .env (compose + api).
  3. Detecta os modelos do Ollama (GET /api/tags) e deixa você escolher o LLM e o
     embedder — sem download automático (task_09); fallback para entrada manual.
  4. Persiste a seleção no .env do compose (interpolado no docker-compose.yml).
  5. Sobe o conjunto (docker compose up -d) — o schema é criado no startup.
  6. Valida a auto-descoberta (GET /discovery) e imprime os dados de conexão.

Uso:
  python install.py                                   # interativo
  python install.py --ollama-url http://192.168.0.10:11434
  python install.py --llm llama3.1:latest --embedder nomic-embed-text --yes
  python install.py --api-key SEU_TOKEN               # token do backend local (opcional)
  # LLM no Ollama + embedder numa API remota (papéis independentes):
  python install.py --yes --llm llama3.1:latest --llm-backend ollama \\
      --embedder text-embedding-3-small --embedder-backend api \\
      --embedder-api-url https://api.openai.com/v1 --embedder-api-key SEU_TOKEN
  python install.py --data-dir /srv/mem0-data         # salva Qdrant + SQLite nesse caminho
  python install.py --skip-models                     # mantém modelos do .env atual
  python install.py --with-ui                         # também sobe a UI (porta 3000)
"""

import argparse
import getpass
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

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
    url = f"http://localhost:{api_port}/discovery"
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
    p.add_argument("--with-ui", action="store_true", help="Também sobe a UI (porta 3000).")
    p.add_argument("--api-port", default=os.environ.get("API_PORT", "8765"))
    p.add_argument("--timeout", type=int, default=int(os.environ.get("TIMEOUT", "180")))
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

    # 1. Pré-requisitos -------------------------------------------------------
    log("Verificando pré-requisitos")
    if not shutil.which("docker"):
        die("Docker não encontrado. Instale o Docker.")
    if not have_docker_compose():
        die("Docker Compose v2 não encontrado (use 'docker compose').")
    if not COMPOSE_DIR.is_dir() or not (COMPOSE_DIR / "docker-compose.yml").is_file():
        die(f"docker-compose.yml não encontrado em {COMPOSE_DIR}.")
    ok("Docker e Docker Compose v2 disponíveis.")

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

    # 3 + 4. Detecção/seleção de modelos (Ollama + llama.cpp) ----------------
    if args.skip_models:
        log("Detecção de modelos pulada (--skip-models): mantendo o .env atual.")
    else:
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

        # LLM e embedder são resolvidos de forma INDEPENDENTE: cada um pode usar
        # um backend local (Ollama/llama.cpp) ou uma API remota — inclusive
        # combinando os dois (ex.: Ollama no LLM, API no embedder).
        if args.yes:
            llm_spec = spec_from_flags("LLM", args, llamacpp_container_url, ollama_explicit)
            emb_spec = spec_from_flags("embedder", args, llamacpp_container_url, ollama_explicit)
        else:
            llm_spec = resolve_role("LLM", available, args, labels,
                                    llamacpp_container_url, ollama_explicit, {})
            # Se o LLM usou uma API, oferece reaproveitar URL/token no embedder.
            api_defaults = {"base_url": llm_spec["base_url"], "api_key": llm_spec["api_key"]} \
                if llm_spec["is_api"] else {}
            emb_spec = resolve_role("embedder", available, args, labels,
                                    llamacpp_container_url, ollama_explicit, api_defaults)

        if not llm_spec["model"]:
            die("Modelo LLM não definido.")
        if not emb_spec["model"]:
            die("Modelo embedder não definido.")

        # API remota: só prossegue se o endpoint do papel responder (conexão+auth).
        for role, spec in (("llm", llm_spec), ("embedder", emb_spec)):
            if spec["is_api"]:
                log(f"Testando conexão com a API ({role})")
                ok_conn, msg = test_remote_api(
                    spec["base_url"], spec["api_key"], spec["model"], role)
                if not ok_conn:
                    die(f"Teste de conexão da API ({role}) falhou: {msg}")
                ok(msg)

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
    set_env(compose_env, "NEXT_PUBLIC_API_URL", f"http://localhost:{args.api_port}")

    # 4b. Local de salvamento das memórias (Qdrant + SQLite) -----------------
    log("Definindo o local de salvamento das memórias")
    configure_storage(args.data_dir, interactive=not args.yes, compose_env=compose_env)

    # 5. Subir o conjunto -----------------------------------------------------
    services = ["mem0_store", "openmemory-mcp"]
    if args.with_ui:
        services.append("openmemory-ui")
    log("Subindo containers: " + " ".join(services))
    r = run(["docker", "compose", "up", "-d", "--build", *services], cwd=str(COMPOSE_DIR))
    if r.returncode != 0:
        die("Falha ao subir os containers (docker compose up).")

    # 6. Validar a auto-descoberta -------------------------------------------
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
