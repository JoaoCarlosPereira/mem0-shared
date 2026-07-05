import Image from "next/image";
import { AttributionDisplay } from "@/lib/attribution";

interface CreatorAvatarProps {
  attribution: AttributionDisplay;
  size: number;
  className?: string;
}

/** Circular avatar: linked user photo when available, else MCP client icon. */
export function CreatorAvatar({
  attribution,
  size,
  className = "",
}: CreatorAvatarProps) {
  if (attribution.avatarUrl) {
    return (
      <Image
        src={attribution.avatarUrl}
        alt=""
        width={size}
        height={size}
        className={`rounded-full object-cover ${className}`}
        unoptimized
      />
    );
  }

  if (!attribution.iconImage) {
    return null;
  }

  return (
    <Image
      src={attribution.iconImage}
      alt=""
      width={size}
      height={size}
      className={`rounded-full ${className}`}
    />
  );
}
