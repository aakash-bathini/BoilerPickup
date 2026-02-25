'use client';

import { useEffect, useState, useRef, useCallback } from 'react';
import { useParams, useRouter } from 'next/navigation';
import Link from 'next/link';
import { useAuth } from '@/lib/auth-context';
import { api, ApiError } from '@/lib/api';
import { Game, GameReschedule, PlayerStats, Message, StatsContest, UserSearchResult } from '@/lib/types';
import { formatEST, statusColor, skillColor, timeAgo } from '@/lib/utils';

export default function GameDetailPage() {
  const params = useParams();
  const { user, refresh: refreshAuth } = useAuth();
  const router = useRouter();
  const gameId = Number(params.id);
  const [game, setGame] = useState<Game | null>(null);
  const [stats, setStats] = useState<PlayerStats[]>([]);
  const [messages, setMessages] = useState<Message[]>([]);
  const [contests, setContests] = useState<StatsContest[]>([]);
  const [rescheduleProposals, setRescheduleProposals] = useState<GameReschedule[]>([]);
  const [showReschedule, setShowReschedule] = useState(false);
  const [showEdit, setShowEdit] = useState(false);
  const [editDate, setEditDate] = useState('');
  const [editTime, setEditTime] = useState('');
  const [rescheduleDate, setRescheduleDate] = useState('');
  const [rescheduleTime, setRescheduleTime] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [msgInput, setMsgInput] = useState('');
  const [showComplete, setShowComplete] = useState(false);
  const [scoreA, setScoreA] = useState(0);
  const [scoreB, setScoreB] = useState(0);
  const [showStats, setShowStats] = useState(false);
  const [statEntries, setStatEntries] = useState<Record<number, Record<string, number>>>({});
  const [contestReason, setContestReason] = useState('');
  const [skSearch, setSkSearch] = useState('');
  const [skResults, setSkResults] = useState<UserSearchResult[]>([]);
  const chatEnd = useRef<HTMLDivElement>(null);

  const loadData = useCallback(async () => {
    try {
      const g = await api.getGame(gameId);
      setGame(g);
      if (g.status === 'completed' || g.status === 'in_progress') {
        api.getGameStats(gameId).then(setStats).catch(() => {});
        api.listContests(gameId).then(setContests).catch(() => {});
      }
      if (g.status === 'open' || g.status === 'full') {
        api.listRescheduleProposals(gameId).then(setRescheduleProposals).catch(() => []);
      }
      const isParticipant = g.participants.some(p => p.user_id === user?.id);
      const isSK = g.scorekeeper_id === user?.id;
      if (isParticipant || isSK) {
        api.getGameMessages(gameId).then(setMessages).catch(() => {});
      }
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Failed to load game');
    } finally {
      setLoading(false);
    }
  }, [gameId, user?.id]);

  useEffect(() => { loadData(); }, [loadData]);

  useEffect(() => {
    chatEnd.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  useEffect(() => {
    if (!game) return;
    const interval = setInterval(() => {
      const isP = game.participants.some(p => p.user_id === user?.id);
      const isSK = game.scorekeeper_id === user?.id;
      if (isP || isSK) api.getGameMessages(gameId).then(setMessages).catch(() => {});
    }, 5000);
    return () => clearInterval(interval);
  }, [game, gameId, user?.id]);

  if (loading) return <div className="page-container"><div className="glass-card p-12 text-center text-gray-500">Loading game...</div></div>;
  if (error || !game) return <div className="page-container"><div className="glass-card p-12 text-center text-red-400">{error || 'Game not found'}</div></div>;
  if (!user) { router.replace('/login'); return null; }

  const isCreator = game.creator_id === user.id;
  const isSK = game.scorekeeper_id === user.id;
  const isParticipant = game.participants.some(p => p.user_id === user.id);
  const canJoin = game.status === 'open' && !isParticipant;
  const canLeave = (game.status === 'open' || game.status === 'full') && isParticipant && !isCreator;
  const canStart = isCreator && (game.status === 'open' || game.status === 'full') && game.participants.length >= game.max_players;
  const canComplete = (isCreator || isSK) && game.status === 'in_progress';
  const canSubmitStats = (isCreator || isSK) && (game.status === 'in_progress' || game.status === 'completed') && !game.stats_finalized;
  const canDelete = isCreator && (game.status === 'open' || game.status === 'full') && game.participants.length <= 1;
  const canEdit = isCreator && (game.status === 'open' || game.status === 'full') && game.participants.length <= 1;
  const canProposeReschedule = (game.status === 'open' || game.status === 'full') && isCreator && game.participants.length > 1;
  const canReschedule = (game.status === 'open' || game.status === 'full') && (isCreator || isParticipant);
  const pendingReschedule = rescheduleProposals.find(r => r.status === 'pending');
  const teamA = game.participants.filter(p => p.team === 'A');
  const teamB = game.participants.filter(p => p.team === 'B');
  const unassigned = game.participants.filter(p => p.team === 'unassigned');

  const handleAction = async (action: () => Promise<Game>) => {
    try {
      const g = await action();
      setGame(g);
      refreshAuth();
    } catch (err) {
      alert(err instanceof ApiError ? err.message : 'Action failed');
    }
  };

  const sendMsg = async () => {
    if (!msgInput.trim()) return;
    try {
      await api.sendMessage({ game_id: gameId, content: msgInput });
      setMsgInput('');
      const msgs = await api.getGameMessages(gameId);
      setMessages(msgs);
    } catch { /* ignore */ }
  };

  const handleStats = async () => {
    const entries = Object.entries(statEntries).map(([uid, s]) => ({
      user_id: Number(uid), pts: s.pts || 0, reb: s.reb || 0, ast: s.ast || 0,
      stl: s.stl || 0, blk: s.blk || 0, tov: s.tov || 0,
      fgm: s.fgm || 0, fga: s.fga || 0, three_pm: s.three_pm || 0, three_pa: s.three_pa || 0,
      ftm: s.ftm || 0, fta: s.fta || 0,
    }));
    if (entries.length === 0) { alert('Enter stats for at least one player'); return; }
    try {
      await api.submitStats(gameId, entries);
      const s = await api.getGameStats(gameId);
      setStats(s);
      setShowStats(false);
      refreshAuth();
      alert('Stats submitted successfully');
    } catch (err) {
      alert(err instanceof ApiError ? err.message : 'Failed to submit stats');
    }
  };

  const updateStat = (userId: number, field: string, value: number) => {
    setStatEntries(prev => ({ ...prev, [userId]: { ...(prev[userId] || {}), [field]: value } }));
  };

  const searchSK = async (q: string) => {
    setSkSearch(q);
    if (q.length < 2) { setSkResults([]); return; }
    try { setSkResults(await api.searchUsers(q)); } catch { setSkResults([]); }
  };

  const STAT_FIELDS = ['pts', 'reb', 'ast', 'stl', 'blk', 'tov', 'fgm', 'fga', 'three_pm', 'three_pa', 'ftm', 'fta'];
  const STAT_LABELS: Record<string, string> = { pts: 'PTS', reb: 'REB', ast: 'AST', stl: 'STL', blk: 'BLK', tov: 'TOV', fgm: 'FGM', fga: 'FGA', three_pm: '3PM', three_pa: '3PA', ftm: 'FTM', fta: 'FTA' };

  return (
    <div className="page-container max-w-5xl mx-auto">
      <div className="glass-card p-6 mb-6 animate-slide-up">
        <div className="flex flex-wrap items-center gap-3 mb-4">
          <span className="px-3 py-1.5 rounded-lg bg-gold-500/10 text-gold-400 font-bold">{game.game_type}</span>
          <span className={`badge ${statusColor(game.status)}`}>{game.status.replace('_', ' ')}</span>
          <span className="text-sm text-gray-500">{game.court_type === 'halfcourt' ? 'Half Court' : 'Full Court'}</span>
        </div>
        <div className="text-sm text-gray-400 mb-2">{formatEST(game.scheduled_time)}</div>
        <div className="flex flex-wrap gap-4 text-xs text-gray-500">
          <span>Skill: {game.skill_min.toFixed(0)}-{game.skill_max.toFixed(0)}</span>
          <span>Players: {game.participants.length}/{game.max_players}</span>
          {game.creator_name && <span>Created by {game.creator_name}</span>}
        </div>
        {game.notes && <p className="mt-3 text-sm text-gray-400 bg-dark-300/50 rounded-lg p-3">{game.notes}</p>}

        {(game.status === 'full' || game.status === 'in_progress') && game.win_prediction != null && (
          <div className="mt-4 flex items-center justify-center gap-4 py-3 px-4 bg-gold-500/5 border border-gold-500/20 rounded-xl">
            <span className="text-xs text-gray-500 uppercase tracking-wider">Win predictor</span>
            <div className="flex items-center gap-3">
              <span className={`text-sm font-bold ${game.win_prediction >= 0.5 ? 'text-gold-400' : 'text-gray-400'}`}>
                Team A {(game.win_prediction * 100).toFixed(0)}%
              </span>
              <span className="text-gray-600">—</span>
              <span className={`text-sm font-bold ${game.win_prediction < 0.5 ? 'text-gold-400' : 'text-gray-400'}`}>
                Team B {((1 - game.win_prediction) * 100).toFixed(0)}%
              </span>
            </div>
            <span className="text-[10px] text-gray-600">ML model · skill, height, stats, wins</span>
          </div>
        )}

        {game.status === 'completed' && game.team_a_score !== null && (
          <div className="mt-4 flex items-center justify-center gap-6 py-4 bg-dark-300/50 rounded-xl">
            <div className="text-center"><div className="text-xs text-gray-500 mb-1">Team A</div><div className="text-3xl font-black text-white">{game.team_a_score}</div></div>
            <div className="text-gray-600 text-sm">vs</div>
            <div className="text-center"><div className="text-xs text-gray-500 mb-1">Team B</div><div className="text-3xl font-black text-white">{game.team_b_score}</div></div>
          </div>
        )}

        <div className="flex flex-wrap gap-2 mt-4">
          {canJoin && <button onClick={() => handleAction(() => api.joinGame(gameId))} className="btn-primary">Join Game</button>}
          {canLeave && <button onClick={() => handleAction(() => api.leaveGame(gameId))} className="btn-danger">Leave Game</button>}
          {canStart && <button onClick={() => handleAction(() => api.startGame(gameId))} className="btn-primary">Start Game</button>}
          {canComplete && <button onClick={() => setShowComplete(true)} className="btn-primary">Complete Game</button>}
          {canSubmitStats && <button onClick={() => setShowStats(true)} className="btn-secondary">Enter Stats</button>}
          {canEdit && (
            <button onClick={() => {
              const d = new Date(game.scheduled_time);
              setEditDate(d.toISOString().slice(0, 10));
              setEditTime(d.toTimeString().slice(0, 5));
              setShowEdit(true);
            }} className="btn-secondary">Edit Game</button>
          )}
          {canDelete && (
            <button
              onClick={async () => {
                if (!confirm('Delete this game? No one else has joined yet.')) return;
                try {
                  await api.deleteGame(gameId);
                  router.push('/games');
                } catch (err) {
                  alert(err instanceof ApiError ? err.message : 'Failed to delete');
                }
              }}
              className="btn-danger"
            >
              Delete Game
            </button>
          )}
          {canProposeReschedule && !pendingReschedule && (
            <button onClick={() => setShowReschedule(true)} className="btn-secondary">Propose Reschedule</button>
          )}
        </div>

        {showEdit && (
          <div className="mt-4 glass-card p-4 space-y-3">
            <h3 className="text-sm font-semibold text-white">Edit Game (no one else has joined)</h3>
            <div className="grid grid-cols-2 gap-4">
              <div><label className="text-xs text-gray-500">Date</label><input type="date" value={editDate} onChange={e => setEditDate(e.target.value)} className="input-field" /></div>
              <div><label className="text-xs text-gray-500">Time (EST)</label><input type="time" value={editTime} onChange={e => setEditTime(e.target.value)} className="input-field" /></div>
            </div>
            <div className="flex gap-2">
              <button onClick={async () => {
                if (!editDate || !editTime) { alert('Enter date and time'); return; }
                try {
                  const scheduledTime = `${editDate}T${editTime}:00-05:00`;
                  await api.updateGame(gameId, { scheduled_time: scheduledTime });
                  setGame(await api.getGame(gameId));
                  setShowEdit(false);
                } catch (err) {
                  alert(err instanceof ApiError ? err.message : 'Failed');
                }
              }} className="btn-primary">Save</button>
              <button onClick={() => setShowEdit(false)} className="btn-secondary">Cancel</button>
            </div>
          </div>
        )}

        {showReschedule && (
          <div className="mt-4 glass-card p-4 space-y-3">
            <h3 className="text-sm font-semibold text-white">Propose New Time</h3>
            <div className="grid grid-cols-2 gap-4">
              <div><label className="text-xs text-gray-500">Date</label><input type="date" value={rescheduleDate} onChange={e => setRescheduleDate(e.target.value)} className="input-field" /></div>
              <div><label className="text-xs text-gray-500">Time (EST)</label><input type="time" value={rescheduleTime} onChange={e => setRescheduleTime(e.target.value)} className="input-field" /></div>
            </div>
            <div className="flex gap-2">
              <button onClick={async () => {
                if (!rescheduleDate || !rescheduleTime) { alert('Enter date and time'); return; }
                try {
                  const scheduledTime = `${rescheduleDate}T${rescheduleTime}:00-05:00`;
                  await api.proposeReschedule(gameId, scheduledTime);
                  setRescheduleProposals(await api.listRescheduleProposals(gameId));
                  setShowReschedule(false);
                  setRescheduleDate('');
                  setRescheduleTime('');
                  loadData();
                } catch (err) {
                  alert(err instanceof ApiError ? err.message : 'Failed');
                }
              }} className="btn-primary">Propose</button>
              <button onClick={() => setShowReschedule(false)} className="btn-secondary">Cancel</button>
            </div>
          </div>
        )}

        {pendingReschedule && canReschedule && (
          <div className="mt-4 glass-card p-4 bg-gold-500/5 border border-gold-500/20">
            <h3 className="text-sm font-semibold text-gold-400 mb-2">Reschedule Proposal</h3>
            <p className="text-sm text-gray-300 mb-2">New time: {formatEST(pendingReschedule.proposed_scheduled_time)}</p>
            <p className="text-xs text-gray-500 mb-3">Votes: {pendingReschedule.votes_for} / {pendingReschedule.total_participants} approved</p>
            <div className="flex gap-2">
              <button onClick={async () => {
                try {
                  await api.voteReschedule(gameId, pendingReschedule.id, true);
                  setRescheduleProposals(await api.listRescheduleProposals(gameId));
                  loadData();
                } catch (err) {
                  alert(err instanceof ApiError ? err.message : 'Failed');
                }
              }} className="btn-primary text-sm">Approve</button>
              <button onClick={async () => {
                try {
                  await api.voteReschedule(gameId, pendingReschedule.id, false);
                  setRescheduleProposals(await api.listRescheduleProposals(gameId));
                  loadData();
                } catch (err) {
                  alert(err instanceof ApiError ? err.message : 'Failed');
                }
              }} className="btn-danger text-sm">Reject</button>
            </div>
          </div>
        )}

        {showComplete && (
          <div className="mt-4 glass-card p-4 space-y-3">
            <h3 className="text-sm font-semibold text-white">Enter Final Score</h3>
            <div className="grid grid-cols-2 gap-4">
              <div><label className="text-xs text-gray-500">Team A</label><input type="number" min={0} value={scoreA} onChange={e => setScoreA(Number(e.target.value))} className="input-field" /></div>
              <div><label className="text-xs text-gray-500">Team B</label><input type="number" min={0} value={scoreB} onChange={e => setScoreB(Number(e.target.value))} className="input-field" /></div>
            </div>
            <div className="flex gap-2">
              <button onClick={() => handleAction(() => api.completeGame(gameId, scoreA, scoreB))} className="btn-primary">Submit Score</button>
              <button onClick={() => setShowComplete(false)} className="btn-secondary">Cancel</button>
            </div>
          </div>
        )}
      </div>

      <div className="grid md:grid-cols-2 gap-6 mb-6">
        <div className="animate-slide-up" style={{ animationDelay: '0.05s' }}>
          <h2 className="text-lg font-semibold text-white mb-3">
            {game.status === 'open' || game.status === 'full' ? 'Players' : 'Roster'}
          </h2>
          {unassigned.length > 0 && (
            <div className="glass-card p-4 mb-3">
              <div className="text-xs text-gray-500 mb-2 uppercase tracking-wider">{game.status === 'in_progress' || game.status === 'completed' ? 'Unassigned' : 'Joined Players'}</div>
              {unassigned.map(p => (
                <div key={p.id} className="flex items-center justify-between py-2 border-b border-gold-500/5 last:border-0">
                  <Link href={`/profile/${p.user_id}`} className="flex items-center gap-2 hover:text-gold-400 transition-colors">
                    <div className="w-7 h-7 rounded-full bg-gold-500/10 flex items-center justify-center text-xs font-bold text-gold-400">{p.display_name?.charAt(0)}</div>
                    <span className="text-sm text-white">{p.display_name}</span>
                  </Link>
                  <div className="flex items-center gap-2">
                    <span className={`text-xs ${skillColor(p.ai_skill_rating || 5)}`}>{p.ai_skill_rating?.toFixed(1)}</span>
                    {isCreator && p.user_id !== user.id && game.status !== 'in_progress' && game.status !== 'completed' && (
                      <button onClick={() => handleAction(() => api.kickPlayer(gameId, p.user_id))} className="text-xs text-red-400 hover:text-red-300 ml-1" title="Remove player">✕</button>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
          {teamA.length > 0 && (
            <div className="glass-card p-4 mb-3">
              <div className="text-xs text-gray-500 mb-2 uppercase tracking-wider">Team A {game.team_a_score !== null && `— ${game.team_a_score} pts`}</div>
              {teamA.map(p => (
                <div key={p.id} className="flex items-center justify-between py-2 border-b border-gold-500/5 last:border-0">
                  <Link href={`/profile/${p.user_id}`} className="flex items-center gap-2 hover:text-gold-400 transition-colors">
                    <div className="w-7 h-7 rounded-full bg-blue-500/10 flex items-center justify-center text-xs font-bold text-blue-400">{p.display_name?.charAt(0)}</div>
                    <span className="text-sm text-white">{p.display_name}</span>
                    {p.preferred_position && <span className="text-[10px] text-gray-500">{p.preferred_position}</span>}
                  </Link>
                  <span className={`text-xs ${skillColor(p.ai_skill_rating || 5)}`}>{p.ai_skill_rating?.toFixed(1)}</span>
                </div>
              ))}
            </div>
          )}
          {teamB.length > 0 && (
            <div className="glass-card p-4">
              <div className="text-xs text-gray-500 mb-2 uppercase tracking-wider">Team B {game.team_b_score !== null && `— ${game.team_b_score} pts`}</div>
              {teamB.map(p => (
                <div key={p.id} className="flex items-center justify-between py-2 border-b border-gold-500/5 last:border-0">
                  <Link href={`/profile/${p.user_id}`} className="flex items-center gap-2 hover:text-gold-400 transition-colors">
                    <div className="w-7 h-7 rounded-full bg-orange-500/10 flex items-center justify-center text-xs font-bold text-orange-400">{p.display_name?.charAt(0)}</div>
                    <span className="text-sm text-white">{p.display_name}</span>
                    {p.preferred_position && <span className="text-[10px] text-gray-500">{p.preferred_position}</span>}
                  </Link>
                  <span className={`text-xs ${skillColor(p.ai_skill_rating || 5)}`}>{p.ai_skill_rating?.toFixed(1)}</span>
                </div>
              ))}
            </div>
          )}

          {isCreator && game.status !== 'completed' && (
            <div className="glass-card p-4 mt-3">
              <div className="text-xs text-gray-500 mb-2 uppercase tracking-wider">Scorekeeper</div>
              {game.scorekeeper_name ? (
                <div className="text-sm text-white">{game.scorekeeper_name} <span className={`badge ml-2 ${game.scorekeeper_status === 'accepted' ? 'badge-green' : 'badge-gold'}`}>{game.scorekeeper_status}</span></div>
              ) : (
                <div>
                  <input type="text" placeholder="Search for scorekeeper..." value={skSearch}
                    onChange={e => searchSK(e.target.value)} className="input-field text-sm" />
                  {skResults.length > 0 && (
                    <div className="mt-2 space-y-1">
                      {skResults.slice(0, 5).map(u => (
                        <button key={u.id} onClick={async () => {
                          await handleAction(() => api.inviteScorekeeper(gameId, u.id));
                          setSkSearch(''); setSkResults([]);
                        }} className="w-full text-left text-sm text-gray-300 hover:text-white py-1.5 px-2 rounded hover:bg-gold-500/5 transition-colors">
                          {u.display_name} (@{u.username})
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>
          )}
          {isSK && game.scorekeeper_status === 'pending' && (
            <div className="glass-card p-4 mt-3 bg-gold-500/5 border-gold-500/20">
              <p className="text-sm text-gold-400 mb-2">You&apos;ve been invited to scorekeeper this game</p>
              <button onClick={() => handleAction(() => api.acceptScorekeeper(gameId))} className="btn-primary text-sm">Accept Invitation</button>
            </div>
          )}
        </div>

        <div className="animate-slide-up" style={{ animationDelay: '0.1s' }}>
          <h2 className="text-lg font-semibold text-white mb-3">Game Chat</h2>
          {isParticipant || isSK ? (
            <div className="glass-card flex flex-col" style={{ height: '400px' }}>
              <div className="flex-1 overflow-y-auto p-4 space-y-3">
                {messages.length === 0 ? (
                  <div className="text-center text-sm text-gray-600 py-8">No messages yet. Start the conversation!</div>
                ) : (
                  messages.map(m => (
                    <div key={m.id} className={`flex ${m.sender_id === user.id ? 'justify-end' : 'justify-start'}`}>
                      <div className={`max-w-[80%] rounded-2xl px-4 py-2 ${
                        m.sender_id === user.id ? 'bg-gold-500/15 text-white' : 'bg-dark-300 text-gray-200'
                      }`}>
                        {m.sender_id !== user.id && <div className="text-xs text-gold-400 mb-0.5">{m.sender_name}</div>}
                        <div className="text-sm">{m.content}</div>
                        <div className="text-[10px] text-gray-500 mt-0.5">{timeAgo(m.created_at)}</div>
                      </div>
                    </div>
                  ))
                )}
                <div ref={chatEnd} />
              </div>
              <div className="p-3 border-t border-gold-500/10 flex gap-2">
                <input value={msgInput} onChange={e => setMsgInput(e.target.value)}
                  onKeyDown={e => e.key === 'Enter' && sendMsg()}
                  placeholder="Type a message..." className="input-field text-sm py-2" />
                <button onClick={sendMsg} className="btn-primary px-4 py-2 text-sm">Send</button>
              </div>
            </div>
          ) : (
            <div className="glass-card p-8 text-center text-gray-500 text-sm">Join the game to access chat</div>
          )}
        </div>
      </div>

      {stats.length > 0 && (
        <div className="glass-card p-6 mb-6 animate-slide-up" style={{ animationDelay: '0.15s' }}>
          <h2 className="text-lg font-semibold text-white mb-4">Game Stats</h2>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead><tr className="text-xs text-gray-500 uppercase">
                <th className="text-left py-2 px-2">Player</th>
                {STAT_FIELDS.map(f => <th key={f} className="text-center py-2 px-1">{STAT_LABELS[f]}</th>)}
              </tr></thead>
              <tbody>{stats.map(s => {
                const p = game.participants.find(pp => pp.user_id === s.user_id);
                return (
                  <tr key={s.id} className="border-t border-gold-500/5">
                    <td className="py-2 px-2">
                      <Link href={`/profile/${s.user_id}`} className="text-white hover:text-gold-400 transition-colors">{p?.display_name || `Player ${s.user_id}`}</Link>
                    </td>
                    {STAT_FIELDS.map(f => <td key={f} className="text-center py-2 px-1 text-gray-300">{(s as unknown as Record<string, number>)[f]}</td>)}
                  </tr>
                );
              })}</tbody>
            </table>
          </div>
          {game.scorekeeper_name && <div className="mt-3 text-xs text-gray-500">Scorekept by {game.scorekeeper_name}</div>}
        </div>
      )}

      {showStats && (
        <div className="glass-card p-6 mb-6 animate-scale-in">
          <h2 className="text-lg font-semibold text-white mb-4">Enter Player Stats</h2>
          <div className="space-y-4 overflow-x-auto">
            {game.participants.map(p => (
              <div key={p.user_id} className="bg-dark-300/50 rounded-xl p-4">
                <div className="text-sm font-medium text-white mb-2">{p.display_name}</div>
                <div className="grid grid-cols-4 sm:grid-cols-6 gap-2">
                  {STAT_FIELDS.map(f => (
                    <div key={f}>
                      <label className="text-[10px] text-gray-500 uppercase">{STAT_LABELS[f]}</label>
                      <input type="number" min={0} value={statEntries[p.user_id]?.[f] ?? ''}
                        onChange={e => updateStat(p.user_id, f, Number(e.target.value))}
                        className="input-field text-sm py-1.5 px-2" />
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
          <div className="flex gap-2 mt-4">
            <button onClick={handleStats} className="btn-primary">Submit Stats</button>
            <button onClick={() => setShowStats(false)} className="btn-secondary">Cancel</button>
          </div>
        </div>
      )}

      {game.status === 'completed' && !game.stats_finalized && isParticipant && (
        <div className="glass-card p-6 mb-6 animate-slide-up" style={{ animationDelay: '0.2s' }}>
          <h2 className="text-lg font-semibold text-white mb-3">Stats Review Period</h2>
          <p className="text-sm text-gray-400 mb-4">Stats finalize 24 hours after game completion. Contest if something is wrong.</p>
          {contests.filter(c => c.status === 'open').map(c => (
            <div key={c.id} className="bg-dark-300/50 rounded-xl p-4 mb-3">
              <div className="text-sm text-white mb-1">{c.contester_name} contested: {c.reason}</div>
              <div className="text-xs text-gray-500 mb-2">Votes: {c.votes_for} for, {c.votes_against} against</div>
              <div className="flex gap-2">
                <button onClick={async () => { await api.voteContest(gameId, c.id, true); setContests(await api.listContests(gameId)); }} className="badge-green cursor-pointer hover:bg-emerald-500/25">Support</button>
                <button onClick={async () => { await api.voteContest(gameId, c.id, false); setContests(await api.listContests(gameId)); }} className="badge-red cursor-pointer hover:bg-red-500/25">Oppose</button>
              </div>
            </div>
          ))}
          {!contests.some(c => c.status === 'open') && (
            <div>
              <textarea value={contestReason} onChange={e => setContestReason(e.target.value)}
                placeholder="Explain why the stats should be reviewed..." className="input-field text-sm mb-2" rows={2} />
              <button onClick={async () => {
                if (contestReason.length < 5) { alert('Please provide more detail'); return; }
                try { await api.createContest(gameId, contestReason); setContests(await api.listContests(gameId)); setContestReason(''); }
                catch (err) { alert(err instanceof ApiError ? err.message : 'Failed'); }
              }} className="btn-danger text-sm">Contest Stats</button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
