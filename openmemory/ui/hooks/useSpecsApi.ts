import { useCallback } from "react";
import axios from "axios";
import { useDispatch, useSelector } from "react-redux";
import { AppDispatch, RootState } from "@/store/store";
import {
  setAllWorkspaces,
  setProjectWorkspaces,
  setCurrentBoard,
  setSpecsLoading,
  setSpecsError,
} from "@/store/specsSlice";
import { usePolling } from "@/hooks/usePolling";
import { getApiUrl } from "@/lib/api-url";
import {
  ClaimResult,
  CommentCreate,
  DocumentType,
  DocumentVersion,
  DocumentWriteRequest,
  DocumentWriteResult,
  SpecSearchResult,
  StatusPatchRequest,
  TaskCard,
  TaskCreate,
  TaskUpdate,
  UpdateStatusResult,
  Workspace,
  WorkspaceBoard,
  WorkspaceCreate,
  WorkspaceSummary,
} from "@/types/specs";

interface UseSpecsApiOptions {
  // Quando true, o índice global (todos os workspaces) é auto-atualizado.
  all?: boolean;
  // Quando informado, o painel do projeto é auto-atualizado (polling).
  projectId?: string;
  // Quando informado, o quadro do workspace é auto-atualizado (polling).
  workspaceId?: string;
  poll?: boolean;
}

const base = () => `${getApiUrl()}/api/v1/specs`;

/**
 * Hook de acesso aos endpoints REST de specs (Tarefas 3/4/6). Segue o padrão de
 * `useAdminApi`: funções `useCallback` sobre `axios`/`getApiUrl()`, sem RTK
 * Query. Despacha painel/quadro para o `specsSlice`. Conflitos (HTTP 409) são
 * devolvidos como resultado estruturado, nunca como exceção não tratada.
 */
