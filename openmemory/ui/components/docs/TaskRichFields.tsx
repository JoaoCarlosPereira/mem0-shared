"use client";

import { useCallback, useEffect, useState } from "react";
import { Paperclip } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import type {
  Checklist,
  TaskAttachment,
  TaskCard,
  TaskLabel,
} from "@/types/specs";

export type TaskRichApi = {
  listLabels: (wsId: string) => Promise<TaskLabel[]>;
  listTaskLabels: (taskId: string) => Promise<TaskLabel[]>;
  createLabel: (
    wsId: string,
    payload: { name: string; color?: string | null },
  ) => Promise<TaskLabel>;
  attachLabel: (taskId: string, labelId: string) => Promise<TaskCard>;
  detachLabel: (taskId: string, labelId: string) => Promise<void>;
  listChecklists: (taskId: string) => Promise<Checklist[]>;
  createChecklist: (taskId: string, title?: string) => Promise<Checklist>;
  createChecklistItem: (
    checklistId: string,
    title: string,
  ) => Promise<unknown>;
  patchChecklistItem: (
    checklistId: string,
    itemId: string,
    payload: { is_completed?: boolean; title?: string },
  ) => Promise<unknown>;
  listAttachments: (taskId: string) => Promise<TaskAttachment[]>;
  uploadAttachment: (taskId: string, file: File) => Promise<TaskAttachment>;
  deleteAttachment: (attachmentId: string) => Promise<void>;
  attachmentDownloadUrl: (attachmentId: string) => string;
};

type Props = {
  task: TaskCard;
  workspaceId: string;
  api: TaskRichApi;
  dueAt: string;
  membersText: string;
  onDueAtChange: (value: string) => void;
  onMembersTextChange: (value: string) => void;
  busy?: boolean;
};

/**
 * Painel de campos ricos do card (labels, checklists, anexos, due, members).
 * Consome somente /api/v1/specs (ADR-006).
 */
