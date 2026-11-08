import { create } from 'zustand';

const useStore = create((set, get) => ({
  // Auth
  user: JSON.parse(localStorage.getItem('cargo_user') || 'null'),
  setAuth: (user) => {
    localStorage.setItem('cargo_user', JSON.stringify(user));
    set({ user });
  },
  clearAuth: () => {
    localStorage.removeItem('cargo_user');
    set({ user: null });
  },

  // Disponibilidades
  disponibilidades: [],
  setDisponibilidades: (data) => set({ disponibilidades: data }),
  updateDisponibilidade: (updated) => {
    const state = get();
    const index = state.disponibilidades.findIndex((d) => d.id === updated.id);
    if (index >= 0) {
      const newList = [...state.disponibilidades];
      newList[index] = updated;
      // Sort by data_conversa desc (most recent first)
      newList.sort((a, b) => new Date(b.data_conversa) - new Date(a.data_conversa));
      set({ disponibilidades: newList });
    }
  },
  addDisponibilidade: (item) => {
    const state = get();
    const newList = [item, ...state.disponibilidades];
    newList.sort((a, b) => new Date(b.data_conversa) - new Date(a.data_conversa));
    set({ disponibilidades: newList });
  },
  removeDisponibilidade: (id) => {
    const state = get();
    set({ disponibilidades: state.disponibilidades.filter((d) => d.id !== id) });
  },

  // Dashboard
  dashboardTotal: { total_disponiveis: 0, total_podem_carregar: 0, total_nao_podem: 0 },
  dashboardDias: [],
  dashboardOrigens: [],
  ranking: [],
  selectedDay: null,

  setDashboardTotal: (data) => set({ dashboardTotal: data }),
  setDashboardDias: (data) => set({ dashboardDias: data }),
  setDashboardOrigens: (data) => set({ dashboardOrigens: data }),
  setRanking: (data) => set({ ranking: data }),
  setSelectedDay: (day) => set({ selectedDay: day }),

  // Motoristas
  motoristas: [],
  setMotoristas: (data) => set({ motoristas: data }),

  // WS connected
  wsConnected: false,
  setWsConnected: (v) => set({ wsConnected: v }),

  // Refresh trigger (incremented by full_refresh WS event)
  refreshTrigger: 0,
  incrementRefresh: () => set((s) => ({ refreshTrigger: s.refreshTrigger + 1 })),

  // Google Sheets sync
  sheetsSyncStatus: {
    enabled: false,
    running: false,
    sync_count: 0,
    last_sync: null,
  },
  setSheetsSyncStatus: (data) => set({ sheetsSyncStatus: data }),
}));

export default useStore;
