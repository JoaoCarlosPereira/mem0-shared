"use client";

import { useMemo, useState } from "react";
import { Check, ChevronsUpDown } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from "@/components/ui/command";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { cn } from "@/lib/utils";
import type { GroupMemberCandidate } from "@/hooks/useGroupsApi";

interface MemberHostnameComboboxProps {
  candidates: GroupMemberCandidate[];
  value: string;
  onChange: (userId: string) => void;
  /** Hostnames já no grupo selecionado — ocultos da lista. */
  excludeUserIds?: string[];
  disabled?: boolean;
  placeholder?: string;
}

function candidateLabel(c: GroupMemberCandidate): string {
  const name = c.display_name || c.name;
  if (name && name !== c.user_id) {
    return `${name} (${c.user_id})`;
  }
  return c.user_id;
}

export function MemberHostnameCombobox({
  candidates,
  value,
  onChange,
  excludeUserIds = [],
  disabled = false,
  placeholder = "Buscar hostname ou nome…",
}: MemberHostnameComboboxProps) {
  const [open, setOpen] = useState(false);
  const excluded = useMemo(
    () => new Set(excludeUserIds.map((id) => id.toLowerCase())),
    [excludeUserIds],
  );

  const options = useMemo(
    () =>
      candidates.filter((c) => !excluded.has(c.user_id.toLowerCase())),
    [candidates, excluded],
  );

  const selected = options.find((c) => c.user_id === value) ?? null;

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button
          type="button"
          variant="outline"
          role="combobox"
          aria-expanded={open}
          aria-label={placeholder}
          disabled={disabled}
          className="w-80 justify-between border-zinc-700 bg-zinc-950 font-normal text-zinc-100 hover:bg-zinc-900 hover:text-zinc-100"
        >
          <span className={cn("truncate", !selected && "text-zinc-500")}>
            {selected ? candidateLabel(selected) : placeholder}
          </span>
          <ChevronsUpDown className="ml-2 h-4 w-4 shrink-0 opacity-50" />
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-80 border-zinc-700 bg-zinc-950 p-0" align="start">
        <Command className="bg-zinc-950 text-zinc-100">
          <CommandInput placeholder="Filtrar por hostname ou nome…" />
          <CommandList>
            <CommandEmpty>Nenhum hostname encontrado.</CommandEmpty>
            <CommandGroup>
              {options.map((c) => (
                <CommandItem
                  key={c.id}
                  value={`${c.user_id} ${c.display_name ?? ""} ${c.name ?? ""} ${c.group_name ?? ""}`}
                  onSelect={() => {
                    onChange(c.user_id);
                    setOpen(false);
                  }}
                  className="aria-selected:bg-zinc-800"
                >
                  <Check
                    className={cn(
                      "mr-2 h-4 w-4",
                      value === c.user_id ? "opacity-100" : "opacity-0",
                    )}
                  />
                  <span className="flex min-w-0 flex-col">
                    <span className="truncate font-medium">
                      {c.display_name || c.name || c.user_id}
                    </span>
                    <span className="truncate text-xs text-zinc-500">
                      {c.user_id}
                      {c.group_name ? ` · ${c.group_name}` : ""}
                    </span>
                  </span>
                </CommandItem>
              ))}
            </CommandGroup>
          </CommandList>
        </Command>
      </PopoverContent>
    </Popover>
  );
}
