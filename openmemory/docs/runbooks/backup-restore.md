# Runbook — Backup e Restauração (drill)

> Prontidão para produção, task_02/task_03 — ADR-003. Alvo LAN single-node.
> Objetivo de recuperação: **RPO ≤ 24h**, **RTO ≤ 1h**.

## Componentes

- **MinIO** (object store S3-compatível) — espelho opcional dos `.zip` (`mirror_s3` na política). Serviço `minio` em `compose/backup.yml`.
- **Backup unificado** — `BackupArchive.create()` (UI `/admin/backup`, worker `openmemory-backup-worker`, ou `POST /admin/backup/run`): um `.zip` com snapshot Qdrant + `pg_dump` + anexos Spec/PLANKA.
- **Endpoints** — `POST /admin/backup/run`, `GET /admin/backup/status`, `GET /admin/backup/list`, `POST /admin/backup/restore`, `GET|PUT /admin/backup/policy`.
- **Schema `agentregistry`** — catálogo da loja interna no **mesmo** PostgreSQL `openmemory` (schema `agentregistry`). O `pg_dump` **já inclui** esse schema e o schema `planka` (quadros).
- **Anexos (volumes FS)** — `spec_attachments` → `/mnt/spec-attachments` e `planka_attachments` → `/mnt/planka-attachments` (montados em `openmemory-mcp` e `openmemory-backup-worker`). Empacotados como `attachments/spec.tar.gz` e `attachments/planka.tar.gz`. **Nunca** no Qdrant / `mem0_storage`.

Conteúdo do `.zip`:
```
manifest.json
qdrant/{collection}.snapshot
postgres/dump.sql.gz
attachments/spec.tar.gz
attachments/planka.tar.gz
```

Espelho S3 (quando `mirror_s3`): chave `archives/{timestamp}.zip`.

## Variáveis de ambiente

| Variável | Descrição | Default |
|----------|-----------|---------|
| `S3_ENDPOINT` | URL do MinIO/S3 | `http://minio:9000` |
| `S3_BUCKET` | Bucket de backups | `mem0-backups` |
| `S3_ACCESS_KEY` / `S3_SECRET_KEY` | Credenciais | (definir no `.env`) |
| `QDRANT_HOST` / `QDRANT_PORT` | Qdrant | `mem0_store` / `6333` |
| `DATABASE_URL` | PostgreSQL | — |
| `SPEC_ATTACHMENTS_DIR` | Raiz anexos Spec | `/mnt/spec-attachments` |
| `PLANKA_ATTACHMENTS_DIR` | Raiz anexos PLANKA (mesmo volume que `/app/data` no sidecar) | `/mnt/planka-attachments` |
| `LOCAL_BACKUP_DIR` | Dir no host montado em `/mnt/backups` | `./backups` |

## Backup agendado

Na UI `/admin/backup`: ative **Backup automático**, configure frequência/horário e, para DR off-host, **Espelhar no S3/MinIO**. O worker `openmemory-backup-worker` lê a política e dispara `BackupArchive.create()`.

Alternativa one-shot:
```bash
curl -X POST localhost:8765/admin/backup/run -H "Authorization: Bearer $ADMIN_TOKEN"
```

Verifique `GET /admin/backup/status` — `rpo_age_seconds` deve ficar abaixo de 86400 (24h).

## Drill de restauração (executar periodicamente)

1. **Pré-condição**: anote `GET /admin/backup/status` / `GET /admin/backup/list` (último `.zip`, idade).
2. **Marque o tempo de início** (para medir o RTO).
3. **Suba um ambiente de restauração** (não o de produção) com os mesmos volumes Postgres/Qdrant/anexos alvo.
4. **Dispare a restauração** pelo nome do arquivo:
   ```bash
   curl -X POST localhost:8765/admin/backup/restore \
     -H 'content-type: application/json' \
     -H "Authorization: Bearer $ADMIN_TOKEN" \
     -d '{"archive":"20260803-020229.zip","confirm":"20260803-020229.zip"}'
   ```
   - Arquivo inexistente → **404**; `confirm` divergente → **400**.
   - Um `pre-restore-*.zip` de segurança é criado automaticamente antes de sobrescrever.
   - Ordem: PostgreSQL → Qdrant → anexos.
5. **Valide**:
   - Contagem de memórias no Qdrant confere com a origem.
   - Spec/Kanban + loja (`agentregistry`) e quadros (`planka`) via Postgres.
   - Arquivos em `/mnt/spec-attachments` e `/mnt/planka-attachments` (ou volume PLANKA `/app/data`).
   - `GET /health` retorna `healthy`.
6. **Marque o tempo de fim** e registre **RTO** (alvo ≤ 1h) e **RPO** (idade do backup usado, alvo ≤ 24h).

> Zips antigos (sem `attachments/*.tar.gz`) ainda restauram Qdrant + Postgres; anexos são skip.

## Registro do último drill

| Data | RPO medido | RTO medido | Resultado |
|------|------------|------------|-----------|
| _preencher após o primeiro drill em ambiente real_ | | | |

> Orquestração coberta por testes em `tests/test_backup_archive.py`, `tests/test_backup_restore.py`, `tests/test_backup_attachments.py`. Medição de RTO/RPO só é válida em execução real.
