import { WriteQueueStatus, GovernanceJobStatus } from "@/types/admin";

type AnyStatus = WriteQueueStatus | GovernanceJobStatus;

const STATUS_CLASSES: Record<AnyStatus, string> = {
  queued: "bg-zinc-700 text-zinc-100",
  processing: "bg-blue-600 text-white",
  done: "bg-green-600 text-white",
  failed: "bg-red-600 text-white",
};

export function JobStatusBadge({ status }: { status: AnyStatus }) {
  return (
    <span
      data-status={status}
      className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${STATUS_CLASSES[status]}`}
    >
      {status}
    </span>
  );
}

export default JobStatusBadge;
