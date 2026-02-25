'use client';

import { useEffect, useState, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { useAuth } from '@/lib/auth-context';
import { api, ApiError } from '@/lib/api';
import { Game } from '@/lib/types';
import { formatESTShort, statusColor } from '@/lib/utils';
import { motion, Variants } from 'framer-motion';
import { Activity, Target, Shield, Zap, Search, PlusCircle, Trophy, BarChart2, Edit2, XCircle, Users } from 'lucide-react';

const FADE_UP: Variants = {
  hidden: { opacity: 0, y: 20 },
  visible: { opacity: 1, y: 0, transition: { duration: 0.5, ease: 'easeOut' } },
};

const STAGGER: Variants = {
  hidden: { opacity: 0 },
  visible: { opacity: 1, transition: { staggerChildren: 0.1 } },
};

export default function DashboardPage() {
  const { user, loading: authLoading, refresh: refreshAuth } = useAuth();
  const router = useRouter();
  const [games, setGames] = useState<Game[]>([]);
  const [weather, setWeather] = useState<Record<string, unknown> | null>(null);
  const [loadingData, setLoadingData] = useState(true);
  const [isFirstVisit, setIsFirstVisit] = useState(false);
  const [editGameId, setEditGameId] = useState<number | null>(null);
  const [editDate, setEditDate] = useState('');
  const [editTime, setEditTime] = useState('');

  const loadData = useCallback(async (userId: number) => {
    const [g, w] = await Promise.all([
      api.listGames().catch(() => []),
      api.getWeather().catch(() => null),
    ]);
    const myGames = g.filter((game: Game) =>
      game.participants.some((p) => p.user_id === userId) && game.status !== 'completed'
    );
    setGames(myGames);
    if (w) setWeather(w.current as Record<string, unknown>);
    setLoadingData(false);
  }, []);

  const refreshWeather = useCallback(async () => {
    try {
      const w = await api.getWeather();
      if (w) setWeather(w.current as Record<string, unknown>);
    } catch {
      /* ignore */
    }
  }, []);

  useEffect(() => {
    if (!authLoading && !user) router.replace('/login');
  }, [user, authLoading, router]);

  useEffect(() => {
    if (!user) return;
    const firstKey = `bp_first_${user.id}`;
    if (!localStorage.getItem(firstKey)) {
      setIsFirstVisit(true);
      localStorage.setItem(firstKey, 'true');
    }

    refreshAuth();
    loadData(user.id);

    const handleFocus = () => {
      refreshAuth();
      loadData(user.id);
      refreshWeather();
    };
    window.addEventListener('focus', handleFocus);
    const weatherInterval = setInterval(refreshWeather, 5 * 60 * 1000);
    return () => {
      window.removeEventListener('focus', handleFocus);
      clearInterval(weatherInterval);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user?.id]);

  if (authLoading || !user) {
    return (
      <div className="min-h-screen bg-[#050505] flex items-center justify-center">
        <div className="w-10 h-10 border-2 border-gold-500 border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  const teamGames = user.games_played;
  const teamWins = user.wins;
  const teamLosses = user.losses;
  const teamRecord = `${teamWins}W-${teamLosses}L`;
  const teamWinRate = teamGames > 0 ? ((teamWins / teamGames) * 100).toFixed(0) : '—';

  const h2hWins = user.challenge_wins;
  const h2hLosses = user.challenge_losses;
  const h2hRecord = `${h2hWins}W-${h2hLosses}L`;
  const h2hTotal = h2hWins + h2hLosses;
  const h2hWinRate = h2hTotal > 0 ? ((h2hWins / h2hTotal) * 100).toFixed(0) : '—';

  const overallWins = teamWins + h2hWins;
  const overallLosses = teamLosses + h2hLosses;
  const overallRecord = `${overallWins}W-${overallLosses}L`;
  const totalGames = teamGames + h2hTotal;
  const overallWinRate = totalGames > 0 ? ((overallWins / totalGames) * 100).toFixed(0) : '—';

  return (
    <div className="min-h-screen bg-[#030303] text-zinc-100 pt-24 pb-12 px-4 selection:bg-gold-500/30">
      <motion.div initial="hidden" animate="visible" variants={STAGGER} className="max-w-7xl mx-auto space-y-8">

        {/* Header Dashboard Card */}
        <motion.div variants={FADE_UP} className="relative overflow-hidden rounded-[2rem] border border-white/10 bg-zinc-900/40 backdrop-blur-md p-8 md:p-12 shadow-2xl">
          <div className="absolute top-0 right-0 -m-32 w-96 h-96 bg-gold-500/10 blur-[100px] rounded-full" />
          <div className="relative z-10 flex flex-col md:flex-row items-start md:items-center justify-between gap-8">
            <div>
              <h1 className="text-3xl md:text-5xl font-black text-white tracking-tight mb-2">
                {isFirstVisit ? `Welcome, ${user.display_name} !` : `Welcome back, ${user.display_name}.`}
              </h1>
              <p className="text-zinc-400 font-light text-lg">
                {(isFirstVisit || totalGames === 0)
                  ? 'Your account is primed. Book a court and build your legacy.'
                  : 'Ready to dominate the hardwood today?'}
              </p>
            </div>

            <div className="flex items-center gap-4 shrink-0">
              <div className="flex flex-col items-center justify-center px-6 py-4 rounded-2xl bg-gradient-to-br from-gold-500/20 to-gold-600/5 border border-gold-500/30 shadow-[0_0_30px_-5px_rgba(207,185,145,0.2)]">
                <div className="text-3xl font-black text-gold-400 drop-shadow-md">{user.ai_skill_rating.toFixed(1)}</div>
                <div className="text-xs text-gold-200/60 uppercase tracking-widest mt-1 font-bold">Player Rating</div>
              </div>
              {weather && (
                <div className="flex flex-col items-center justify-center px-6 py-4 rounded-2xl bg-emerald-500/10 border border-emerald-500/20 shadow-lg">
                  <div className="text-3xl font-bold text-emerald-400">{String(weather.temperature)}°F</div>
                  <div className="text-xs text-emerald-200/60 uppercase tracking-widest mt-1 font-bold">West Lafayette</div>
                </div>
              )}
            </div>

            {user.nba_match && (
              <div className="hidden lg:flex flex-col justify-center px-6 py-4 rounded-2xl bg-zinc-900/60 border border-gold-500/10 shadow-lg shrink-0 animate-scale-in">
                <div className="text-xl font-bold text-white">Plays like <span className="text-gold-400">{user.nba_match.name}</span></div>
                <div className="text-xs text-zinc-500 mt-1 uppercase tracking-wider font-bold flex items-center gap-2">
                  <Activity className="w-3 h-3" /> {user.nba_match.similarity.toFixed(1)}% AI Match
                </div>
              </div>
            )}
          </div>
        </motion.div>

        {/* Stats Grid */}
        <motion.div variants={STAGGER} className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          {[
            { label: 'Team Record', value: teamRecord, sub: teamGames > 0 ? `${teamWinRate}% Win Rate` : 'No games', icon: <Users className="w-5 h-5 text-zinc-400" /> },
            { label: '1v1 Record', value: h2hRecord, sub: h2hTotal > 0 ? `${h2hWinRate}% Win Rate` : 'No challenges', icon: <Target className="w-5 h-5 text-orange-400" /> },
            { label: 'Overall', value: overallRecord, sub: totalGames > 0 ? `${overallWinRate}% Win Rate` : '—', icon: <Trophy className="w-5 h-5 text-gold-400" />, bar: totalGames > 0 && overallWinRate !== '—' ? Number(overallWinRate) / 100 : null },
            { label: 'Skill Certainty', value: `${(user.skill_confidence * 100).toFixed(0)}% `, sub: 'Rating Consistency', icon: <Activity className="w-5 h-5 text-blue-400" />, bar: user.skill_confidence },
          ].map((s) => (
            <motion.div key={s.label} variants={FADE_UP} className="group bg-zinc-900/40 border border-white/5 hover:border-white/10 p-6 rounded-3xl transition-all duration-300">
              <div className="flex justify-between items-start mb-4">
                <div className="p-2 bg-white/5 rounded-xl border border-white/5 group-hover:bg-white/10 transition-colors">
                  {s.icon}
                </div>
              </div>
              <div className="text-2xl font-black text-white tracking-tight mb-1">{s.value}</div>
              <div className="text-sm text-zinc-500 font-medium">{s.label}</div>
              {s.sub && <div className="text-xs text-zinc-600 mt-1">{s.sub}</div>}
              {s.bar != null && (
                <div className="mt-3 h-1.5 rounded-full bg-zinc-800 overflow-hidden">
                  <div
                    className="h-full rounded-full bg-gradient-to-r from-zinc-500 to-white transition-all duration-1000 ease-out"
                    style={{ width: `${Math.min(100, s.bar * 100)}% ` }}
                  />
                </div>
              )}
            </motion.div>
          ))}
        </motion.div>

        {/* Action Grid */}
        <motion.div variants={STAGGER} className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {[
            { title: 'Host Game', desc: 'Secure the court', icon: <PlusCircle className="w-6 h-6 text-emerald-400" />, href: '/games/create', bg: 'bg-emerald-500/10 text-emerald-400' },
            { title: 'Find Game', desc: 'Join the action', icon: <Search className="w-6 h-6 text-blue-400" />, href: '/games', bg: 'bg-blue-500/10 text-blue-400' },
            { title: '1v1 Clash', desc: 'Settle the debate', icon: <Shield className="w-6 h-6 text-orange-400" />, href: '/challenges', bg: 'bg-orange-500/10 text-orange-400' },
            { title: 'Rankings', desc: 'See where you stand', icon: <BarChart2 className="w-6 h-6 text-gold-400" />, href: '/leaderboard', bg: 'bg-gold-500/10 text-gold-400' },
          ].map((action) => (
            <Link key={action.title} href={action.href}>
              <motion.div variants={FADE_UP} className="group relative overflow-hidden bg-zinc-900/30 border border-white/5 hover:bg-zinc-800/50 p-6 rounded-3xl transition-all duration-300 h-full flex flex-col justify-center">
                <div className="absolute inset-0 bg-gradient-to-br from-white/5 to-transparent opacity-0 group-hover:opacity-100 transition-opacity" />
                <div className={`w-12 h-12 rounded-2xl flex items-center justify-center mb-4 shadow-inner ${action.bg} group-hover:scale-110 transition-transform duration-300`}>
                  {action.icon}
                </div>
                <div className="text-lg font-bold text-white mb-1">{action.title}</div>
                <div className="text-sm text-zinc-500">{action.desc}</div>
              </motion.div>
            </Link>
          ))}
        </motion.div>

        {/* Upcoming Games Section */}
        <motion.div variants={FADE_UP} className="bg-zinc-900/40 border border-white/5 rounded-[2rem] p-8 mt-4 shadow-xl">
          <div className="flex flex-wrap items-center justify-between gap-4 mb-8">
            <h2 className="text-2xl font-bold text-white tracking-tight flex items-center gap-3">
              <Zap className="w-6 h-6 text-gold-400" /> Active Schedule
            </h2>
            <div className="flex gap-4">
              <Link href="/games" className="text-sm text-zinc-400 hover:text-white transition-colors font-medium">Browse All</Link>
            </div>
          </div>

          {loadingData ? (
            <div className="flex justify-center items-center py-12">
              <div className="w-8 h-8 border-2 border-gold-500 border-t-transparent rounded-full animate-spin" />
            </div>
          ) : games.length === 0 ? (
            <div className="text-center py-16 border border-dashed border-white/5 rounded-3xl bg-zinc-900/20">
              <div className="w-16 h-16 bg-white/5 rounded-full flex items-center justify-center mx-auto mb-4">
                <Search className="w-8 h-8 text-zinc-500" />
              </div>
              <p className="text-lg font-medium text-white mb-2">No upcoming games scheduled</p>
              <p className="text-zinc-500 text-sm mb-6 max-w-sm mx-auto">Get out there and hoop. Join an existing game or organize your own full-court run.</p>
              <Link href="/games" className="inline-flex items-center justify-center px-6 py-3 text-sm font-bold text-black bg-gold-400 hover:bg-gold-300 rounded-xl transition-all">
                Find a Game
              </Link>
            </div>
          ) : (
            <div className="space-y-4">
              {games.map(g => {
                const isCreator = g.creator_id === user.id;
                const canEdit = isCreator && (g.status === 'open' || g.status === 'full') && g.participants.length <= 1;
                const canDelete = isCreator && (g.status === 'open' || g.status === 'full') && g.participants.length <= 1;
                const isEditing = editGameId === g.id;

                return (
                  <motion.div key={g.id} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="group rounded-2xl bg-zinc-900/60 border border-white/5 hover:border-gold-500/20 transition-all duration-300 overflow-hidden">
                    <div className="flex flex-col sm:flex-row p-5 gap-5 items-start sm:items-center">
                      <Link href={`/games/${g.id}`} className="flex-1 flex items-center gap-5 min-w-0 pointer-events-auto">
                        <div className="w-14 h-14 rounded-2xl bg-gold-500/10 border border-gold-500/20 flex flex-col items-center justify-center shrink-0 group-hover:bg-gold-500/20 transition-colors">
                          <span className="text-gold-400 font-black text-sm">{g.game_type}</span>
                        </div>
                        <div>
                          <h3 className="text-lg font-bold text-white group-hover:text-gold-100 transition-colors">
                            {g.game_type} {g.court_type === 'halfcourt' ? 'Half' : 'Full'} Court
                          </h3>
                          <div className="flex items-center gap-2 mt-1">
                            <span className="text-sm text-zinc-400 font-medium">{formatESTShort(g.scheduled_time)}</span>
                            <span className="w-1 h-1 rounded-full bg-zinc-600" />
                            <span className="text-sm text-zinc-500">{g.participants.length}/{g.max_players} Filled</span>
                          </div>
                        </div>
                      </Link>

                      <div className="flex items-center gap-3 w-full sm:w-auto justify-between sm:justify-end shrink-0 pl-16 sm:pl-0 border-t sm:border-0 border-white/5 pt-4 sm:pt-0">
                        <span className={`px-3 py-1 rounded-full text-xs font-bold uppercase tracking-wider ${statusColor(g.status)} border border-current`}>
                          {g.status.replace('_', ' ')}
                        </span>

                        <div className="flex items-center gap-2">
                          {canEdit && (
                            <button
                              onClick={(e) => {
                                e.preventDefault();
                                const d = new Date(g.scheduled_time);
                                setEditDate(d.toISOString().slice(0, 10));
                                setEditTime(d.toTimeString().slice(0, 5));
                                setEditGameId(isEditing ? null : g.id);
                              }}
                              className="p-2 text-zinc-400 hover:text-gold-400 hover:bg-gold-500/10 rounded-lg transition-colors"
                              title={isEditing ? 'Cancel Edit' : 'Edit Game'}
                            >
                              {isEditing ? <XCircle className="w-5 h-5" /> : <Edit2 className="w-5 h-5" />}
                            </button>
                          )}
                          {canDelete && !isEditing && (
                            <button
                              onClick={async (e) => {
                                e.preventDefault();
                                if (!confirm('Are you sure you want to cancel this game?')) return;
                                try {
                                  await api.deleteGame(g.id);
                                  loadData(user.id);
                                } catch (err) {
                                  alert(err instanceof ApiError ? err.message : 'Failed');
                                }
                              }}
                              className="px-3 py-1.5 text-xs font-bold text-red-400 hover:text-white hover:bg-red-500 rounded-lg transition-colors"
                            >
                              Cancel
                            </button>
                          )}
                        </div>
                      </div>
                    </div>

                    {isEditing && (
                      <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: 'auto', opacity: 1 }} className="px-5 pb-5 pt-0 overflow-hidden">
                        <div className="bg-black/30 rounded-xl p-5 border border-white/5">
                          <h4 className="text-sm font-semibold text-white mb-4">Reschedule Game</h4>
                          <div className="grid sm:grid-cols-2 gap-4 mb-5">
                            <div>
                              <label className="block text-xs font-medium text-zinc-500 uppercase tracking-widest mb-1.5">Date</label>
                              <input type="date" value={editDate} onChange={e => setEditDate(e.target.value)} className="w-full bg-zinc-900 border border-white/10 rounded-lg px-4 py-2.5 text-white focus:outline-none focus:border-gold-500 transition-colors" />
                            </div>
                            <div>
                              <label className="block text-xs font-medium text-zinc-500 uppercase tracking-widest mb-1.5">Time (EST)</label>
                              <input type="time" value={editTime} onChange={e => setEditTime(e.target.value)} className="w-full bg-zinc-900 border border-white/10 rounded-lg px-4 py-2.5 text-white focus:outline-none focus:border-gold-500 transition-colors" />
                            </div>
                          </div>
                          <div className="flex gap-3">
                            <button
                              onClick={async () => {
                                if (!editDate || !editTime) return;
                                try {
                                  const scheduledTime = `${editDate}T${editTime}:00-05:00`;
                                  await api.updateGame(g.id, { scheduled_time: scheduledTime });
                                  loadData(user.id);
                                  setEditGameId(null);
                                } catch (err) {
                                  alert(err instanceof ApiError ? err.message : 'Failed');
                                }
                              }}
                              className="bg-gold-500 hover:bg-gold-400 text-black font-bold px-6 py-2 rounded-lg transition-colors text-sm"
                            >
                              Save Changes
                            </button>
                            <button onClick={() => setEditGameId(null)} className="bg-zinc-800 hover:bg-zinc-700 text-white font-medium px-6 py-2 rounded-lg transition-colors text-sm">
                              Cancel
                            </button>
                          </div>
                        </div>
                      </motion.div>
                    )}
                  </motion.div>
                );
              })}
            </div>
          )}
        </motion.div>

      </motion.div>
    </div >
  );
}
