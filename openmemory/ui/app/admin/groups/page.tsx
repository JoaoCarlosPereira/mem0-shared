"use client";

import { useCallback, useEffect, useState } from "react";
import { Users } from "lucide-react";
import { PageHeader } from "@/components/shared/PageHeader";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { useGroupsApi, Group, GroupMember } from "@/hooks/useGroupsApi";

function errorMessage(err: any, fallback: string): string {
  return err?.response?.data?.detail || err?.message || fallback;
}

export default function GroupsPage() {
  const {
    fetchGroups,
    createGroup,
    updateGroup,
    deleteGroup,
    fetchMembers,
    addMember,
    removeMember,
  } = useGroupsApi();

  const [groups, setGroups] = useState<Group[]>([]);
  const [newName, setNewName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const [selected, setSelected] = useState<Group | null>(null);
  const [members, setMembers] = useState<GroupMember[]>([]);
  const [newMember, setNewMember] = useState("");

  const reload = useCallback(async () => {
    setLoading(true);
    try {
      setGroups(await fetchGroups());
    } catch (err) {
      setError(errorMessage(err, "Falha ao carregar grupos"));
    } finally {
      setLoading(false);
    }
  }, [fetchGroups]);

  useEffect(() => {
    reload();
  }, [reload]);

  const handleCreate = async () => {
    setError(null);
    try {
      await createGroup(newName);
      setNewName("");
      await reload();
    } catch (err) {
      setError(errorMessage(err, "Falha ao criar grupo"));
    }
  };

  const handleRename = async (group: Group) => {
    const name = window.prompt("Novo nome do grupo", group.name);
    if (!name || name === group.name) return;
    setError(null);
    try {
      await updateGroup(group.id, name);
      await reload();
    } catch (err) {
      setError(errorMessage(err, "Falha ao renomear grupo"));
    }
  };

  const handleDelete = async (group: Group) => {
    setError(null);
    try {
      await deleteGroup(group.id);
      if (selected?.id === group.id) setSelected(null);
      await reload();
    } catch (err) {
      setError(errorMessage(err, "Falha ao remover grupo"));
    }
  };

  const openMembers = async (group: Group) => {
    setSelected(group);
    setError(null);
    try {
      setMembers(await fetchMembers(group.id));
    } catch (err) {
      setError(errorMessage(err, "Falha ao carregar membros"));
    }
  };

  const handleAddMember = async () => {
    if (!selected) return;
    setError(null);
    try {
      await addMember(selected.id, newMember);
      setNewMember("");
      setMembers(await fetchMembers(selected.id));
      await reload();
    } catch (err) {
      setError(errorMessage(err, "Falha ao adicionar membro"));
    }
  };

  const handleRemoveMember = async (member: GroupMember) => {
    if (!selected) return;
    setError(null);
    try {
      await removeMember(selected.id, member.user_id);
      setMembers(await fetchMembers(selected.id));
      await reload();
    } catch (err) {
      setError(errorMessage(err, "Falha ao remover membro"));
    }
  };

  return (
    <div>
      <PageHeader
        className="mb-4"
        icon={Users}
        title="Grupos"
        description="Equipes da empresa: cadastro, edição e gestão de membros"
      />

      {error && (
        <div
          role="alert"
          className="mb-3 rounded-md border border-red-800 bg-red-950/40 px-3 py-2 text-sm text-red-300"
        >
          {error}
        </div>
      )}

      <div className="mb-4 flex gap-2">
        <Input
          placeholder="Nome do novo grupo…"
          className="w-72"
          value={newName}
          onChange={(e) => setNewName(e.target.value)}
        />
        <Button onClick={handleCreate} disabled={!newName.trim()}>
          Criar grupo
        </Button>
      </div>

      <div className="rounded-md border border-zinc-800">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Nome</TableHead>
              <TableHead>Membros</TableHead>
              <TableHead className="text-right">Ações</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {loading ? (
              <TableRow>
                <TableCell colSpan={3} className="py-8 text-center text-zinc-500">
                  Carregando…
                </TableCell>
              </TableRow>
            ) : groups.length === 0 ? (
              <TableRow>
                <TableCell colSpan={3} className="py-8 text-center text-zinc-500">
                  Nenhum grupo cadastrado
                </TableCell>
              </TableRow>
            ) : (
              groups.map((g) => (
                <TableRow key={g.id}>
                  <TableCell className="font-medium">{g.name}</TableCell>
                  <TableCell>{g.member_count}</TableCell>
                  <TableCell className="space-x-2 text-right">
                    <Button variant="secondary" size="sm" onClick={() => openMembers(g)}>
                      Membros
                    </Button>
                    <Button variant="secondary" size="sm" onClick={() => handleRename(g)}>
                      Renomear
                    </Button>
                    <Button
                      variant="destructive"
                      size="sm"
                      onClick={() => handleDelete(g)}
                    >
                      Remover
                    </Button>
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </div>

      {selected && (
        <div className="mt-6 rounded-md border border-zinc-800 p-4">
          <h2 className="mb-3 text-lg font-semibold text-white">
            Membros de {selected.name}
          </h2>
          <div className="mb-3 flex gap-2">
            <Input
              placeholder="hostname do usuário…"
              className="w-72"
              value={newMember}
              onChange={(e) => setNewMember(e.target.value)}
            />
            <Button onClick={handleAddMember} disabled={!newMember.trim()}>
              Adicionar / mover
            </Button>
          </div>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Usuário</TableHead>
                <TableHead className="text-right">Ações</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {members.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={2} className="py-6 text-center text-zinc-500">
                    Nenhum membro
                  </TableCell>
                </TableRow>
              ) : (
                members.map((m) => (
                  <TableRow key={m.id}>
                    <TableCell>{m.user_id}</TableCell>
                    <TableCell className="text-right">
                      <Button
                        variant="secondary"
                        size="sm"
                        onClick={() => handleRemoveMember(m)}
                      >
                        Remover
                      </Button>
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </div>
      )}
    </div>
  );
}
