"use client";

import { useSelector } from "react-redux";
import { RootState } from "@/store/store";

export function ProjectsSummary() {
  const listTotal = useSelector((state: RootState) => state.apps.listTotal);
  const totalMemoriesCreated = useSelector(
    (state: RootState) => state.apps.totalMemoriesCreated,
  );
  const visibleCount = useSelector((state: RootState) => state.apps.apps.length);
  const visibleMemories = useSelector((state: RootState) =>
    state.apps.apps.reduce((sum, app) => sum + app.total_memories_created, 0),
  );

  if (listTotal === 0) {
    return null;
  }

  const showingSubset =
    visibleCount < listTotal || visibleMemories < totalMemoriesCreated;

  return (
    <p className="text-sm text-zinc-400 mb-4">
      <span className="text-zinc-200 font-medium">
        {listTotal.toLocaleString("pt-BR")} projetos
      </span>
      {" · "}
      <span className="text-zinc-200 font-medium">
        {totalMemoriesCreated.toLocaleString("pt-BR")} memórias no total
      </span>
      {showingSubset && (
        <span className="text-zinc-500">
          {" "}
          (exibindo {visibleCount.toLocaleString("pt-BR")} projetos com{" "}
          {visibleMemories.toLocaleString("pt-BR")} memórias)
        </span>
      )}
    </p>
  );
}
