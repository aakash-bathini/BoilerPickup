'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { useAuth } from '@/lib/auth-context';
import { api } from '@/lib/api';
import { UserSearchResult } from '@/lib/types';
import { skillColor, skillBg, positionLabel } from '@/lib/utils';

const POSITIONS = ['PG', 'SG', 'SF', 'PF', 'C'] as const;

export default function LeaderboardPage() {
  const { user } = useAuth();
  const [overall, setOverall] = useState<UserSearchResult[]>([]);
  const [byPosition, setByPosition] = useState<Record<string, UserSearchResult[]>>({});
  const [hotWeek, setHotWeek] = useState<UserSearchResult[]>([]);
  const [h2hTotal, setH2hTotal] = useState<UserSearchResult[]>([]);
  const [h2hWeek, setH2hWeek] = useState<UserSearchResult[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeSection, setActiveSection] = useState<'skill' | '1v1'>('skill');
  const [activeTab, setActiveTab] = useState<'overall' | string>('overall');

  useEffect(() => {
    const load = async () => {
      setLoading(true);
      try {
        const [all, pg, sg, sf, pf, c, hot, h2hTot, h2hWk] = await Promise.all([
          api.getLeaderboard(50),
          api.getLeaderboard(20, 'PG'),
          api.getLeaderboard(20, 'SG'),
          api.getLeaderboard(20, 'SF'),
          api.getLeaderboard(20, 'PF'),
          api.getLeaderboard(20, 'C'),
          api.getLeaderboard(20, undefined, 'hot_week'),
          api.getLeaderboard1v1(50, 'wins_total'),
          api.getLeaderboard1v1(50, 'wins_week'),
        ]);
        setOverall(all);
        setByPosition({ PG: pg, SG: sg, SF: sf, PF: pf, C: c });
        setHotWeek(hot);
        setH2hTotal(h2hTot);
        setH2hWeek(h2hWk);
      } catch {
        setOverall([]);
        setByPosition({});
        setHotWeek([]);
        setH2hTotal([]);
        setH2hWeek([]);
      } finally {
        setLoading(false);
      }
    };
    load();
  }, []);

  const totalGames = (p: UserSearchResult) => (p.games_played || 0) + (p.challenge_wins || 0) + (p.challenge_losses || 0);
  const playersWithGames = overall.filter(p => totalGames(p) >= 1);

  const skillList = activeTab === 'overall' ? playersWithGames
    : activeTab === 'hot_week' ? hotWeek
      : (byPosition[activeTab] || []);

  const h2hList = activeTab === 'h2h_week' ? h2hWeek : h2hTotal;
  const is1v1Section = activeSection === '1v1';
  const currentList = is1v1Section ? h2hList : skillList;

  return (
    <div className="min-h-screen relative overflow-hidden">
      {/* Background */}
      <div className="fixed inset-0 -z-10">
        <div className="absolute inset-0 bg-gradient-to-b from-black via-[#0a0a0a] to-black" />
        <div className="absolute inset-0 opacity-20" style={{
          backgroundImage: `radial-gradient(circle at 20% 30%, rgba(207, 185, 145, 0.15) 0%, transparent 50%),
            radial-gradient(circle at 80% 70%, rgba(207, 185, 145, 0.08) 0%, transparent 50%)`,
        }} />
        <div className="absolute inset-0 opacity-30" style={{
          backgroundImage: `radial-gradient(ellipse 80% 50% at 50% 0%, rgba(207, 185, 145, 0.06) 0%, transparent 70%)`,
        }} />
        <div className="absolute bottom-0 left-0 right-0 h-1 bg-gradient-to-r from-transparent via-gold-500/20 to-transparent" />
      </div>

      <div className="page-container max-w-6xl mx-auto relative">
        {/* Hero */}
        <div className="mb-10 animate-slide-up">
          <div className="flex items-center gap-3 mb-2">
            <span className="text-4xl">🏀</span>
            <h1 className="text-3xl md:text-4xl font-black text-white tracking-tight">
              Purdue CoRec Rankings
            </h1>
          </div>
          <p className="text-gray-400 mt-1 max-w-xl">
            Skill ratings (team + 1v1) and head-to-head 1v1 rankings. Best overall, by position, hottest this week, or most 1v1 wins.
          </p>
        </div>

        {loading ? (
          <div className="space-y-6">
            <div className="glass-card p-8 animate-pulse">
              <div className="h-48 bg-dark-50/30 rounded-xl mb-6" />
              <div className="space-y-3">
                {[1, 2, 3, 4, 5].map(i => (
                  <div key={i} className="h-14 bg-dark-50/20 rounded-xl" />
                ))}
              </div>
            </div>
          </div>
        ) : playersWithGames.length === 0 && hotWeek.length === 0 && h2hTotal.length === 0 ? (
          <div className="glass-card p-16 text-center animate-fade-in">
            <div className="w-20 h-20 mx-auto mb-6 rounded-2xl bg-gold-500/10 flex items-center justify-center text-4xl">🏀</div>
            <h3 className="text-xl font-bold text-white mb-2">No players yet</h3>
            <p className="text-gray-400 mb-6">
              {user ? 'No one has played yet. Create a game or browse to get the community started!' : 'Be the first to register and climb the ranks!'}
            </p>
            {user ? (
              <div className="flex gap-3 justify-center">
                <Link href="/games" className="btn-secondary inline-block">Browse Games</Link>
                <Link href="/games/create" className="btn-primary inline-block">Create Game</Link>
              </div>
            ) : (
              <Link href="/register" className="btn-primary inline-block">Get Started</Link>
            )}
          </div>
        ) : (
          <>
            {/* Section: Skill vs 1v1 */}
            <div className="flex gap-3 mb-6 animate-slide-up">
              <button
                onClick={() => { setActiveSection('skill'); setActiveTab('overall'); }}
                className={`px-6 py-3 rounded-xl font-bold text-sm transition-all ${activeSection === 'skill'
                  ? 'bg-gold-500/25 text-gold-400 border-2 border-gold-500/50'
                  : 'bg-dark-300/50 text-gray-400 border border-transparent hover:border-gold-500/20 hover:text-gray-300'
                  }`}
              >
                🏆 Skill Rankings
              </button>
              <button
                onClick={() => { setActiveSection('1v1'); setActiveTab('h2h_total'); }}
                className={`px-6 py-3 rounded-xl font-bold text-sm transition-all ${activeSection === '1v1'
                  ? 'bg-orange-500/25 text-orange-400 border-2 border-orange-500/50'
                  : 'bg-dark-300/50 text-gray-400 border border-transparent hover:border-orange-500/20 hover:text-gray-300'
                  }`}
              >
                ⚡ 1v1 Head-to-Head
              </button>
            </div>

            {/* Tabs */}
            <div className="flex flex-wrap gap-2 mb-8 animate-slide-up">
              {activeSection === 'skill' ? (
                <>
                  <button onClick={() => setActiveTab('overall')}
                    className={`px-5 py-2.5 rounded-xl font-semibold text-sm transition-all ${activeTab === 'overall' ? 'bg-gold-500/20 text-gold-400 border border-gold-500/40' : 'bg-dark-300/50 text-gray-400 border border-transparent hover:border-gold-500/20 hover:text-gray-300'
                      }`}>Best Overall</button>
                  <button onClick={() => setActiveTab('hot_week')}
                    className={`px-5 py-2.5 rounded-xl font-semibold text-sm transition-all ${activeTab === 'hot_week' ? 'bg-gold-500/20 text-gold-400 border border-gold-500/40' : 'bg-dark-300/50 text-gray-400 border border-transparent hover:border-gold-500/20 hover:text-gray-300'
                      }`}>🔥 Players on Fire</button>
                  {POSITIONS.map(pos => (
                    <button key={pos} onClick={() => setActiveTab(pos)}
                      className={`px-5 py-2.5 rounded-xl font-semibold text-sm transition-all ${activeTab === pos ? 'bg-gold-500/20 text-gold-400 border border-gold-500/40' : 'bg-dark-300/50 text-gray-400 border border-transparent hover:border-gold-500/20 hover:text-gray-300'
                        }`}>{positionLabel(pos)}</button>
                  ))}
                </>
              ) : (
                <>
                  <button onClick={() => setActiveTab('h2h_total')}
                    className={`px-5 py-2.5 rounded-xl font-semibold text-sm transition-all ${activeTab === 'h2h_total' ? 'bg-orange-500/20 text-orange-400 border border-orange-500/40' : 'bg-dark-300/50 text-gray-400 border border-transparent hover:border-orange-500/20 hover:text-gray-300'
                      }`}>Most 1v1 Wins (All Time)</button>
                  <button onClick={() => setActiveTab('h2h_week')}
                    className={`px-5 py-2.5 rounded-xl font-semibold text-sm transition-all ${activeTab === 'h2h_week' ? 'bg-orange-500/20 text-orange-400 border border-orange-500/40' : 'bg-dark-300/50 text-gray-400 border border-transparent hover:border-orange-500/20 hover:text-gray-300'
                      }`}>🔥 1v1 Wins (Last 7 Days)</button>
                </>
              )}
            </div>

            {/* Rankings Table */}
            <div className="glass-card overflow-hidden animate-slide-up">
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead>
                    <tr className={`text-xs text-gray-500 uppercase tracking-wider border-b ${is1v1Section ? 'border-orange-500/10' : 'border-gold-500/10'} bg-dark-300/30`}>
                      <th className="text-left py-4 px-4">#</th>
                      <th className="text-left py-4 px-4 w-[250px]">Player</th>
                      <th className="text-center py-4 px-4">Rating</th>
                      <th className="text-left py-4 px-4 hidden md:table-cell">NBA Playstyle Match</th>
                      {is1v1Section ? (
                        <>
                          <th className="text-center py-4 px-4">1v1 Record</th>
                          <th className="text-center py-4 px-4 hidden sm:table-cell">Win Rate</th>
                        </>
                      ) : (
                        <>
                          <th className="text-center py-4 px-4 hidden sm:table-cell">PPG / RPG / APG</th>
                          <th className="text-center py-4 px-4">Total Record</th>
                          {activeTab === 'hot_week' && <th className="text-center py-4 px-4">+7d</th>}
                        </>
                      )}
                    </tr>
                  </thead>
                  <tbody>
                    {currentList.map((p, i) => (
                      <tr key={p.id} className="border-b border-gold-500/5 hover:bg-gold-500/5 transition-colors group">
                        <td className="py-4 px-4">
                          <span className={`text-sm font-bold ${i < 3 ? 'text-gold-400' : 'text-gray-500'}`}>
                            {i === 0 ? '🥇' : i === 1 ? '🥈' : i === 2 ? '🥉' : i + 1}
                          </span>
                        </td>
                        <td className="py-4 px-4">
                          <Link href={`/profile/${p.id}`} className="flex items-center gap-3 hover:text-gold-400 transition-colors">
                            <div className={`w-10 h-10 rounded-xl flex items-center justify-center text-gold-400 font-bold text-sm border ${skillBg(p.ai_skill_rating)}`}>
                              {p.display_name.charAt(0)}
                            </div>
                            <div>
                              <div className="text-sm font-semibold text-white">{p.display_name}</div>
                              <div className="text-xs text-gray-600">@{p.username}</div>
                            </div>
                          </Link>
                        </td>
                        <td className="py-4 px-4 text-center">
                          <span className={`inline-flex items-center justify-center min-w-[3rem] px-3 py-1.5 rounded-lg font-bold text-sm ${skillBg(p.ai_skill_rating)} ${skillColor(p.ai_skill_rating)}`}>
                            {p.ai_skill_rating.toFixed(1)}
                          </span>
                        </td>
                        <td className="py-4 px-4 text-left hidden md:table-cell">
                          {p.nba_match ? (
                            <div className="flex items-center gap-2">
                              <span className="text-lg">🏀</span>
                              <div>
                                <div className="text-[11px] font-semibold text-white truncate max-w-[120px]">{p.nba_match.name}</div>
                                <div className="text-[10px] text-gold-400">{p.nba_match.similarity.toFixed(1)}% Match</div>
                              </div>
                            </div>
                          ) : (
                            <span className="text-xs text-gray-500">—</span>
                          )}
                        </td>
                        {is1v1Section ? (
                          <>
                            <td className="py-4 px-4 text-center">
                              <span className="text-base font-bold text-orange-400">
                                {(() => {
                                  const w = activeTab === 'h2h_week' ? (p.challenge_wins_week || 0) : (p.challenge_wins || 0);
                                  const l = activeTab === 'h2h_week' ? (p.challenge_losses_week || 0) : (p.challenge_losses || 0);
                                  return `${w}W-${l}L`;
                                })()}
                              </span>
                            </td>
                            <td className="py-4 px-4 text-center hidden sm:table-cell">
                              <span className="text-sm text-gray-400">
                                {(() => {
                                  const w = activeTab === 'h2h_week' ? (p.challenge_wins_week || 0) : (p.challenge_wins || 0);
                                  const l = activeTab === 'h2h_week' ? (p.challenge_losses_week || 0) : (p.challenge_losses || 0);
                                  const total = w + l;
                                  return total > 0 ? ((w / total) * 100).toFixed(0) + '%' : '0%';
                                })()}
                              </span></td>
                          </>
                        ) : (
                          <>
                            <td className="py-4 px-4 text-center hidden sm:table-cell">
                              <div className="text-sm font-semibold text-emerald-400">{p.ppg?.toFixed(1) || '0.0'} <span className="text-[10px] uppercase font-bold text-gray-500 ml-0.5">PTS</span></div>
                              <div className="text-[11px] font-semibold text-blue-400">{p.rpg?.toFixed(1) || '0.0'} <span className="text-[9px] uppercase font-bold text-gray-500 ml-0.5">REB</span> | {p.apg?.toFixed(1) || '0.0'} <span className="text-[9px] uppercase font-bold text-gray-500 ml-0.5">AST</span></div>
                            </td>
                            <td className="py-4 px-4 text-center">
                              <span className="text-sm font-bold text-white">
                                {(() => {
                                  const tw = activeTab === 'hot_week' ? (p.wins_week || 0) + (p.challenge_wins_week || 0) : ((p.wins || 0) + (p.challenge_wins || 0));
                                  const tl = activeTab === 'hot_week' ? (p.losses_week || 0) + (p.challenge_losses_week || 0) : ((p.losses || 0) + (p.challenge_losses || 0));
                                  return `${tw}W-${tl}L`;
                                })()}
                              </span>
                            </td>
                            {activeTab === 'hot_week' && (
                              <td className="py-4 px-4 text-center">
                                {p.skill_rating_change_week != null ? (
                                  <span className={`text-sm font-medium ${p.skill_rating_change_week >= 0 ? 'text-emerald-400' : 'text-red-400/80'}`}>
                                    {p.skill_rating_change_week >= 0 ? '+' : ''}{p.skill_rating_change_week.toFixed(1)}
                                  </span>
                                ) : (
                                  <span className="text-sm text-gray-500">—</span>
                                )}
                              </td>
                            )}
                          </>
                        )}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
