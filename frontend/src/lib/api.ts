import type {
  Token, User, UserSearchResult, Game, GameReschedule, PlayerStats,
  CareerStats, GameStatsHistoryEntry, Message, ConversationPreview,
  Challenge, ChallengeHistoryEntry, StatsContest,
} from './types';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

function getToken(): string | null {
  if (typeof window === 'undefined') return null;
  return localStorage.getItem('token');
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = getToken();
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options.headers as Record<string, string> || {}),
  };
  if (token) headers['Authorization'] = `Bearer ${token}`;

  const res = await fetch(`${API_BASE}${path}`, { ...options, headers });

  if (options.method === 'DELETE' && res.status === 204) {
    return undefined as T;
  }

  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }));
    const msg = Array.isArray(body.detail)
      ? body.detail.map((d: { msg?: string }) => d?.msg || String(d)).join('. ')
      : (body.detail || 'Request failed');
    throw new ApiError(typeof msg === 'string' ? msg : 'Request failed', res.status);
  }
  return res.json();
}

export const api = {
  register: (data: {
    email: string; username: string; password: string; display_name: string;
    height?: string; weight?: number; preferred_position?: string; gender?: string;
    self_reported_skill: number;
  }) => request<{ message: string }>('/api/auth/register', { method: 'POST', body: JSON.stringify(data) }),

  verifyEmail: (email: string, code: string) =>
    request<{ message: string }>('/api/auth/verify-email', {
      method: 'POST', body: JSON.stringify({ email, code }),
    }),

  resendVerificationCode: (email: string) =>
    request<{ message: string }>('/api/auth/resend-code', {
      method: 'POST', body: JSON.stringify({ email }),
    }),

  login: async (email: string, password: string): Promise<Token> => {
    const token = await request<Token>('/api/auth/login', {
      method: 'POST', body: JSON.stringify({ email, password }),
    });
    localStorage.setItem('token', token.access_token);
    return token;
  },

  logout: () => { localStorage.removeItem('token'); },

  getMe: () => request<User>('/api/users/me'),
  updateMe: (data: Partial<User>) =>
    request<User>('/api/users/me', { method: 'PUT', body: JSON.stringify(data) }),
  getUser: (id: number) => request<User>(`/api/users/${id}`),

  compareToUser: (userId: number) =>
    request<{ target: { id: number; display_name: string; username: string; ai_skill_rating: number }; my_win_probability: number; their_win_probability: number }>(`/api/users/compare/${userId}`),

  searchUsers: (q: string, filters?: {
    position?: string; min_skill?: number; max_skill?: number;
    min_games?: number; min_wins?: number; sort_by?: string;
    min_ppg?: number; min_rpg?: number; min_apg?: number;
    min_spg?: number; min_bpg?: number; min_fg_pct?: number;
  }) => {
    const params = new URLSearchParams();
    if (q) params.set('q', q);
    if (filters?.position) params.set('position', filters.position);
    if (filters?.min_skill !== undefined) params.set('min_skill', String(filters.min_skill));
    if (filters?.max_skill !== undefined) params.set('max_skill', String(filters.max_skill));
    if (filters?.min_games !== undefined) params.set('min_games', String(filters.min_games));
    if (filters?.min_wins !== undefined) params.set('min_wins', String(filters.min_wins));
    if (filters?.min_ppg !== undefined) params.set('min_ppg', String(filters.min_ppg));
    if (filters?.min_rpg !== undefined) params.set('min_rpg', String(filters.min_rpg));
    if (filters?.min_apg !== undefined) params.set('min_apg', String(filters.min_apg));
    if (filters?.min_spg !== undefined) params.set('min_spg', String(filters.min_spg));
    if (filters?.min_bpg !== undefined) params.set('min_bpg', String(filters.min_bpg));
    if (filters?.min_fg_pct !== undefined) params.set('min_fg_pct', String(filters.min_fg_pct));
    if (filters?.sort_by) params.set('sort_by', filters.sort_by);
    return request<UserSearchResult[]>(`/api/users/search?${params.toString()}`);
  },

  getLeaderboard: (limit?: number, position?: string, sort?: 'overall' | 'position' | 'hot_week') => {
    const params = new URLSearchParams();
    if (limit) params.set('limit', String(limit));
    if (position) params.set('position', position);
    if (sort) params.set('sort', sort);
    const qs = params.toString();
    return request<UserSearchResult[]>(`/api/users/leaderboard${qs ? `?${qs}` : ''}`);
  },

  getLeaderboard1v1: (limit?: number, sort?: 'wins_total' | 'wins_week') => {
    const params = new URLSearchParams();
    if (limit) params.set('limit', String(limit));
    if (sort) params.set('sort', sort || 'wins_total');
    const qs = params.toString();
    return request<UserSearchResult[]>(`/api/users/leaderboard-1v1${qs ? `?${qs}` : ''}`);
  },

  getUserChallengesHistory: (userId: number, limit?: number) => {
    const params = new URLSearchParams();
    if (limit) params.set('limit', String(limit));
    const qs = params.toString();
    return request<ChallengeHistoryEntry[]>(`/api/users/${userId}/challenges-history${qs ? `?${qs}` : ''}`);
  },

  updateGame: (id: number, data: { scheduled_time?: string; skill_min?: number; skill_max?: number; court_type?: string; notes?: string }) =>
    request<Game>(`/api/games/${id}`, { method: 'PATCH', body: JSON.stringify(data) }),

  createGame: (data: {
    game_type: string; scheduled_time: string; skill_min: number; skill_max: number;
    court_type: string; notes?: string;
  }) => request<Game>('/api/games', { method: 'POST', body: JSON.stringify(data) }),

  listGames: (filters?: { game_type?: string; status?: string }) => {
    const params = new URLSearchParams();
    if (filters?.game_type) params.set('game_type', filters.game_type);
    if (filters?.status) params.set('status', filters.status);
    const qs = params.toString();
    return request<Game[]>(`/api/games${qs ? `?${qs}` : ''}`);
  },

  getGame: (id: number) => request<Game>(`/api/games/${id}`),
  deleteGame: (id: number) => request<undefined>(`/api/games/${id}`, { method: 'DELETE' }),
  joinGame: (id: number) => request<Game>(`/api/games/${id}/join`, { method: 'POST' }),
  leaveGame: (id: number) => request<Game>(`/api/games/${id}/leave`, { method: 'POST' }),
  startGame: (id: number) => request<Game>(`/api/games/${id}/start`, { method: 'POST' }),
  kickPlayer: (gameId: number, userId: number) =>
    request<Game>(`/api/games/${gameId}/kick/${userId}`, { method: 'POST' }),
  completeGame: (id: number, teamAScore: number, teamBScore: number) =>
    request<Game>(`/api/games/${id}/complete`, {
      method: 'POST', body: JSON.stringify({ team_a_score: teamAScore, team_b_score: teamBScore }),
    }),

  inviteScorekeeper: (gameId: number, userId: number) =>
    request<Game>(`/api/games/${gameId}/invite-scorekeeper`, {
      method: 'POST', body: JSON.stringify({ user_id: userId }),
    }),
  acceptScorekeeper: (gameId: number) =>
    request<Game>(`/api/games/${gameId}/accept-scorekeeper`, { method: 'POST' }),
  myScorekeeperGames: () => request<Game[]>('/api/games/scorekeeping/mine'),

  createContest: (gameId: number, reason: string) =>
    request<StatsContest>(`/api/games/${gameId}/contest`, {
      method: 'POST', body: JSON.stringify({ reason }),
    }),
  voteContest: (gameId: number, contestId: number, support: boolean) =>
    request<StatsContest>(`/api/games/${gameId}/contest/${contestId}/vote`, {
      method: 'POST', body: JSON.stringify({ support }),
    }),
  listContests: (gameId: number) => request<StatsContest[]>(`/api/games/${gameId}/contests`),

  proposeReschedule: (gameId: number, scheduledTime: string) =>
    request<GameReschedule>(`/api/games/${gameId}/reschedule`, {
      method: 'POST', body: JSON.stringify({ scheduled_time: scheduledTime }),
    }),
  voteReschedule: (gameId: number, rescheduleId: number, approved: boolean) =>
    request<GameReschedule>(`/api/games/${gameId}/reschedule/${rescheduleId}/vote`, {
      method: 'POST', body: JSON.stringify({ approved }),
    }),
  listRescheduleProposals: (gameId: number) =>
    request<GameReschedule[]>(`/api/games/${gameId}/reschedule`),

  submitStats: (gameId: number, stats: Array<{
    user_id: number; pts: number; reb: number; ast: number;
    stl: number; blk: number; tov: number;
    fgm: number; fga: number; three_pm: number; three_pa: number;
    ftm: number; fta: number;
  }>) => request<PlayerStats[]>(`/api/games/${gameId}/stats`, {
    method: 'POST', body: JSON.stringify({ stats }),
  }),

  getGameStats: (gameId: number) => request<PlayerStats[]>(`/api/games/${gameId}/stats`),
  getCareerStats: (userId: number) => request<CareerStats>(`/api/users/${userId}/stats`),
  getCareerStatsByGameType: (userId: number) =>
    request<import('@/lib/types').CareerStatsByType>(`/api/users/${userId}/stats/by-game-type`),
  getSkillHistory: (userId: number) =>
    request<import('@/lib/types').SkillHistoryEntry[]>(`/api/users/${userId}/skill-history`),
  getStatsHistory: (userId: number) => request<GameStatsHistoryEntry[]>(`/api/users/${userId}/stats/history`),

  sendMessage: (data: { game_id?: number; recipient_id?: number; content: string }) =>
    request<Message>('/api/messages', { method: 'POST', body: JSON.stringify(data) }),
  getGameMessages: (gameId: number) => request<Message[]>(`/api/messages/game/${gameId}`),
  getDmThread: (userId: number) => request<Message[]>(`/api/messages/dm/${userId}`),
  getConversations: () => request<ConversationPreview[]>('/api/messages/conversations'),

  createChallenge: (challengedId: number, scheduledTime?: string, message?: string) =>
    request<Challenge>('/api/challenges', {
      method: 'POST', body: JSON.stringify({
        challenged_id: challengedId,
        scheduled_time: scheduledTime || null,
        message: message || null,
      }),
    }),
  acceptChallenge: (id: number) =>
    request<Challenge>(`/api/challenges/${id}/accept`, { method: 'POST' }),
  declineChallenge: (id: number) =>
    request<Challenge>(`/api/challenges/${id}/decline`, { method: 'POST' }),
  submitChallengeScore: (id: number, myScore: number, opponentScore: number) =>
    request<Challenge>(`/api/challenges/${id}/submit-score`, {
      method: 'POST', body: JSON.stringify({ my_score: myScore, opponent_score: opponentScore }),
    }),
  confirmChallenge: (id: number) =>
    request<Challenge>(`/api/challenges/${id}/confirm`, { method: 'POST' }),
  listChallenges: (statusFilter?: string) => {
    const params = statusFilter ? `?status=${statusFilter}` : '';
    return request<Challenge[]>(`/api/challenges${params}`);
  },

  reportUser: (reportedId: number, reason: string, details?: string) =>
    request('/api/report', {
      method: 'POST', body: JSON.stringify({ reported_id: reportedId, reason, details }),
    }),
  blockUser: (userId: number) =>
    request(`/api/block/${userId}`, { method: 'POST' }),
  unblockUser: (userId: number) =>
    request(`/api/block/${userId}`, { method: 'DELETE' }),

  getWeather: () => request<{ current: Record<string, unknown>; forecast: Array<Record<string, unknown>> }>('/api/weather', { cache: 'no-store' }),
  chatWithPete: (message: string) =>
    request<{ reply: string; data?: Record<string, unknown> }>('/api/chat', {
      method: 'POST', body: JSON.stringify({ message }),
    }),
};

export { ApiError };
