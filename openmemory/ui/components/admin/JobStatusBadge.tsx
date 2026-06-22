import { WriteQueueStatus, GovernanceJobStatus } from "@/types/admin";
import { jobStatusLabel } from "@/lib/i18n/pt-BR";

type AnyStatus = WriteQueueStatus | GovernanceJobStatus;

const STATUS_CLASSES: Record<AnyStatus, string> = {
  queued: "bg-zinc-700 text-zinc-100",
  processing: "bg-blue-600 text-white",
  done: "bg-green-600 text-white",
  skipped: "bg-amber-600 text-white",
  failed: "bg-red-600 text-white",
};

export function JobStatusBadge({ status }: { status: AnyStatus }) {
  return (
    <span
      data-status={jobStatusLabel(status)}
      className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${STATUS_CLASSES[status]}`}
    >
      {jobStatusLabel(status)}
    </span>
  );
}

export default JobStatusBadge;
