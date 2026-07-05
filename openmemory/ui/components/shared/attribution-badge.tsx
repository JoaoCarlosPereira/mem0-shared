import { resolveAttribution } from "@/lib/attribution";
import { CreatorAvatar } from "@/components/shared/creator-avatar";

export interface CreatorAttributionInput {
  appName?: string | null;
  clientName?: string | null;
  hostname?: string | null;
  displayName?: string | null;
  avatarUrl?: string | null;
  metadata?: Record<string, unknown> | null;
}

export function resolveCreatorAttribution(opts: CreatorAttributionInput) {
  return resolveAttribution(opts);
}

interface AttributionBadgeProps extends CreatorAttributionInput {
  prefix?: string;
  iconSize?: number;
  className?: string;
}

export function AttributionBadge({
  appName,
  clientName,
  hostname,
  displayName,
  avatarUrl,
  metadata,
  prefix = "Criada por:",
  iconSize = 24,
  className = "",
}: AttributionBadgeProps) {
  const attribution = resolveCreatorAttribution({
    appName,
    clientName,
    hostname,
    displayName,
    avatarUrl,
    metadata,
  });

  return (
    <div
      className={`flex items-center gap-1 bg-zinc-700 px-3 py-1 rounded-lg ${className}`}
    >
      {prefix ? (
        <span className="text-sm text-zinc-400">{prefix}</span>
      ) : null}
      <div className="rounded-full bg-zinc-700 flex items-center justify-center overflow-hidden">
        <CreatorAvatar
          attribution={attribution}
          size={iconSize}
          className={
            iconSize <= 20 ? "w-4 h-4" : iconSize <= 24 ? "w-5 h-5" : "w-7 h-7"
          }
        />
      </div>
      <p className="text-sm text-zinc-100 font-semibold">{attribution.label}</p>
    </div>
  );
}

interface AttributionLabelProps extends CreatorAttributionInput {}

/** Compact inline label (tables, lists). */
export function AttributionLabel({
  appName,
  clientName,
  hostname,
  displayName,
  avatarUrl,
  metadata,
}: AttributionLabelProps) {
  const attribution = resolveCreatorAttribution({
    appName,
    clientName,
    hostname,
    displayName,
    avatarUrl,
    metadata,
  });

  return (
    <div className="flex items-center justify-center gap-1.5">
      <CreatorAvatar
        attribution={attribution}
        size={18}
        className="w-[18px] h-[18px]"
      />
      <span className="text-sm font-semibold">{attribution.label}</span>
    </div>
  );
}

/** Queue/audit rows keyed by ``user_display_name`` / ``user_avatar_url``. */
export function ActorLabel({
  hostname,
  clientName,
  displayName,
  avatarUrl,
}: {
  hostname?: string | null;
  clientName?: string | null;
  displayName?: string | null;
  avatarUrl?: string | null;
}) {
  const attribution = resolveCreatorAttribution({
    clientName,
    hostname,
    displayName,
    avatarUrl,
  });

  return (
    <div
      className="flex items-center gap-1.5"
      title={hostname && displayName ? hostname : clientName ?? undefined}
    >
      <CreatorAvatar
        attribution={attribution}
        size={18}
        className="w-[18px] h-[18px]"
      />
      <span className="font-medium text-zinc-200">{attribution.label}</span>
    </div>
  );
}
