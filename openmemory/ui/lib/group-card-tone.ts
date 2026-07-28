/** Paleta estável de tons por grupo/autor no tema escuro do shell. */
export const GROUP_CARD_TONES = [
  {
    accent: "bg-sky-400",
    border: "border-sky-500/35",
    borderHover: "hover:border-sky-400/55",
    wash: "from-sky-500/15 via-slate-950/80 to-slate-950",
    ring: "ring-sky-400/40",
    glow: "shadow-sky-500/10",
    chip: "bg-sky-500/15 text-sky-300",
  },
  {
    accent: "bg-emerald-400",
    border: "border-emerald-500/35",
    borderHover: "hover:border-emerald-400/55",
    wash: "from-emerald-500/15 via-slate-950/80 to-slate-950",
    ring: "ring-emerald-400/40",
    glow: "shadow-emerald-500/10",
    chip: "bg-emerald-500/15 text-emerald-300",
  },
  {
    accent: "bg-amber-400",
    border: "border-amber-500/35",
    borderHover: "hover:border-amber-400/55",
    wash: "from-amber-500/15 via-slate-950/80 to-slate-950",
    ring: "ring-amber-400/40",
    glow: "shadow-amber-500/10",
    chip: "bg-amber-500/15 text-amber-300",
  },
  {
    accent: "bg-rose-400",
    border: "border-rose-500/35",
    borderHover: "hover:border-rose-400/55",
    wash: "from-rose-500/15 via-slate-950/80 to-slate-950",
    ring: "ring-rose-400/40",
    glow: "shadow-rose-500/10",
    chip: "bg-rose-500/15 text-rose-300",
  },
  {
    accent: "bg-violet-400",
    border: "border-violet-500/35",
    borderHover: "hover:border-violet-400/55",
    wash: "from-violet-500/15 via-slate-950/80 to-slate-950",
    ring: "ring-violet-400/40",
    glow: "shadow-violet-500/10",
    chip: "bg-violet-500/15 text-violet-300",
  },
  {
    accent: "bg-cyan-400",
    border: "border-cyan-500/35",
    borderHover: "hover:border-cyan-400/55",
    wash: "from-cyan-500/15 via-slate-950/80 to-slate-950",
    ring: "ring-cyan-400/40",
    glow: "shadow-cyan-500/10",
    chip: "bg-cyan-500/15 text-cyan-300",
  },
  {
    accent: "bg-orange-400",
    border: "border-orange-500/35",
    borderHover: "hover:border-orange-400/55",
    wash: "from-orange-500/15 via-slate-950/80 to-slate-950",
    ring: "ring-orange-400/40",
    glow: "shadow-orange-500/10",
    chip: "bg-orange-500/15 text-orange-300",
  },
  {
    accent: "bg-teal-400",
    border: "border-teal-500/35",
    borderHover: "hover:border-teal-400/55",
    wash: "from-teal-500/15 via-slate-950/80 to-slate-950",
    ring: "ring-teal-400/40",
    glow: "shadow-teal-500/10",
    chip: "bg-teal-500/15 text-teal-300",
  },
] as const;

export const UNGROUPED_CARD_TONE = {
  accent: "bg-blue-500",
  border: "border-slate-700/80",
  borderHover: "hover:border-blue-500/45",
  wash: "from-slate-800/50 via-slate-950/90 to-slate-950",
  ring: "ring-blue-500/35",
  glow: "shadow-blue-500/5",
  chip: "bg-slate-800 text-slate-400",
} as const;

export type GroupCardTone =
  | (typeof GROUP_CARD_TONES)[number]
  | typeof UNGROUPED_CARD_TONE;

function hashKey(value: string): number {
  let hash = 0;
  for (let i = 0; i < value.length; i += 1) {
    hash = (hash * 31 + value.charCodeAt(i)) >>> 0;
  }
  return hash;
}

/**
 * Tom determinístico: prioriza o grupo; sem grupo, varia pelo autor
 * para o grid não virar um muro monocromático.
 */
export function groupCardTone(
  group?: string | null,
  authorKey?: string | null,
): GroupCardTone {
  const trimmedGroup = group?.trim();
  if (trimmedGroup) {
    return GROUP_CARD_TONES[
      hashKey(trimmedGroup) % GROUP_CARD_TONES.length
    ];
  }
  const trimmedAuthor = authorKey?.trim();
  if (trimmedAuthor) {
    return GROUP_CARD_TONES[
      hashKey(`author:${trimmedAuthor}`) % GROUP_CARD_TONES.length
    ];
  }
  return UNGROUPED_CARD_TONE;
}
