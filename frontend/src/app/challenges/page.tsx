'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { useAuth } from '@/lib/auth-context';
import { api, ApiError } from '@/lib/api';
import { Challenge } from '@/lib/types';
import { formatESTShort, formatEST } from '@/lib/utils';

export default function ChallengesPage() {
  const { user, loading: authLoading, refresh } = useAuth();
  const router = useRouter();
  const [challenges, setChallenges] = useState<Challenge[]>([]);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState<string>('active');
  const [scoreModal, setScoreModal] = useState<number | null>(null);
  const [myScore, setMyScore] = useState(0);
  const [oppScore, setOppScore] = useState(0);

  const load = async () => {
    try {
      const c = await api.listChallenges();
      setChallenges(c);
    } catch { setChallenges([]); }
    setLoading(false);
  };

  useEffect(() => {
    if (!authLoading && !user) router.replace('/login');
  }, [user, authLoading, router]);

  useEffect(() => {
    if (!user) return;
    load();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user]);

  if (authLoading || !user) return null;

  const active = challenges.filter(c => ['pending', 'accepted', 'in_progress', 'awaiting_confirmation'].includes(c.status));
  const completed = challenges.filter(c => c.status === 'completed');
  const declined = challenges.filter(c => ['declined', 'expired'].includes(c.status));
  const shown = tab === 'active' ? active : tab === 'completed' ? completed : declined;

  const handleAction = async (action: () => Promise<Challenge>) => {
    try {
      await action();
      await load();
      refresh();
    } catch (err) {
      alert(err instanceof ApiError ? err.message : 'Failed');
    }
  };

  const submitScore = async (id: number) => {
    if (myScore < 0 || myScore > 15 || oppScore < 0 || oppScore > 15) {
      alert('Scores must be between 0 and 15');
      return;
    }
    if (myScore === oppScore) {
      alert('Games cannot end in a tie');
      return;
    }
    try {
      await api.submitChallengeScore(id, myScore, oppScore);
      await load();
      refresh();
      setScoreModal(null);
    } catch (err) {
      alert(err instanceof ApiError ? err.message : 'Failed');
    }
  };

  const getStatusBadge = (c: Challenge) => {
    const now = new Date();
    const scheduled = c.scheduled_time ? new Date(c.scheduled_time) : null;

    switch (c.status) {
      case 'pending': return <span className="badge badge-gold">Pending</span>;
      case 'accepted': {
        if (scheduled && scheduled > now) {
          return <span className="badge badge-blue">Scheduled</span>;
        }
        return <span className="badge badge-blue">Ready to Play</span>;
      }
      case 'awaiting_confirmation': return <span className="badge bg-amber-500/15 text-amber-400 border border-amber-500/20">Awaiting Confirmation</span>;
      case 'completed': return <span className={`badge ${c.winner_id === user.id ? 'badge-green' : 'badge-red'}`}>{c.winner_id === user.id ? 'Won' : 'Lost'}</span>;
      case 'declined': return <span className="badge badge-red">Declined</span>;
      default: return <span className="badge text-gray-500">{c.status}</span>;
    }
  };

  return (
    <div className="page-container max-w-3xl mx-auto">
      <div className="flex items-center justify-between mb-6 animate-slide-up">
        <div>
          <h1 className="text-2xl font-bold text-white">1v1 Challenges</h1>
          <p className="text-sm text-gray-500 mt-1">Your 1v1 record: {user.challenge_wins} wins – {user.challenge_losses} losses</p>
        </div>
      </div>

      <div className="flex gap-2 mb-6">
        {[
          { key: 'active', label: `Active (${active.length})` },
          { key: 'completed', label: `Completed (${completed.length})` },
          { key: 'declined', label: `Other (${declined.length})` },
        ].map(t => (
          <button key={t.key} onClick={() => setTab(t.key)}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition-all ${
              tab === t.key ? 'bg-gold-500/20 text-gold-400 border border-gold-500/30' : 'text-gray-400 hover:text-white hover:bg-white/5'
            }`}>{t.label}</button>
        ))}
      </div>

      {loading ? (
        <div className="glass-card p-12 text-center text-gray-500">Loading...</div>
      ) : shown.length === 0 ? (
        <div className="glass-card p-12 text-center animate-fade-in">
          <p className="text-gray-500 mb-3">No {tab} challenges</p>
          <p className="text-sm text-gray-600">Visit a player&apos;s profile to issue a 1v1 challenge</p>
          <Link href="/search" className="btn-secondary text-sm mt-4 inline-block">Find Players (Search)</Link>
        </div>
      ) : (
        <div className="space-y-3">
          {shown.map(c => {
            const isChallenger = c.challenger_id === user.id;
            const opponentName = isChallenger ? c.challenged_name : c.challenger_name;
            const opponentId = isChallenger ? c.challenged_id : c.challenger_id;
            const needsMyConfirm = c.status === 'awaiting_confirmation' && (
              (isChallenger && !c.challenger_confirmed) || (!isChallenger && !c.challenged_confirmed)
            );

            return (
              <div key={c.id} className="glass-card p-4 animate-slide-up">
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-3">
                    <Link href={`/profile/${opponentId}`} className="flex items-center gap-2 hover:text-gold-400 transition-colors">
                      <div className="w-8 h-8 rounded-full bg-gold-500/10 flex items-center justify-center text-gold-400 text-xs font-bold">
                        {opponentName?.charAt(0)}
                      </div>
                      <span className="text-white font-medium">{opponentName}</span>
                    </Link>
                    {isChallenger ? (
                      <span className="text-[10px] text-gray-600">You challenged</span>
                    ) : (
                      <span className="text-[10px] text-gray-600">Challenged you</span>
                    )}
                  </div>
                  {getStatusBadge(c)}
                </div>

                {c.challenger_win_probability != null && c.status !== 'completed' && (
                  <div className="flex items-center gap-2 mb-2 py-2 px-3 rounded-lg bg-gold-500/5 border border-gold-500/15">
                    <span className="text-[10px] text-gray-500 uppercase tracking-wider">Win predictor</span>
                    <span className={isChallenger ? (c.challenger_win_probability >= 0.5 ? 'text-gold-400 font-semibold' : 'text-gray-400') : (c.challenger_win_probability < 0.5 ? 'text-gold-400 font-semibold' : 'text-gray-400')}>
                      {isChallenger ? 'You' : opponentName} {(isChallenger ? c.challenger_win_probability : 1 - c.challenger_win_probability) * 100}%
                    </span>
                    <span className="text-gray-600">—</span>
                    <span className={!isChallenger ? (c.challenger_win_probability >= 0.5 ? 'text-gold-400 font-semibold' : 'text-gray-400') : (c.challenger_win_probability < 0.5 ? 'text-gold-400 font-semibold' : 'text-gray-400')}>
                      {!isChallenger ? 'You' : opponentName} {(isChallenger ? 1 - c.challenger_win_probability : c.challenger_win_probability) * 100}%
                    </span>
                  </div>
                )}

                {c.message && (
                  <div className="text-sm text-gray-300 bg-dark-300/30 rounded-lg px-3 py-2 mb-2 border-l-2 border-gold-500/30">
                    &quot;{c.message}&quot;
                  </div>
                )}

                {c.scheduled_time && (
                  <div className="flex items-center gap-1.5 text-sm text-blue-400 mb-2">
                    <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
                    <span>Scheduled: {formatEST(c.scheduled_time)}</span>
                  </div>
                )}

                {c.challenger_score !== null && (
                  <div className="text-sm text-gray-400 mb-2">
                    Score: {c.challenger_score} - {c.challenged_score}
                    <span className="text-xs text-gray-600 ml-2">(games to 15)</span>
                  </div>
                )}

                <div className="text-xs text-gray-600 mb-3">Created {formatESTShort(c.created_at)}</div>

                <div className="flex gap-2 flex-wrap">
                  {c.status === 'pending' && !isChallenger && (
                    <>
                      <button onClick={() => handleAction(() => api.acceptChallenge(c.id))} className="btn-primary text-sm px-3 py-1.5">Accept</button>
                      <button onClick={() => handleAction(() => api.declineChallenge(c.id))} className="btn-danger text-sm px-3 py-1.5">Decline</button>
                    </>
                  )}
                  {c.status === 'pending' && isChallenger && (
                    <span className="text-xs text-gray-500 italic">Waiting for response...</span>
                  )}
                  {(c.status === 'accepted' || c.status === 'in_progress') && (
                    <button onClick={() => { setScoreModal(c.id); setMyScore(0); setOppScore(0); }} className="btn-primary text-sm px-3 py-1.5">Submit Score</button>
                  )}
                  {needsMyConfirm && (
                    <button onClick={() => handleAction(() => api.confirmChallenge(c.id))} className="btn-primary text-sm px-3 py-1.5">Confirm Score</button>
                  )}
                  <Link href={`/messages?dm=${opponentId}`} className="btn-secondary text-sm px-3 py-1.5 inline-flex items-center gap-1">
                    <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" /></svg>
                    Message
                  </Link>
                </div>

                {scoreModal === c.id && (
                  <div className="mt-3 bg-dark-300/50 rounded-xl p-4 animate-scale-in">
                    <p className="text-xs text-gray-400 mb-3">Games are to 15 points. Both players must confirm the score.</p>
                    <div className="grid grid-cols-2 gap-4 mb-3">
                      <div>
                        <label className="text-xs text-gray-500">Your Score (0-15)</label>
                        <input type="number" min={0} max={15} value={myScore} onChange={e => setMyScore(Math.min(15, Math.max(0, Number(e.target.value))))} className="input-field" />
                      </div>
                      <div>
                        <label className="text-xs text-gray-500">Opponent Score (0-15)</label>
                        <input type="number" min={0} max={15} value={oppScore} onChange={e => setOppScore(Math.min(15, Math.max(0, Number(e.target.value))))} className="input-field" />
                      </div>
                    </div>
                    <div className="flex gap-2">
                      <button onClick={() => submitScore(c.id)} className="btn-primary text-sm">Submit</button>
                      <button onClick={() => setScoreModal(null)} className="btn-secondary text-sm">Cancel</button>
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
