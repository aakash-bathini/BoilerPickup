'use client';

import { useEffect, useState, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { useAuth } from '@/lib/auth-context';
import { api, ApiError } from '@/lib/api';
import { Game } from '@/lib/types';
import { formatESTShort, statusColor } from '@/lib/utils';

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
      game.participants.some(p => p.user_id === userId) && game.status !== 'completed'
    );
    setGames(myGames);
    if (w) setWeather(w.current as Record<string, unknown>);
    setLoadingData(false);
  }, []);

  const refreshWeather = useCallback(async () => {
    try {
      const w = await api.getWeather();
      if (w) setWeather(w.current as Record<string, unknown>);
    } catch { /* ignore */ }
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
      <div className="page-container">
        <div className="space-y-6">
          {[1, 2, 3].map(i => (
            <div key={i} className="glass-card p-6 animate-pulse">
              <div className="h-4 bg-dark-50 rounded w-1/3 mb-4" />
              <div className="h-3 bg-dark-50 rounded w-2/3" />
            </div>
          ))}
        </div>
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
  const overallWinRate = totalGames > 0 ? (((overallWins / totalGames) * 100).toFixed(0)) : '—';

  return (
    <div className="page-container">
      <div className="mb-8 animate-slide-up">
        <div className="glass-card p-6 md:p-8 flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
          <div>
            <h1 className="text-2xl md:text-3xl font-bold text-white">
              {isFirstVisit ? `Welcome to Boiler Pickup, ${user.display_name}!` : `Welcome back, ${user.display_name}`}
            </h1>
            {(isFirstVisit || totalGames === 0) && (
              <p className="text-gray-400 mt-1">
                {isFirstVisit
                  ? 'Your account is set up and ready to go. Find a game or create your own!'
                  : 'You haven\'t played any games yet. Browse available games or create one!'}
              </p>
            )}
          </div>
          <div className="flex items-center gap-3">
            <div className="text-center px-4 py-2 rounded-xl bg-gold-500/10 border border-gold-500/20">
              <div className="text-2xl font-black text-gold-400">{user.ai_skill_rating.toFixed(1)}</div>
              <div className="text-[10px] text-gray-500 uppercase tracking-wider">Skill (1–10)</div>
            </div>
            {weather && (
              <div className="text-center px-4 py-2 rounded-xl bg-blue-500/10 border border-blue-500/20">
                <div className="text-2xl font-bold text-blue-400">{String(weather.temperature)}°F</div>
                <div className="text-[10px] text-gray-500 uppercase tracking-wider">CoRec · West Lafayette</div>
              </div>
            )}
          </div>
        </div>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
        {[
          { label: 'Team Games', value: teamRecord, sub: teamGames > 0 ? `${teamWinRate}% win rate` : 'No games yet', color: 'text-white', bar: null as number | null },
          { label: '1v1 Head-to-Head', value: h2hRecord, sub: h2hTotal > 0 ? `${h2hWinRate}% win rate` : 'No challenges yet', color: 'text-orange-400', bar: null },
          { label: 'Overall', value: overallRecord, sub: totalGames > 0 ? `${overallWinRate}% win rate` : '—', color: 'text-emerald-400', bar: totalGames > 0 && overallWinRate !== '—' ? Number(overallWinRate) / 100 : null },
          { label: 'Rating Confidence', value: `${(user.skill_confidence * 100).toFixed(0)}%`, sub: 'How certain we are about your skill', color: 'text-blue-400', bar: user.skill_confidence },
        ].map((s, i) => (
          <div key={s.label} className="glass-card p-4 text-center animate-slide-up transition-all duration-300 hover:border-gold-500/20" style={{ animationDelay: `${i * 0.05}s` }}>
            <div className={`text-2xl font-bold ${s.color}`}>{s.value}</div>
            <div className="text-xs text-gray-500 mt-1">{s.label}</div>
            {s.sub && <div className="text-[10px] text-gray-600 mt-0.5">{s.sub}</div>}
            {s.bar != null && (
              <div className="mt-2 h-1 rounded-full bg-dark-400 overflow-hidden">
                <div
                  className="h-full rounded-full bg-gradient-to-r from-gold-500 to-gold-400 transition-all duration-500"
                  style={{ width: `${Math.min(100, s.bar * 100)}%` }}
                />
              </div>
            )}
          </div>
        ))}
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
        <Link href="/games/create" className="glass-card-hover p-5 flex items-center gap-4 group animate-slide-up transition-all duration-300" style={{ animationDelay: '0.1s' }}>
          <div className="w-12 h-12 rounded-xl bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center group-hover:scale-110 transition-transform duration-300">
            <svg className="w-6 h-6 text-emerald-400" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" /></svg>
          </div>
          <div>
            <div className="text-white font-semibold">Create Game</div>
            <div className="text-xs text-gray-500">Organize at CoRec</div>
          </div>
        </Link>
        <Link href="/games" className="glass-card-hover p-5 flex items-center gap-4 group animate-slide-up transition-all duration-300" style={{ animationDelay: '0.15s' }}>
          <div className="w-12 h-12 rounded-xl bg-blue-500/10 border border-blue-500/20 flex items-center justify-center group-hover:scale-110 transition-transform duration-300">
            <svg className="w-6 h-6 text-blue-400" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" /></svg>
          </div>
          <div>
            <div className="text-white font-semibold">Find Games</div>
            <div className="text-xs text-gray-500">Browse by skill</div>
          </div>
        </Link>
        <Link href="/challenges" className="glass-card-hover p-5 flex items-center gap-4 group animate-slide-up transition-all duration-300" style={{ animationDelay: '0.2s' }}>
          <div className="w-12 h-12 rounded-xl bg-orange-500/10 border border-orange-500/20 flex items-center justify-center group-hover:scale-110 transition-transform duration-300">
            <svg className="w-6 h-6 text-orange-400" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" /></svg>
          </div>
          <div>
            <div className="text-white font-semibold">1v1 Challenges</div>
            <div className="text-xs text-gray-500">Prove yourself</div>
          </div>
        </Link>
        <Link href="/leaderboard" className="glass-card-hover p-5 flex items-center gap-4 group animate-slide-up transition-all duration-300" style={{ animationDelay: '0.25s' }}>
          <div className="w-12 h-12 rounded-xl bg-gold-500/10 border border-gold-500/20 flex items-center justify-center group-hover:scale-110 transition-transform duration-300">
            <svg className="w-6 h-6 text-gold-400" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 3v4M3 5h4M6 17v4m-2-2h4m5-16l2.286 6.857L21 12l-5.714 2.143L13 21l-2.286-6.857L5 12l5.714-2.143L13 3z" /></svg>
          </div>
          <div>
            <div className="text-white font-semibold">Rankings</div>
            <div className="text-xs text-gray-500">Leaderboard</div>
          </div>
        </Link>
      </div>

      <div className="animate-slide-up" style={{ animationDelay: '0.25s' }}>
        <div className="flex flex-wrap items-center justify-between gap-4 mb-4">
          <h2 className="text-xl font-bold text-white">Your Upcoming Games</h2>
          <div className="flex gap-2">
            <Link href="/games" className="text-sm text-gold-400 hover:text-gold-300 font-medium">Browse Games</Link>
            <span className="text-gray-600">·</span>
            <Link href="/games/create" className="text-sm text-gold-400 hover:text-gold-300 font-medium">Create Game</Link>
          </div>
        </div>
        {loadingData ? (
          <div className="glass-card p-8 text-center text-gray-500">Loading games...</div>
        ) : games.length === 0 ? (
          <div className="glass-card p-8 text-center">
            <div className="text-gray-500 mb-3">No upcoming games</div>
            <Link href="/games" className="text-gold-400 hover:text-gold-300 text-sm font-medium">Browse available games →</Link>
            <p className="text-xs text-gray-600 mt-4">Need help? Tap the mascot in the corner to chat with Coach Pete.</p>
          </div>
        ) : (
          <div className="space-y-3">
            {games.map(g => {
              const isCreator = g.creator_id === user.id;
              const canEdit = isCreator && (g.status === 'open' || g.status === 'full') && g.participants.length <= 1;
              const canDelete = isCreator && (g.status === 'open' || g.status === 'full') && g.participants.length <= 1;
              const isEditing = editGameId === g.id;
              return (
                <div key={g.id} className="glass-card-hover overflow-hidden">
                  <div className="p-4 flex items-center justify-between gap-4 group">
                    <Link href={`/games/${g.id}`} className="flex-1 flex items-center gap-4 min-w-0">
                      <div className="w-12 h-12 rounded-xl bg-gold-500/10 border border-gold-500/20 flex items-center justify-center shrink-0">
                        <span className="text-gold-400 font-bold text-sm">{g.game_type}</span>
                      </div>
                      <div className="min-w-0">
                        <div className="text-white font-medium">{g.game_type} {g.court_type === 'halfcourt' ? 'Half' : 'Full'} Court</div>
                        <div className="text-xs text-gray-500">{formatESTShort(g.scheduled_time)}</div>
                      </div>
                    </Link>
                    <div className="flex items-center gap-3 shrink-0">
                      <div className="text-xs text-gray-500">{g.participants.length}/{g.max_players}</div>
                      <span className={`badge ${statusColor(g.status)}`}>{g.status.replace('_', ' ')}</span>
                      {canEdit && (
                        <button
                          onClick={(e) => {
                            e.preventDefault();
                            const d = new Date(g.scheduled_time);
                            setEditDate(d.toISOString().slice(0, 10));
                            setEditTime(d.toTimeString().slice(0, 5));
                            setEditGameId(isEditing ? null : g.id);
                          }}
                          className="text-xs text-gold-400 hover:text-gold-300 font-medium"
                        >
                          {isEditing ? 'Cancel' : 'Edit'}
                        </button>
                      )}
                      {canDelete && !isEditing && (
                      <button
                        onClick={async (e) => {
                          e.preventDefault();
                          if (!confirm('Delete this game?')) return;
                          try {
                            await api.deleteGame(g.id);
                            loadData(user.id);
                          } catch (err) {
                            alert(err instanceof ApiError ? err.message : 'Failed');
                          }
                        }}
                        className="text-xs text-red-400 hover:text-red-300 font-medium"
                      >
                        Delete
                      </button>
                    )}
                  </div>
                </div>
                {isEditing && (
                  <div className="px-4 pb-4 pt-0 border-t border-gold-500/10 mt-0 animate-fade-in">
                    <div className="bg-dark-300/50 rounded-xl p-4 mt-2">
                      <h3 className="text-sm font-semibold text-white mb-3">Edit date & time</h3>
                      <div className="grid grid-cols-2 gap-4 mb-4">
                        <div>
                          <label className="label-text">Date</label>
                          <input type="date" value={editDate} onChange={e => setEditDate(e.target.value)} className="input-field" />
                        </div>
                        <div>
                          <label className="label-text">Time (EST)</label>
                          <input type="time" value={editTime} onChange={e => setEditTime(e.target.value)} className="input-field" />
                        </div>
                      </div>
                      <div className="flex gap-2">
                        <button
                          onClick={async () => {
                            if (!editDate || !editTime) { alert('Enter date and time'); return; }
                            try {
                              const scheduledTime = `${editDate}T${editTime}:00-05:00`;
                              await api.updateGame(g.id, { scheduled_time: scheduledTime });
                              loadData(user.id);
                              setEditGameId(null);
                            } catch (err) {
                              alert(err instanceof ApiError ? err.message : 'Failed');
                            }
                          }}
                          className="btn-primary flex-1"
                        >
                          Save
                        </button>
                        <button onClick={() => setEditGameId(null)} className="btn-secondary">Cancel</button>
                      </div>
                    </div>
                  </div>
                )}
              </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
