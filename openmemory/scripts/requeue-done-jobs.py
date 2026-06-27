#!/usr/bin/env python3
"""Re-queue completed write jobs after Qdrant data loss.

The durable PostgreSQL ``write_queue`` keeps the original texts even when the
vector store was wiped. Run this inside an API or write-worker container:

    docker compose -f docker-compose.scale.yml exec openmemory-write-worker \\
        python /usr/src/openmemory/scripts/requeue-done-jobs.py

Optional project filter:

    python requeue-done-jobs.py --project SPED
"""

from __future__ import annotations

import argparse
import sys


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", help="Requeue only this project")
    parser.add_argument("--dry-run", action="store_true", help="Count only, do not update")
    args = parser.parse_args()

    from app.database import SessionLocal
    from app.utils.write_queue_requeue import requeue_done_write_jobs

    db = SessionLocal()
    try:
        if args.dry_run:
            from app.models import WriteQueueJob, WriteQueueStatus

            query = db.query(WriteQueueJob).filter(WriteQueueJob.status == WriteQueueStatus.done)
            if args.project:
                query = query.filter(WriteQueueJob.project == args.project)
            count = query.count()
            print(f"Would requeue {count} done job(s)")
            return 0

        count, projects = requeue_done_write_jobs(db, project=args.project)
        print(f"Requeued {count} done job(s) across projects: {', '.join(sorted(projects)) or '(none)'}")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
