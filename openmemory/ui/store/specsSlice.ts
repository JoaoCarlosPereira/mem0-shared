import { createSlice, PayloadAction } from "@reduxjs/toolkit";
import { WorkspaceBoard, WorkspaceSummary } from "@/types/specs";

interface SpecsState {
  // Índice global de Specs: todos os workspaces acessíveis (todos os projetos).
  allWorkspaces: WorkspaceSummary[] | null;
  // Painel de Projeto (task_13): workspaces do projeto com progresso resumido.
  projectWorkspaces: WorkspaceSummary[] | null;
  // Quadro Kanban (task_14): workspace atualmente aberto (documentos + tasks).
  currentBoard: WorkspaceBoard | null;
  pollingIntervalMs: number;
  loading: boolean;
  error: string | null;
}

const initialState: SpecsState = {
  allWorkspaces: null,
  projectWorkspaces: null,
  currentBoard: null,
  // Mesmo padrão do adminSlice (15s, faixa 10–60s).
  pollingIntervalMs: 15000,
  loading: false,
  error: null,
};

const specsSlice = createSlice({
  name: "specs",
  initialState,
  reducers: {
    setAllWorkspaces: (state, action: PayloadAction<WorkspaceSummary[]>) => {
      state.allWorkspaces = action.payload;
      state.loading = false;
      state.error = null;
    },
    setProjectWorkspaces: (
      state,
      action: PayloadAction<WorkspaceSummary[]>,
    ) => {
      state.projectWorkspaces = action.payload;
      state.loading = false;
      state.error = null;
    },
    setCurrentBoard: (state, action: PayloadAction<WorkspaceBoard>) => {
      state.currentBoard = action.payload;
      state.loading = false;
      state.error = null;
    },
    setSpecsLoading: (state) => {
      state.loading = true;
      state.error = null;
    },
    setSpecsError: (state, action: PayloadAction<string>) => {
      state.loading = false;
      state.error = action.payload;
    },
    setSpecsPollingInterval: (state, action: PayloadAction<number>) => {
      const clamped = Math.min(60000, Math.max(10000, action.payload));
      state.pollingIntervalMs = clamped;
    },
  },
});

export const {
  setAllWorkspaces,
  setProjectWorkspaces,
  setCurrentBoard,
  setSpecsLoading,
  setSpecsError,
  setSpecsPollingInterval,
} = specsSlice.actions;

export default specsSlice.reducer;
