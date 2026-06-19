#!/usr/bin/env python3
"""Desinstalador DESTRUTIVO da Memória Central Compartilhada (multiplataforma).

Remove TUDO que o install.py / bootstrap-scale.sh criam, sem deixar rastro do
projeto na máquina:

  • containers, redes e volumes dos dois stacks (docker-compose.yml e
    docker-compose.scale.yml — este último inclui Postgres/Redis/proxy/etc.);
  • imagens usadas/buildadas (qdrant, postgres, pgbouncer, redis, traefik,
    prometheus, grafana, otel, tempo, minio e as mem0/openmemory-*);
  • volumes nomeados (mem0_storage, mem0_db, mem0_pgdata, minio_data,
    ollama_*_data) e os dados em disco do Qdrant/SQLite (inclusive --data-dir);
  • arquivos gerados (openmemory/.env, openmemory/api/.env, SQLite, tokens).

ATENCAO: operação IRREVERSÍVEL — apaga os dados das memórias. Por padrão pede
    confirmação; use --yes para pular (automação).

Uso:
  python uninstall.py                 # interativo, pede confirmação
  python uninstall.py --yes           # não-interativo
  python uninstall.py --prune         # + docker system prune -af --volumes
                                      #   (AFETA TODO o Docker, não só este projeto)
  python uninstall.py --keep-images   # não remove imagens
  python uninstall.py --purge-repo    # também apaga o diretório do repositório
"""

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
COMPOSE_DIR = ROOT / "openmemory"

COMPOSE_FILES = ["docker-compose.yml", "docker-compose.scale.yml"]
PROJECT = "openmemory"  # nome do projeto compose (= basename de COMPOSE_DIR)
KNOWN_VOLUMES = ["mem0_storage", "mem0_db", "mem0_pgdata",
                 "minio_data", "ollama_embed_data", "ollama_llm_data"]
BUILT_IMAGES = ["mem0/openmemory-mcp", "mem0/openmemory-ui"]


def log(msg):  print("\n==> " + msg)
def ok(msg):   print("  [ok] " + msg)
def warn(msg): print("  [!] " + msg)
def die(msg):  print("  [x] " + msg, file=sys.stderr); sys.exit(1)


def run(cmd, **kwargs):
    """Roda um subprocesso; nunca levanta (best-effort). Retorna o returncode."""
    try:
        return subprocess.run(cmd, **kwargs).returncode
    except FileNotFoundError:
        return 127


