import Image from "next/image";
import { resolveAttribution } from "@/lib/attribution";

interface AttributionBadgeProps {
  appName?: string | null;
  clientName?: string | null;
  hostname?: string | null;
  metadata?: Record<string, unknown> | null;
  prefix?: string;
  iconSize?: number;
  className?: string;
}

export function AttributionBadge({
  appName,
  clientName,
  hostname,
  metadata,
  prefix = "Criada por:",
  iconSize = 24,
  className = "",
}: AttributionBadgeProps) {
  const attribution = resolveAttribution({
    appName,
    clientName,
    hostname,
    metadata,
  });

  return (
    <div
      className={`flex items-center gap-1 bg-zinc-700 px-3 py-1 rounded-lg ${className}`}
    >
      {prefix ? (
        <span className="text-sm text-zinc-400">{prefix}</span>
      ) : null}
      {attribution.iconImage ? (
        <div className="rounded-full bg-zinc-700 flex items-center justify-center overflow-hidden">
          <Image
            src={attribution.iconImage}
            alt=""
            width={iconSize}
            height={iconSize}
            className={
              iconSize <= 20 ? "w-4 h-4" : iconSize <= 24 ? "w-5 h-5" : "w-7 h-7"
            }
          />
        </div>
      ) : null}
      <p className="text-sm text-zinc-100 font-semibold">{attribution.label}</p>
    </div>
  );
}

interface AttributionLabelProps {
  appName?: string | null;
  clientName?: string | null;
  hostname?: string | null;
  metadata?: Record<string, unknown> | null;
}

/** Compact inline label (tables, lists). */
export function AttributionLabel({
  appName,
  clientName,
  hostname,
  metadata,
}: AttributionLabelProps) {
  const attribution = resolveAttribution({
    appName,
    clientName,
    hostname,
    metadata,
  });

  return (
    <div className="flex items-center justify-center gap-1.5">
      {attribution.iconImage ? (
        <Image
          src={attribution.iconImage}
          alt=""
          width={18}
          height={18}
          className="w-[18px] h-[18px] rounded-full"
        />
      ) : null}
      <span className="text-sm font-semibold">{attribution.label}</span>
    </div>
  );
}
