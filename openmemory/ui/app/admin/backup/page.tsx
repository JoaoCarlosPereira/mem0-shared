"use client";

import { useEffect, useState } from "react";
import { useSelector } from "react-redux";
import { HardDrive, AlertTriangle, RotateCcw, Play } from "lucide-react";
import { Button } from "@/components/ui/button";
import { RootState } from "@/store/store";
import { BackupPolicy } from "@/store/backupSlice";
import { useBackupApi } from "@/hooks/useBackupApi";
import { canRestore, isStale, isValidRetention } from "@/lib/backup";

const DEFAULT_POLICY: BackupPolicy = {
  enabled: false,
  frequency: "daily",
  run_at: "03:00",
  timezone: "America/Sao_Paulo",
  local_dir: "/mnt/dados/backups",
  retention: 5,
  mirror_s3: false,
};

export default function BackupPage() {
  const { fetchStatus, fetchList, fetchPolicy, savePolicy, runBackup, restore } =
    useBackupApi();
  const status = useSelector((s: RootState) => s.backup.status);
  const archives = useSelector((s: RootState) => s.backup.archives);
  const policy = useSelector((s: RootState) => s.backup.policy);
  const error = useSelector((s: RootState) => s.backup.error);
  const loading = useSelector((s: RootState) => s.backup.loading);

  const [form, setForm] = useState<BackupPolicy>(DEFAULT_POLICY);
  const [selected, setSelected] = useState<string>("");
  const [confirmText, setConfirmText] = useState<string>("");

  useEffect(() => {
    fetchPolicy();
    fetchStatus();
    fetchList();
  }, [fetchPolicy, fetchStatus, fetchList]);

  useEffect(() => {
    if (policy) setForm(policy);
  }, [policy]);

  const stale = isStale(status?.rpo_age_seconds ?? null);

  return (
    <div className="flex flex-col gap-6 p-6 text-zinc-200">
      <h1 className="flex items-center gap-2 text-xl font-semibold">
        <HardDrive className="h-5 w-5" /> Backup
      </h1>

      {error && (
        <div role="alert" className="rounded-md bg-red-950 px-3 py-2 text-sm text-red-300">
          {error}
        </div>
      )}

      {/* Status / RPO */}
      <section
        data-testid="backup-status"
        className={`rounded-lg border p-4 ${
          stale ? "border-amber-600 bg-amber-950/30" : "border-zinc-800 bg-zinc-950"
        }`}
      >
        <div className="mb-2 flex items-center justify-between">
          <h2 className="font-medium">Status</h2>
          {stale && (
            <span className="flex items-center gap-1 text-sm text-amber-400">
              <AlertTriangle className="h-4 w-4" /> Backup desatualizado
            </span>
          )}
        </div>
        <dl className="grid grid-cols-2 gap-2 text-sm sm:grid-cols-4">
          <div>
            <dt className="text-zinc-500">Último backup</dt>
            <dd>{status?.last_backup ?? "—"}</dd>
          </div>
          <div>
            <dt className="text-zinc-500">Idade (RPO)</dt>
            <dd>
              {status?.rpo_age_seconds != null
                ? `${Math.round(status.rpo_age_seconds / 3600)}h`
                : "—"}
            </dd>
          </div>
          <div>
            <dt className="text-zinc-500">Cópias</dt>
            <dd>{status?.archives ?? 0}</dd>
          </div>
          <div>
            <dt className="text-zinc-500">Último erro</dt>
            <dd>{status?.last_error ?? "—"}</dd>
          </div>
        </dl>
        <Button className="mt-3" disabled={loading} onClick={() => runBackup()}>
          <Play className="mr-1 h-4 w-4" />{" "}
          {loading ? "Backup em andamento…" : "Fazer backup agora"}
        </Button>
      </section>

      {/* Política */}
      <section className="rounded-lg border border-zinc-800 bg-zinc-950 p-4">
        <h2 className="mb-3 font-medium">Configuração</h2>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={form.enabled}
              onChange={(e) => setForm({ ...form, enabled: e.target.checked })}
            />
            Backup automático ativado
          </label>
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={form.mirror_s3}
              onChange={(e) => setForm({ ...form, mirror_s3: e.target.checked })}
            />
            Espelhar no S3/MinIO
          </label>
          <label className="text-sm">
            Frequência
            <select
              aria-label="Frequência"
              className="mt-1 w-full rounded bg-zinc-900 p-2"
              value={form.frequency}
              onChange={(e) =>
                setForm({ ...form, frequency: e.target.value as BackupPolicy["frequency"] })
              }
            >
              <option value="daily">Diário</option>
              <option value="weekly">Semanal</option>
            </select>
          </label>
          <label className="text-sm">
            Horário (HH:MM)
            <input
              aria-label="Horário"
              className="mt-1 w-full rounded bg-zinc-900 p-2"
              value={form.run_at}
              onChange={(e) => setForm({ ...form, run_at: e.target.value })}
            />
          </label>
          <label className="text-sm">
            Diretório local (no host)
            <input
              aria-label="Diretório local"
              className="mt-1 w-full rounded bg-zinc-900 p-2"
              value={form.local_dir}
              onChange={(e) => setForm({ ...form, local_dir: e.target.value })}
            />
            <span className="mt-1 block text-xs text-zinc-500">
              Caminho no servidor (ex.: /mnt/dados/backups). Deve coincidir com
              LOCAL_BACKUP_DIR no compose.
            </span>
          </label>
          <label className="text-sm">
            Cópias retidas
            <input
              aria-label="Cópias retidas"
              type="number"
              min={1}
              max={50}
              className="mt-1 w-full rounded bg-zinc-900 p-2"
              value={form.retention}
              onChange={(e) =>
                setForm({ ...form, retention: Number(e.target.value) })
              }
            />
          </label>
        </div>
        <Button
          className="mt-3"
          disabled={!isValidRetention(form.retention)}
          onClick={() => savePolicy(form)}
        >
          Salvar configuração
        </Button>
      </section>

      {/* Restore guiado */}
      <section className="rounded-lg border border-zinc-800 bg-zinc-950 p-4">
        <h2 className="mb-1 font-medium">Restaurar</h2>
        <p className="mb-3 flex items-center gap-1 text-sm text-amber-400">
          <AlertTriangle className="h-4 w-4" /> O restore sobrescreve o estado atual.
          Um snapshot de segurança é criado automaticamente antes.
        </p>
        <label className="text-sm">
          Backup
          <select
            aria-label="Backup para restaurar"
            className="mt-1 w-full rounded bg-zinc-900 p-2"
            value={selected}
            onChange={(e) => {
              setSelected(e.target.value);
              setConfirmText("");
            }}
          >
            <option value="">Selecione…</option>
            {archives.map((a) => (
              <option key={`${a.location}:${a.name}`} value={a.name}>
                {a.name} ({a.location})
              </option>
            ))}
          </select>
        </label>
        <label className="mt-2 block text-sm">
          Digite o nome do backup para confirmar
          <input
            aria-label="Confirmação"
            className="mt-1 w-full rounded bg-zinc-900 p-2"
            value={confirmText}
            onChange={(e) => setConfirmText(e.target.value)}
          />
        </label>
        <Button
          variant="destructive"
          className="mt-3"
          disabled={!canRestore(confirmText, selected)}
          onClick={() => restore(selected, confirmText)}
        >
          <RotateCcw className="mr-1 h-4 w-4" /> Restaurar
        </Button>
      </section>
    </div>
  );
}