def have_docker():
    return shutil.which("docker") is not None and \
        run(["docker", "compose", "version"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) == 0


def read_env(file_path, key):
    """Lê o valor de KEY num .env (ou None)."""
    if not file_path.exists():
        return None
    prefix = key + "="
    for line in file_path.read_text(encoding="utf-8", errors="replace").splitlines():
        s = line.strip()
        if s.startswith(prefix):
            return s[len(prefix):].strip()
    return None


def parse_args(argv):
    p = argparse.ArgumentParser(description="Desinstalador destrutivo (multiplataforma).")
    p.add_argument("--yes", "-y", action="store_true", help="Não pergunta (automação).")
    p.add_argument("--prune", action="store_true",
                   help="Roda docker system prune -af --volumes (AFETA TODO o Docker).")
    p.add_argument("--keep-images", action="store_true", help="Não remove imagens.")
    p.add_argument("--purge-repo", action="store_true",
                   help="Também apaga o diretório do repositório ao final.")
    return p.parse_args(argv)


def confirm(args):
    if args.yes:
        return
    print(__doc__.split("Uso:")[0].rstrip())
    print("\n  Isto vai DESTRUIR containers, volumes, imagens e dados deste projeto.")
    if args.prune:
        print("  --prune: também roda 'docker system prune -af --volumes' (TODO o Docker!).")
    if args.purge_repo:
        print(f"  --purge-repo: também apaga {ROOT}")
    resp = input("\n  Para confirmar, digite DESTRUIR: ").strip()
    if resp != "DESTRUIR":
        die("Cancelado (confirmação não recebida).")


def compose_down(args):
    """docker compose down -v --remove-orphans [--rmi all] nos dois stacks."""
    if not COMPOSE_DIR.is_dir():
        warn(f"{COMPOSE_DIR} não existe — pulando 'compose down'.")
        return
    for f in COMPOSE_FILES:
        if not (COMPOSE_DIR / f).is_file():
            continue
        log(f"Derrubando o stack ({f})")
        cmd = ["docker", "compose", "-f", f]
        # --profile *: garante que serviços opt-in (local-inference, alerts,
        # backup, migration) também sejam removidos.
        for prof in ("local-inference", "alerts", "backup", "migration"):
            cmd += ["--profile", prof]
        cmd += ["down", "--volumes", "--remove-orphans"]
        if not args.keep_images:
            cmd += ["--rmi", "all"]
        run(cmd, cwd=str(COMPOSE_DIR))
    ok("Containers, redes e volumes do compose removidos.")


def remove_named_volumes():
    log("Removendo volumes nomeados remanescentes")
    # Por label do projeto (cobre nomes prefixados independentemente do projeto).
    try:
        out = subprocess.run(
            ["docker", "volume", "ls", "--filter",
             f"label=com.docker.compose.project={PROJECT}", "-q"],
            capture_output=True, text=True).stdout.split()
    except Exception:
        out = []
    names = set(out)
    for v in KNOWN_VOLUMES:
        names.add(v)
        names.add(f"{PROJECT}_{v}")
    removed = 0
    for name in sorted(n for n in names if n):
        if run(["docker", "volume", "rm", "-f", name],
               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) == 0:
            removed += 1
    ok(f"{removed} volume(s) nomeado(s) removido(s).")


def remove_images():
    log("Removendo imagens buildadas do projeto")
    for img in BUILT_IMAGES:
        run(["docker", "image", "rm", "-f", img],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    ok("Imagens mem0/openmemory-* removidas (se existiam).")


def remove_host_data():
    """Apaga dados em disco: --data-dir (Qdrant/SQLite) e o SQLite local-first."""
    log("Apagando dados em disco")
    compose_env = COMPOSE_DIR / ".env"
    targets = []
    for key in ("QDRANT_STORAGE", "SQLITE_STORAGE"):
        val = read_env(compose_env, key)
        # Só caminhos de host (default são nomes de volume: 'mem0_storage'/'mem0_db').
        if val and ("/" in val or "\\" in val or ":" in val[1:3]):
            targets.append(Path(val))
    # SQLite local-first (bind mount ./api -> /usr/src/openmemory).
    api_dir = COMPOSE_DIR / "api"
    for fn in ("openmemory.db", "openmemory.db-wal", "openmemory.db-shm"):
        targets.append(api_dir / fn)
    n = 0
    for t in targets:
        try:
            if t.is_dir():
                shutil.rmtree(t, ignore_errors=True); n += 1
            elif t.exists():
                t.unlink(); n += 1
        except OSError as e:
            warn(f"Não consegui remover {t}: {e}")
    ok(f"{n} caminho(s) de dados removido(s).")


def remove_generated_files():
    log("Removendo arquivos gerados")
    files = [COMPOSE_DIR / ".env", COMPOSE_DIR / "api" / ".env",
             Path("/tmp/om_tags.json")]
    n = 0
    for f in files:
        try:
            if f.exists():
                f.unlink(); n += 1
        except OSError as e:
            warn(f"Não consegui remover {f}: {e}")
    ok(f"{n} arquivo(s) gerado(s) removido(s).")


def docker_prune():
    log("docker system prune -af --volumes (TODO o Docker)")
    run(["docker", "system", "prune", "-af", "--volumes"])
    ok("Prune global concluído.")


def purge_repo():
    log(f"Apagando o diretório do repositório: {ROOT}")
    # No POSIX o processo continua mesmo após o arquivo ser removido.
    shutil.rmtree(ROOT, ignore_errors=True)
    if ROOT.exists():
        warn(f"Sobrou conteúdo em {ROOT} — remova manualmente: rm -rf '{ROOT}'")
    else:
        ok("Repositório removido.")


def main(argv=None):
    args = parse_args(argv)
    if not have_docker():
        warn("Docker/Compose não encontrado — só vou limpar arquivos e dados em disco.")
    confirm(args)

    if have_docker():
        compose_down(args)
        remove_named_volumes()
        if not args.keep_images:
            remove_images()
    remove_host_data()
    remove_generated_files()
    if args.prune and have_docker():
        docker_prune()

    log("Desinstalação concluída.")
    print("""
  Removido: containers, redes, volumes, imagens, dados (Qdrant/SQLite/Postgres),
  e os arquivos .env gerados. Nenhum dado das memórias permanece.

  Conferir sobras (devem vir vazios):
    docker ps -a | grep -E 'openmemory|mem0_store'
    docker volume ls | grep -E 'mem0|minio|ollama'
    docker image ls | grep -E 'openmemory|mem0'""")
    if args.purge_repo:
        purge_repo()
    else:
        print(f"\n  O repositório em {ROOT} foi PRESERVADO. Para removê-lo:")
        print(f"    rm -rf '{ROOT}'    (ou rode com --purge-repo)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
