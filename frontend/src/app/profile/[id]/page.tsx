'use client';

import { useEffect, useState } from 'react';
import { useParams, useRouter, useSearchParams } from 'next/navigation';
import Link from 'next/link';
import { useAuth } from '@/lib/auth-context';
import { api, ApiError } from '@/lib/api';
import { User, CareerStats, CareerStatsByType, SkillHistoryEntry } from '@/lib/types';
import { skillColor, positionLabel } from '@/lib/utils';
import { SkillRatingChart } from '@/components/SkillRatingChart';

export default function PublicProfilePage() {
  const params = useParams();
  const searchParams = useSearchParams();
  const { user: currentUser } = useAuth();
  const router = useRouter();
  const userId = Number(params.id);
  const [profile, setProfile] = useState<User | null>(null);
  const [stats, setStats] = useState<CareerStats | null>(null);
  const [statsByType, setStatsByType] = useState<CareerStatsByType | null>(null);
  const [skillHistory, setSkillHistory] = useState<SkillHistoryEntry[]>([]);
  const [challengeHistory, setChallengeHistory] = useState<import('@/lib/types').ChallengeHistoryEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [showChallenge, setShowChallenge] = useState(false);
  const [challengeDate, setChallengeDate] = useState('');
  const [challengeTime, setChallengeTime] = useState('');
  const [challengeMsg, setChallengeMsg] = useState('');
  const [sending, setSending] = useState(false);

  useEffect(() => {
    if (searchParams.get('challenge') === '1' && currentUser && userId !== currentUser.id) {
      setShowChallenge(true);
    }
  }, [searchParams, currentUser, userId]);

  useEffect(() => {
    if (currentUser && userId === currentUser.id) { router.replace('/profile'); return; }
    Promise.all([
      api.getUser(userId),
      api.getCareerStats(userId),
      api.getCareerStatsByGameType(userId),
      api.getSkillHistory(userId),
      api.getUserChallengesHistory(userId, 15),
    ]).then(([u, s, sbt, sh, ch]) => {
      setProfile(u);
      setStats(s);
      setStatsByType(sbt);
      setSkillHistory(sh);
      setChallengeHistory(ch);
    }).catch(err => {
      setError(err instanceof ApiError ? err.message : 'User not found');
    }).finally(() => setLoading(false));
  }, [userId, currentUser, router]);

  const sendChallenge = async () => {
    if (!profile) return;
    if (!challengeDate || !challengeTime) {
      alert('Please pick a date and time for the challenge. Both players need to know when to meet.');
      return;
    }
    setSending(true);
    try {
      const scheduledTime = `${challengeDate}T${challengeTime}:00-05:00`;
      await api.createChallenge(profile.id, scheduledTime, challengeMsg || undefined);
      alert('Challenge sent!');
      setShowChallenge(false);
      setChallengeDate('');
      setChallengeTime('');
      setChallengeMsg('');
    } catch (err) {
      alert(err instanceof ApiError ? err.message : 'Failed to send challenge');
    }
    setSending(false);
  };

  if (loading) return <div className="page-container"><div className="glass-card p-12 text-center text-gray-500">Loading profile...</div></div>;
  if (error || !profile) return <div className="page-container"><div className="glass-card p-12 text-center text-red-400">{error}</div></div>;

  const teamGames = profile.games_played;
  const teamWins = profile.wins;
  const teamLosses = profile.losses;
  const teamRecord = `${teamWins}W-${teamLosses}L`;
  const teamWinRate = teamGames > 0 ? ((teamWins / teamGames) * 100).toFixed(0) : '—';

  const h2hWins = profile.challenge_wins;
  const h2hLosses = profile.challenge_losses;
  const h2hRecord = `${h2hWins}W-${h2hLosses}L`;
  const h2hTotal = h2hWins + h2hLosses;
  const h2hWinRate = h2hTotal > 0 ? ((h2hWins / h2hTotal) * 100).toFixed(0) : '—';

  const overallWins = teamWins + h2hWins;
  const overallLosses = teamLosses + h2hLosses;
  const overallRecord = `${overallWins}W-${overallLosses}L`;
  const totalGames = teamGames + h2hTotal;
  const overallWinRate = totalGames > 0 ? (((overallWins / totalGames) * 100).toFixed(0)) : '—';

  return (
    <div className="page-container max-w-4xl mx-auto">
      <div className="glass-card p-6 md:p-8 mb-6 animate-slide-up">
        <div className="flex flex-col md:flex-row items-start gap-6">
          <div className="w-20 h-20 rounded-2xl bg-gradient-to-br from-gold-500/30 to-gold-700/30 flex items-center justify-center text-gold-400 text-3xl font-black shrink-0">
            {profile.display_name.charAt(0)}
          </div>
          <div className="flex-1">
            <h1 className="text-2xl font-bold text-white">{profile.display_name}</h1>
            <div className="text-sm text-gray-500 mb-2">@{profile.username}</div>
            <div className="flex flex-wrap gap-3 text-sm text-gray-400 mb-3">
              <span>{positionLabel(profile.preferred_position)}</span>
              {profile.height && <span>{profile.height}</span>}
              {profile.weight && <span>{profile.weight} lbs</span>}
            </div>
            {profile.bio && <p className="text-sm text-gray-400 mb-3">{profile.bio}</p>}
            <div className="flex flex-wrap gap-2">
              {currentUser && (
                <>
                  <Link href={`/messages?user=${profile.id}`} className="btn-primary text-sm px-4 py-1.5">Message</Link>
                  <button onClick={() => setShowChallenge(!showChallenge)} className="btn-secondary text-sm px-4 py-1.5">Challenge 1v1</button>
                  <button onClick={async () => {
                    const reason = prompt('Report reason (harassment, cheating, etc.):');
                    if (!reason) return;
                    try { await api.reportUser(profile.id, reason); alert('Report submitted'); } catch (err) { alert(err instanceof ApiError ? err.message : 'Failed'); }
                  }} className="text-xs text-gray-600 hover:text-red-400 transition-colors ml-2 mt-1">Report</button>
                  <button onClick={async () => {
                    if (!confirm('Block this user? You won\'t see each other in search or games.')) return;
                    try { await api.blockUser(profile.id); alert('User blocked'); router.back(); } catch (err) { alert(err instanceof ApiError ? err.message : 'Failed'); }
                  }} className="text-xs text-gray-600 hover:text-red-400 transition-colors mt-1">Block</button>
                </>
              )}
            </div>
          </div>
          <div className="text-center px-6 py-3 rounded-xl bg-gold-500/10 border border-gold-500/20">
            <div className={`text-3xl font-black ${skillColor(profile.ai_skill_rating)}`}>{profile.ai_skill_rating.toFixed(1)}</div>
            <div className="text-[10px] text-gray-500 uppercase tracking-wider mt-1">Skill (1–10)</div>
          </div>
        </div>

        {profile.nba_match && (
          <div className="mt-5 py-3 px-4 rounded-xl bg-gold-500/5 border border-gold-500/20 flex flex-col md:flex-row items-center justify-between gap-4 animate-fade-in">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-full bg-dark-500 flex items-center justify-center text-xl shadow-inner border border-gold-500/10">🏀</div>
              <div>
                <div className="text-[10px] text-gray-500 uppercase tracking-widest font-bold">AI Playstyle Match</div>
                <div className="text-sm text-gold-400 font-semibold">Plays like <span className="text-white">{profile.nba_match.name}</span></div>
              </div>
            </div>
            <div className="text-right">
              <div className="text-sm font-bold text-white">{profile.nba_match.similarity.toFixed(1)}% Match</div>
              <div className="text-[10px] text-gray-500 md:text-right text-left">Based on NBA Euclidean Distance</div>
            </div>
          </div>
        )}

        {showChallenge && currentUser && (
          <div className="mt-5 bg-dark-300/50 rounded-xl p-5 animate-scale-in border border-gold-500/10">
            <h3 className="text-sm font-semibold text-white mb-3">Schedule 1v1 Challenge</h3>
            <div className="mb-3 py-2 px-3 rounded-lg bg-gold-500/5 border border-gold-500/15 inline-flex items-center gap-2">
              <span className="text-[10px] text-gray-500 uppercase tracking-wider">Win predictor</span>
              <span className="text-sm text-white">
                You {Math.round((1 / (1 + Math.pow(10, (profile.ai_skill_rating - currentUser.ai_skill_rating) / 4))) * 100)}% — {profile.display_name} {Math.round((1 / (1 + Math.pow(10, (currentUser.ai_skill_rating - profile.ai_skill_rating) / 4))) * 100)}%
              </span>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mb-3">
              <div>
                <label className="text-xs text-gray-500 mb-1 block">Date <span className="text-red-400">*</span></label>
                <input type="date" value={challengeDate} onChange={e => setChallengeDate(e.target.value)} className="input-field" required />
              </div>
              <div>
                <label className="text-xs text-gray-500 mb-1 block">Time EST <span className="text-red-400">*</span></label>
                <input type="time" value={challengeTime} onChange={e => setChallengeTime(e.target.value)} className="input-field" required />
              </div>
            </div>
            <div className="mb-3">
              <label className="text-xs text-gray-500 mb-1 block">Message (optional)</label>
              <input type="text" value={challengeMsg} onChange={e => setChallengeMsg(e.target.value)}
                placeholder="e.g., Let's run it at the CoRec!" maxLength={500} className="input-field" />
            </div>
            <div className="flex gap-2">
              <button onClick={sendChallenge} disabled={sending} className="btn-primary text-sm px-4 py-1.5">{sending ? 'Sending...' : 'Send Challenge'}</button>
              <button onClick={() => setShowChallenge(false)} className="btn-secondary text-sm px-4 py-1.5">Cancel</button>
            </div>
          </div>
        )}
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        {[
          { label: 'Team Games', value: teamRecord, sub: teamGames > 0 ? `${teamWinRate}% win rate` : 'No games yet' },
          { label: '1v1 Head-to-Head', value: h2hRecord, sub: h2hTotal > 0 ? `${h2hWinRate}% win rate` : 'No challenges yet' },
          { label: 'Overall', value: overallRecord, sub: totalGames > 0 ? `${overallWinRate}% win rate` : '—' },
          { label: 'Rating Confidence', value: `${(profile.skill_confidence * 100).toFixed(0)}%`, sub: stats && stats.games_played > 0 ? `${stats.ppg.toFixed(1)} PPG avg` : 'Skill certainty' },
        ].map(s => (
          <div key={s.label} className="glass-card p-4 text-center">
            <div className="text-xl font-bold text-white">{s.value}</div>
            <div className="text-xs text-gray-500 mt-1">{s.label}</div>
            {s.sub && <div className="text-[10px] text-gray-600 mt-0.5">{s.sub}</div>}
          </div>
        ))}
      </div>

      {statsByType && (statsByType.five_v_five.games_played > 0 || statsByType.three_v_three.games_played > 0 || statsByType.two_v_two.games_played > 0) ? (
        <div className="glass-card p-6 mb-6">
          <h2 className="text-lg font-semibold text-white mb-4">Career Averages by Game Type</h2>
          <div className="grid md:grid-cols-3 gap-6">
            {[
              { key: '5v5', label: '5v5', s: statsByType.five_v_five },
              { key: '3v3', label: '3v3', s: statsByType.three_v_three },
              { key: '2v2', label: '2v2', s: statsByType.two_v_two },
            ].map(({ key, label, s }) => (
              <div key={key} className="rounded-xl bg-dark-300/30 border border-gold-500/10 p-4">
                <div className="text-sm font-medium text-gold-400 mb-3">{label}</div>
                {s.games_played > 0 ? (
                  <>
                    <div className="grid grid-cols-3 gap-2">
                      {[
                        { label: 'PPG', value: s.ppg.toFixed(1) }, { label: 'RPG', value: s.rpg.toFixed(1) },
                        { label: 'APG', value: s.apg.toFixed(1) }, { label: 'SPG', value: s.spg.toFixed(1) },
                        { label: 'BPG', value: s.bpg.toFixed(1) }, { label: 'TOPG', value: s.topg.toFixed(1) },
                        { label: 'FG%', value: `${(s.fg_pct * 100).toFixed(1)}` },
                        { label: '3P%', value: `${(s.three_pct * 100).toFixed(1)}` },
                        { label: 'FT%', value: `${(s.ft_pct * 100).toFixed(1)}` },
                      ].map(x => (
                        <div key={x.label} className="text-center">
                          <div className="text-sm font-bold text-white">{x.value}</div>
                          <div className="text-[9px] text-gray-500 uppercase">{x.label}</div>
                        </div>
                      ))}
                    </div>
                    <div className="text-[10px] text-gray-600 mt-2">{s.games_played} games</div>
                  </>
                ) : (
                  <div className="text-xs text-gray-500">No {label} games yet</div>
                )}
              </div>
            ))}
          </div>

          {skillHistory.length > 0 && (
            <div className="mt-6 pt-6 border-t border-gold-500/10">
              <h3 className="text-sm font-semibold text-white mb-3">Skill Rating Progression</h3>
              <SkillRatingChart data={skillHistory} />
            </div>
          )}
        </div>
      ) : skillHistory.length > 0 ? (
        <div className="glass-card p-6 mb-6">
          <h2 className="text-lg font-semibold text-white mb-4">Skill Rating Progression</h2>
          <SkillRatingChart data={skillHistory} />
        </div>
      ) : (
        <div className="glass-card p-8 text-center text-gray-500 mb-6">
          No team stats recorded yet for this player.
        </div>
      )}

      {challengeHistory.length > 0 && (
        <div className="glass-card p-6 mt-6">
          <h2 className="text-lg font-semibold text-white mb-4">1v1 Challenge History</h2>
          <div className="space-y-2 max-h-64 overflow-y-auto">
            {challengeHistory.map(ch => {
              const isChallenger = ch.challenger_id === userId;
              const oppName = isChallenger ? ch.challenged_name : ch.challenger_name;
              const myScore = isChallenger ? (ch.challenger_score ?? 0) : (ch.challenged_score ?? 0);
              const oppScore = isChallenger ? (ch.challenged_score ?? 0) : (ch.challenger_score ?? 0);
              const won = ch.winner_id === userId;
              return (
                <div key={ch.id} className="flex items-center justify-between py-2 px-3 rounded-lg bg-dark-300/30 border border-gold-500/5">
                  <span className="text-sm text-gray-300">
                    vs {oppName || 'Unknown'} — {myScore}-{oppScore}
                  </span>
                  <span className={`text-xs font-medium ${won ? 'text-emerald-400' : 'text-red-400/80'}`}>
                    {won ? 'W' : 'L'}
                  </span>
                  {ch.completed_at && (
                    <span className="text-[10px] text-gray-600">{new Date(ch.completed_at).toLocaleDateString()}</span>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
