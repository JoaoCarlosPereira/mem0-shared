import { createSlice, PayloadAction } from '@reduxjs/toolkit';

/** Perfil da pessoa autenticada via Google (feature auth Google, ADR-002). */
export interface PersonProfile {
  email: string | null;
  displayName: string | null;
  avatarUrl: string | null;
  machineHostname: string | null;
  group: string | null;
}

interface ProfileState {
  /**
   * Âncora de dados das rotas REST legadas (?user_id=). A identidade real da
   * pessoa vem da sessão Google (campo `person`), não deste valor.
   */
  userId: string;
  person: PersonProfile | null;
  totalMemories: number;
  totalApps: number;
  status: 'idle' | 'loading' | 'succeeded' | 'failed';
  error: string | null;
  apps: any[];
}

const initialState: ProfileState = {
  userId: process.env.NEXT_PUBLIC_USER_ID || 'user',
  person: null,
  totalMemories: 0,
  totalApps: 0,
  status: 'idle',
  error: null,
  apps: [],
};

const profileSlice = createSlice({
  name: 'profile',
  initialState,
  reducers: {
    setUserId: (state, action: PayloadAction<string>) => {
      state.userId = action.payload;
    },
    setProfileLoading: (state) => {
      state.status = 'loading';
      state.error = null;
    },
    setProfileError: (state, action: PayloadAction<string>) => {
      state.status = 'failed';
      state.error = action.payload;
    },
    resetProfileState: (state) => {
      state.status = 'idle';
      state.error = null;
      state.userId = process.env.NEXT_PUBLIC_USER_ID || 'user';
    },
    setTotalMemories: (state, action: PayloadAction<number>) => {
      state.totalMemories = action.payload;
    },
    setTotalApps: (state, action: PayloadAction<number>) => {
      state.totalApps = action.payload;
    },
    setApps: (state, action: PayloadAction<any[]>) => {
      state.apps = action.payload;
    },
    setPersonProfile: (state, action: PayloadAction<PersonProfile>) => {
      state.person = action.payload;
    },
    clearPersonProfile: (state) => {
      state.person = null;
    }
  },
});

export const {
  setUserId,
  setProfileLoading,
  setProfileError,
  resetProfileState,
  setTotalMemories,
  setTotalApps,
  setApps,
  setPersonProfile,
  clearPersonProfile
} = profileSlice.actions;

export default profileSlice.reducer;