export const useSpecsApi = (options?: UseSpecsApiOptions) => {
  const poll = options?.poll ?? true;
  const all = options?.all ?? false;
  const projectId = options?.projectId;
  const workspaceId = options?.workspaceId;
  const dispatch = useDispatch<AppDispatch>();
  const intervalMs = useSelector(
    (state: RootState) => state.specs.pollingIntervalMs,
  );

  // --- Índice global (todos os workspaces) ---
  const fetchAllWorkspaces = useCallback(async (): Promise<void> => {
    dispatch(setSpecsLoading());
    try {
      const res = await axios.get<WorkspaceSummary[]>(`${base()}/workspaces`);
      dispatch(setAllWorkspaces(res.data));
    } catch (err: any) {
      dispatch(setSpecsError(err?.message || "Falha ao listar specs"));
    }
  }, [dispatch]);

  // --- Painel de Projeto ---
  const fetchProjectWorkspaces = useCallback(
    async (project?: string): Promise<void> => {
      const target = project ?? projectId;
      if (!target) return;
      dispatch(setSpecsLoading());
      try {
        const res = await axios.get<WorkspaceSummary[]>(
          `${base()}/projects/${encodeURIComponent(target)}/workspaces`,
        );
        dispatch(setProjectWorkspaces(res.data));
      } catch (err: any) {
        dispatch(setSpecsError(err?.message || "Falha ao listar workspaces"));
      }
    },
    [dispatch, projectId],
  );

  // --- Quadro (workspace completo) ---
  const fetchWorkspaceBoard = useCallback(
    async (id?: string): Promise<void> => {
      const target = id ?? workspaceId;
      if (!target) return;
      dispatch(setSpecsLoading());
      try {
        const res = await axios.get<WorkspaceBoard>(
          `${base()}/workspaces/${target}`,
        );
        dispatch(setCurrentBoard(res.data));
      } catch (err: any) {
        dispatch(setSpecsError(err?.message || "Falha ao carregar o quadro"));
      }
    },
    [dispatch, workspaceId],
  );

  const createWorkspace = useCallback(
    async (payload: WorkspaceCreate): Promise<Workspace> => {
      const res = await axios.post<Workspace>(`${base()}/workspaces`, payload);
      return res.data;
    },
    [],
  );

  // --- Documentos ---
  const writeDocument = useCallback(
    async (
      wsId: string,
      documentType: DocumentType,
      payload: DocumentWriteRequest,
    ): Promise<DocumentWriteResult> => {
      try {
        const res = await axios.put<DocumentWriteResult>(
          `${base()}/workspaces/${wsId}/documents/${documentType}`,
          payload,
        );
        return { ...res.data, conflict: false };
      } catch (err: any) {
        // Conflito de versão (409): devolve estruturado para a UI reconciliar.
        if (err?.response?.status === 409) {
          const detail = err.response.data?.detail ?? {};
          return {
            conflict: true,
            current_version: detail.current_version,
            current_content: detail.current_content,
          };
        }
        throw err;
      }
    },
    [],
  );

  const fetchDocumentVersions = useCallback(
    async (
      wsId: string,
      documentType: DocumentType,
    ): Promise<DocumentVersion[]> => {
      const res = await axios.get<DocumentVersion[]>(
        `${base()}/workspaces/${wsId}/documents/${documentType}/versions`,
      );
      return res.data;
    },
    [],
  );

  // --- Tasks ---
  const createTask = useCallback(
    async (payload: TaskCreate): Promise<TaskCard> => {
      const res = await axios.post<TaskCard>(`${base()}/tasks`, payload);
      return res.data;
    },
    [],
  );

  const updateTask = useCallback(
    async (
      taskId: string,
      payload: TaskUpdate,
    ): Promise<{ conflict: boolean; task?: TaskCard; current_version?: number }> => {
      try {
        const res = await axios.patch<TaskCard>(
          `${base()}/tasks/${taskId}`,
          payload,
        );
        return { conflict: false, task: res.data };
      } catch (err: any) {
        if (err?.response?.status === 409) {
          const detail = err.response.data?.detail ?? {};
          return {
            conflict: true,
            current_version: detail.current_version,
          };
        }
        throw err;
      }
    },
    [],
  );

  const deleteTask = useCallback(async (taskId: string): Promise<void> => {
    await axios.delete(`${base()}/tasks/${taskId}`);
  }, []);

  const deleteDocument = useCallback(
    async (wsId: string, documentType: DocumentType): Promise<void> => {
      await axios.delete(
        `${base()}/workspaces/${wsId}/documents/${documentType}`,
      );
    },
    [],
  );

  const claimTask = useCallback(
    async (taskId: string, claimant: string): Promise<ClaimResult> => {
      try {
        const res = await axios.post<TaskCard>(
          `${base()}/tasks/${taskId}/claim`,
          { claimant },
        );
        return { claimed: true, task: res.data, version: res.data.version };
      } catch (err: any) {
        if (err?.response?.status === 409) {
          const detail = err.response.data?.detail ?? {};
          return {
            claimed: false,
            current_assignee: detail.current_assignee,
            version: detail.version,
          };
        }
        throw err;
      }
    },
    [],
  );

  const releaseTask = useCallback(
    async (
      taskId: string,
      body?: { actor?: string; reason?: string },
    ): Promise<TaskCard> => {
      const res = await axios.post<TaskCard>(
        `${base()}/tasks/${taskId}/release`,
        body ?? {},
      );
      return res.data;
    },
    [],
  );

  const updateTaskStatus = useCallback(
    async (
      taskId: string,
      payload: StatusPatchRequest,
    ): Promise<UpdateStatusResult> => {
      try {
        const res = await axios.patch<TaskCard>(
          `${base()}/tasks/${taskId}/status`,
          payload,
        );
        return { conflict: false, task: res.data };
      } catch (err: any) {
        if (err?.response?.status === 409) {
          const detail = err.response.data?.detail ?? {};
          return {
            conflict: true,
            current_version: detail.current_version,
            current_status: detail.current_status,
          };
        }
        throw err;
      }
    },
    [],
  );

  const createComment = useCallback(
    async (payload: CommentCreate): Promise<any> => {
      const res = await axios.post(`${base()}/comments`, payload);
      return res.data;
    },
    [],
  );

  // --- Busca semântica ---
  const searchSpecs = useCallback(
    async (q: string, project?: string): Promise<SpecSearchResult[]> => {
      const res = await axios.get<SpecSearchResult[]>(`${base()}/search`, {
        params: { q, project_id: project || undefined },
      });
      return res.data;
    },
    [],
  );

  usePolling(fetchAllWorkspaces, intervalMs, poll && all);
  usePolling(fetchProjectWorkspaces, intervalMs, poll && !!projectId);
  usePolling(fetchWorkspaceBoard, intervalMs, poll && !!workspaceId);

  return {
    fetchAllWorkspaces,
    fetchProjectWorkspaces,
    fetchWorkspaceBoard,
    createWorkspace,
    writeDocument,
    fetchDocumentVersions,
    createTask,
    updateTask,
    deleteTask,
    deleteDocument,
    claimTask,
    releaseTask,
    updateTaskStatus,
    createComment,
    searchSpecs,
  };
};

export default useSpecsApi;