export function TaskRichFields({
  task,
  workspaceId,
  api,
  dueAt,
  membersText,
  onDueAtChange,
  onMembersTextChange,
  busy,
}: Props) {
  const [labels, setLabels] = useState<TaskLabel[]>([]);
  const [attachedIds, setAttachedIds] = useState<Set<string>>(new Set());
  const [checklists, setChecklists] = useState<Checklist[]>([]);
  const [attachments, setAttachments] = useState<TaskAttachment[]>([]);
  const [newLabel, setNewLabel] = useState("");
  const [newItemByChecklist, setNewItemByChecklist] = useState<
    Record<string, string>
  >({});
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const reload = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const seedIds =
        task.label_ids?.length
          ? task.label_ids
          : (task.labels || []).map((l) => l.id);
      if (seedIds.length) {
        setAttachedIds(new Set(seedIds));
      }

      const [wsLabels, taskLabels, cls, atts] = await Promise.all([
        api.listLabels(workspaceId),
        api.listTaskLabels(task.id),
        api.listChecklists(task.id),
        api.listAttachments(task.id),
      ]);
      setLabels(wsLabels);
      setAttachedIds(new Set(taskLabels.map((l) => l.id)));
      setChecklists(cls);
      setAttachments(atts);
    } catch (err: any) {
      setError(err?.message || "Falha ao carregar campos ricos");
    } finally {
      setLoading(false);
    }
  }, [
    api,
    workspaceId,
    task.id,
    task.label_ids,
    task.labels,
  ]);

  useEffect(() => {
    void reload();
  }, [task.id, reload]);

  const onCreateLabel = async () => {
    const name = newLabel.trim();
    if (!name) return;
    setError(null);
    try {
      const label = await api.createLabel(workspaceId, { name });
      setLabels((prev) => [...prev, label]);
      setNewLabel("");
    } catch (err: any) {
      setError(err?.message || "Falha ao criar label");
    }
  };

  const onToggleLabel = async (label: TaskLabel) => {
    setError(null);
    try {
      if (attachedIds.has(label.id)) {
        await api.detachLabel(task.id, label.id);
        setAttachedIds((prev) => {
          const next = new Set(prev);
          next.delete(label.id);
          return next;
        });
      } else {
        await api.attachLabel(task.id, label.id);
        setAttachedIds((prev) => new Set(prev).add(label.id));
      }
    } catch (err: any) {
      setError(err?.message || "Falha ao associar label");
    }
  };

  const onAddChecklist = async () => {
    setError(null);
    try {
      const cl = await api.createChecklist(task.id, "Checklist");
      setChecklists((prev) => [...prev, { ...cl, items: cl.items || [] }]);
    } catch (err: any) {
      setError(err?.message || "Falha ao criar checklist");
    }
  };

  const onAddItem = async (checklistId: string) => {
    const title = (newItemByChecklist[checklistId] || "").trim();
    if (!title) return;
    setError(null);
    try {
      await api.createChecklistItem(checklistId, title);
      setNewItemByChecklist((prev) => ({ ...prev, [checklistId]: "" }));
      const cls = await api.listChecklists(task.id);
      setChecklists(cls);
    } catch (err: any) {
      setError(err?.message || "Falha ao adicionar item");
    }
  };

  const onToggleItem = async (
    checklistId: string,
    itemId: string,
    isCompleted: boolean,
  ) => {
    setError(null);
    try {
      await api.patchChecklistItem(checklistId, itemId, {
        is_completed: !isCompleted,
      });
      setChecklists((prev) =>
        prev.map((cl) =>
          cl.id !== checklistId
            ? cl
            : {
                ...cl,
                items: cl.items.map((it) =>
                  it.id === itemId
                    ? { ...it, is_completed: !isCompleted }
                    : it,
                ),
              },
        ),
      );
    } catch (err: any) {
      setError(err?.message || "Falha ao atualizar item");
    }
  };

  const onUpload = async (fileList: FileList | null) => {
    const file = fileList?.[0];
    if (!file) return;
    setError(null);
    try {
      const att = await api.uploadAttachment(task.id, file);
      setAttachments((prev) => [...prev, att]);
    } catch (err: any) {
      setError(err?.message || "Falha no upload");
    }
  };

  const onDeleteAtt = async (id: string) => {
    setError(null);
    try {
      await api.deleteAttachment(id);
      setAttachments((prev) => prev.filter((a) => a.id !== id));
    } catch (err: any) {
      setError(err?.message || "Falha ao remover anexo");
    }
  };

  return (
    <div
      className="space-y-4 rounded-md border border-border bg-card/40 p-3"
      data-testid="task-rich-fields"
    >
      {error && (
        <p className="text-sm text-destructive" role="alert">
          {error}
        </p>
      )}
      {loading && (
        <p className="text-xs text-muted-foreground">Carregando…</p>
      )}

      <div className="grid gap-3 sm:grid-cols-2">
        <div className="space-y-1">
          <Label htmlFor="task-due">Prazo</Label>
          <Input
            id="task-due"
            type="datetime-local"
            value={dueAt}
            onChange={(e) => onDueAtChange(e.target.value)}
            disabled={busy}
            className="border-border bg-background"
            data-testid="task-due-input"
          />
        </div>
        <div className="space-y-1">
          <Label htmlFor="task-members">Membros (vírgula)</Label>
          <Input
            id="task-members"
            value={membersText}
            onChange={(e) => onMembersTextChange(e.target.value)}
            disabled={busy}
            placeholder="alice, bob"
            className="border-border bg-background"
            data-testid="task-members-input"
          />
        </div>
      </div>

      <div className="space-y-2">
        <div className="flex items-center justify-between gap-2">
          <Label>Labels</Label>
          <div className="flex gap-1">
            <Input
              value={newLabel}
              onChange={(e) => setNewLabel(e.target.value)}
              placeholder="nova label"
              className="h-8 w-32 border-border bg-background text-xs"
              data-testid="task-label-new"
            />
            <Button
              type="button"
              size="sm"
              variant="outline"
              className="h-8"
              onClick={onCreateLabel}
              data-testid="task-label-create"
            >
              +
            </Button>
          </div>
        </div>
        <div className="flex flex-wrap gap-1" data-testid="task-labels-list">
          {labels.map((label) => {
            const on = attachedIds.has(label.id);
            return (
              <button
                key={label.id}
                type="button"
                onClick={() => onToggleLabel(label)}
                data-testid={`task-label-${label.id}`}
              >
                <Badge
                  variant={on ? "default" : "outline"}
                  style={
                    label.color
                      ? on
                        ? {
                            backgroundColor: label.color,
                            borderColor: label.color,
                            color: "#fff",
                          }
                        : { borderColor: label.color, color: label.color }
                      : undefined
                  }
                >
                  {label.name}
                </Badge>
              </button>
            );
          })}
          {labels.length === 0 && (
            <span className="text-xs text-muted-foreground">
              Nenhuma label neste workspace
            </span>
          )}
        </div>
      </div>

      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <Label>Checklists</Label>
          <Button
            type="button"
            size="sm"
            variant="outline"
            className="h-7 text-xs"
            onClick={onAddChecklist}
            data-testid="task-checklist-add"
          >
            Nova checklist
          </Button>
        </div>
        <div className="space-y-3" data-testid="task-checklists">
          {checklists.map((cl) => (
            <div
              key={cl.id}
              className="rounded border border-border/80 bg-background/60 p-2"
              data-testid={`task-checklist-${cl.id}`}
            >
              <div className="mb-1 text-xs font-medium text-foreground">
                {cl.title}
              </div>
              <ul className="space-y-1">
                {(cl.items || []).map((item) => (
                  <li key={item.id} className="flex items-center gap-2 text-sm">
                    <input
                      type="checkbox"
                      checked={item.is_completed}
                      onChange={() =>
                        onToggleItem(cl.id, item.id, item.is_completed)
                      }
                      data-testid={`checklist-item-${item.id}`}
                    />
                    <span
                      className={
                        item.is_completed
                          ? "text-muted-foreground line-through"
                          : ""
                      }
                    >
                      {item.title}
                    </span>
                  </li>
                ))}
              </ul>
              <div className="mt-2 flex gap-1">
                <Input
                  value={newItemByChecklist[cl.id] || ""}
                  onChange={(e) =>
                    setNewItemByChecklist((prev) => ({
                      ...prev,
                      [cl.id]: e.target.value,
                    }))
                  }
                  placeholder="novo item"
                  className="h-8 border-border bg-background text-xs"
                  data-testid={`checklist-item-new-${cl.id}`}
                />
                <Button
                  type="button"
                  size="sm"
                  className="h-8"
                  variant="secondary"
                  onClick={() => onAddItem(cl.id)}
                >
                  Add
                </Button>
              </div>
            </div>
          ))}
        </div>
      </div>

      <div className="space-y-2">
        <Label className="inline-flex items-center gap-1">
          <Paperclip className="h-3.5 w-3.5" /> Anexos
        </Label>
        <Input
          type="file"
          className="border-border bg-background text-xs"
          onChange={(e) => onUpload(e.target.files)}
          data-testid="task-attachment-upload"
        />
        <ul className="space-y-1 text-sm" data-testid="task-attachments">
          {attachments.map((att) => (
            <li
              key={att.id}
              className="flex items-center justify-between gap-2"
            >
              <a
                href={api.attachmentDownloadUrl(att.id)}
                className="text-primary underline-offset-2 hover:underline"
                target="_blank"
                rel="noreferrer"
              >
                {att.filename}
              </a>
              <Button
                type="button"
                size="sm"
                variant="ghost"
                className="h-7 text-xs"
                onClick={() => onDeleteAtt(att.id)}
              >
                Remover
              </Button>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
