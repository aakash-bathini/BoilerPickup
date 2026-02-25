export interface User {
  id: number;
  username: string;
  display_name: string;
  height: string | null;
  weight: number | null;
  preferred_position: string | null;
  gender: string | null;
  self_reported_skill: number;
  ai_skill_rating: number;
  skill_confidence: number;
  games_played: number;
  wins: number;
  losses: number;
  challenge_wins: number;
  challenge_losses: number;
  bio: string | null;
  is_disabled: boolean;
  nba_match?: { name: string; similarity: number; reason?: string; stats?: any };
  created_at: string;
}

export interface UserSearchResult {
  id: number;
  username: string;
  display_name: string;
  ai_skill_rating: number;
  preferred_position: string | null;
  games_played: number;
  wins: number;
  losses: number;
  challenge_wins?: number;
  challenge_losses?: number;
  wins_week: number;
  losses_week: number;
  challenge_wins_week: number;
  challenge_losses_week: number;
  skill_rating_change_week?: number | null;
  ppg?: number;
  rpg?: number;
  apg?: number;
  nba_match?: { name: string; similarity: number; reason?: string; stats?: any };
}

export interface GameParticipant {
  id: number;
  user_id: number;
  team: string;
  username: string | null;
  display_name: string | null;
  ai_skill_rating: number | null;
  preferred_position: string | null;
}

export interface Game {
  id: number;
  creator_id: number;
  game_type: string;
  scheduled_time: string;
  skill_min: number;
  skill_max: number;
  status: string;
  court_type: string;
  team_a_score: number | null;
  team_b_score: number | null;
  max_players: number;
  notes: string | null;
  created_at: string;
  participants: GameParticipant[];
  creator_name: string | null;
  scorekeeper_id: number | null;
  scorekeeper_status: string | null;
  scorekeeper_name: string | null;
  stats_finalized: boolean;
  stats_finalized_at: string | null;
  completed_at: string | null;
  win_prediction?: number | null;  // P(Team A wins), 0-1, when roster full
}

export interface GameReschedule {
  id: number;
  game_id: number;
  proposed_scheduled_time: string;
  proposed_by_id: number;
  status: string;
  votes_for: number;
  votes_against: number;
  total_participants: number;
  created_at: string;
}

export interface PlayerStats {
  id: number;
  user_id: number;
  game_id: number;
  pts: number;
  reb: number;
  ast: number;
  stl: number;
  blk: number;
  tov: number;
  fgm: number;
  fga: number;
  three_pm: number;
  three_pa: number;
  ftm: number;
  fta: number;
}

export interface CareerStats {
  games_played: number;
  wins: number;
  losses: number;
  win_rate: number;
  challenge_wins: number;
  challenge_losses: number;
  ppg: number;
  rpg: number;
  apg: number;
  spg: number;
  bpg: number;
  topg: number;
  fg_pct: number;
  three_pct: number;
  ft_pct: number;
  total_pts: number;
  total_reb: number;
  total_ast: number;
  total_stl: number;
  total_blk: number;
  total_tov: number;
}

export interface CareerStatsByGameType {
  games_played: number;
  ppg: number;
  rpg: number;
  apg: number;
  spg: number;
  bpg: number;
  topg: number;
  fg_pct: number;
  three_pct: number;
  ft_pct: number;
}

export interface CareerStatsByType {
  five_v_five: CareerStatsByGameType;
  three_v_three: CareerStatsByGameType;
  two_v_two: CareerStatsByGameType;
}

export interface SkillHistoryEntry {
  timestamp: string;
  rating: number;
}

export interface GameStatsHistoryEntry {
  game_id: number;
  game_type: string;
  scheduled_time: string;
  pts: number;
  reb: number;
  ast: number;
  stl: number;
  blk: number;
  tov: number;
  fgm: number;
  fga: number;
  three_pm: number;
  three_pa: number;
  ftm: number;
  fta: number;
  skill_before: number | null;
  skill_after: number | null;
}

export interface Message {
  id: number;
  sender_id: number;
  game_id: number | null;
  recipient_id: number | null;
  content: string;
  created_at: string;
  sender_name: string | null;
  sender_username: string | null;
}

export interface ConversationPreview {
  user_id: number;
  username: string;
  display_name: string;
  last_message: string;
  last_message_time: string;
}

export interface Token {
  access_token: string;
  token_type: string;
}

export interface ChallengeHistoryEntry {
  id: number;
  challenger_id: number;
  challenged_id: number;
  challenger_name: string | null;
  challenged_name: string | null;
  challenger_score: number | null;
  challenged_score: number | null;
  winner_id: number | null;
  completed_at: string | null;
}

export interface Challenge {
  id: number;
  challenger_id: number;
  challenged_id: number;
  status: string;
  scheduled_time: string | null;
  message: string | null;
  challenger_score: number | null;
  challenged_score: number | null;
  challenger_confirmed: boolean;
  challenged_confirmed: boolean;
  winner_id: number | null;
  created_at: string;
  completed_at: string | null;
  challenger_name: string | null;
  challenged_name: string | null;
  challenger_win_probability?: number | null;  // P(challenger wins)
}

export interface StatsContest {
  id: number;
  game_id: number;
  contester_id: number;
  reason: string;
  status: string;
  votes_for: number;
  votes_against: number;
  created_at: string;
  resolved_at: string | null;
  contester_name: string | null;
}
