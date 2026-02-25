'use client';

import { useEffect, useState, Suspense } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import Link from 'next/link';
import { useAuth } from '@/lib/auth-context';
import { api } from '@/lib/api';
import { UserSearchResult } from '@/lib/types';
import { skillColor } from '@/lib/utils';

function SearchContent() {
  const { user, loading: authLoading } = useAuth();
  const router = useRouter();
  const searchParams = useSearchParams();
  const [query, setQuery] = useState(searchParams.get('q') || '');
  const [results, setResults] = useState<UserSearchResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [position, setPosition] = useState('');
  const [minSkill, setMinSkill] = useState('');
  const [maxSkill, setMaxSkill] = useState('');
  const [minGames, setMinGames] = useState('');
  const [minWins, setMinWins] = useState('');
  const [minPpg, setMinPpg] = useState('');
  const [minRpg, setMinRpg] = useState('');
  const [minApg, setMinApg] = useState('');
  const [minSpg, setMinSpg] = useState('');
  const [minBpg, setMinBpg] = useState('');
  const [minFgPct, setMinFgPct] = useState('');
  const [sortBy, setSortBy] = useState('skill');
  const [showFilters, setShowFilters] = useState(false);

  useEffect(() => {
    if (!authLoading && !user) router.replace('/login');
  }, [user, authLoading, router]);

  const doSearch = async () => {
    if (!user) return;
    setLoading(true);
    try {
      const filters: Record<string, unknown> = { sort_by: sortBy };
      if (position) filters.position = position;
      if (minSkill) filters.min_skill = Number(minSkill);
      if (maxSkill) filters.max_skill = Number(maxSkill);
      if (minGames) filters.min_games = Number(minGames);
      if (minWins) filters.min_wins = Number(minWins);
      if (minPpg) filters.min_ppg = Number(minPpg);
      if (minRpg) filters.min_rpg = Number(minRpg);
      if (minApg) filters.min_apg = Number(minApg);
      if (minSpg) filters.min_spg = Number(minSpg);
      if (minBpg) filters.min_bpg = Number(minBpg);
      if (minFgPct) filters.min_fg_pct = Number(minFgPct);
      const r = await api.searchUsers(query, filters as Parameters<typeof api.searchUsers>[1]);
      setResults(r);
    } catch {
      setResults([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (!user) return;
    const t = setTimeout(doSearch, 300);
    return () => clearTimeout(t);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [query, position, minSkill, maxSkill, minGames, minWins, minPpg, minRpg, minApg, minSpg, minBpg, minFgPct, sortBy, user]);

  if (authLoading || !user) return null;

  return (
    <div className="page-container max-w-4xl mx-auto">
      <h1 className="text-2xl font-bold text-white mb-6 animate-slide-up">Find Players</h1>

      <div className="glass-card p-4 mb-6 animate-slide-up" style={{ animationDelay: '0.05s' }}>
        <div className="flex gap-3">
          <input type="text" value={query} onChange={e => setQuery(e.target.value)}
            placeholder="Search by name or username..."
            className="input-field" />
          <button onClick={() => setShowFilters(!showFilters)}
            className={`btn-secondary px-4 text-sm whitespace-nowrap ${showFilters ? 'bg-gold-500/10' : ''}`}>
            <svg className="w-4 h-4 inline mr-1" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 4a1 1 0 011-1h16a1 1 0 011 1v2.586a1 1 0 01-.293.707l-6.414 6.414a1 1 0 00-.293.707V17l-4 4v-6.586a1 1 0 00-.293-.707L3.293 7.293A1 1 0 013 6.586V4z" /></svg>
            Filters
          </button>
        </div>

        {showFilters && (
          <div className="mt-4 pt-4 border-t border-gold-500/10 grid grid-cols-2 md:grid-cols-3 gap-4 animate-fade-in">
            <div>
              <label className="text-xs text-gray-500 mb-1 block">Position</label>
              <select value={position} onChange={e => setPosition(e.target.value)} className="input-field text-sm">
                <option value="">Any</option>
                {['PG', 'SG', 'SF', 'PF', 'C'].map(p => <option key={p} value={p}>{p}</option>)}
              </select>
            </div>
            <div>
              <label className="text-xs text-gray-500 mb-1 block">Min Skill</label>
              <input type="number" min={1} max={10} value={minSkill} onChange={e => setMinSkill(e.target.value)} className="input-field text-sm" placeholder="1" />
            </div>
            <div>
              <label className="text-xs text-gray-500 mb-1 block">Max Skill</label>
              <input type="number" min={1} max={10} value={maxSkill} onChange={e => setMaxSkill(e.target.value)} className="input-field text-sm" placeholder="10" />
            </div>
            <div>
              <label className="text-xs text-gray-500 mb-1 block">Min Games</label>
              <input type="number" min={0} value={minGames} onChange={e => setMinGames(e.target.value)} className="input-field text-sm" placeholder="0" />
            </div>
            <div>
              <label className="text-xs text-gray-500 mb-1 block">Min Wins</label>
              <input type="number" min={0} value={minWins} onChange={e => setMinWins(e.target.value)} className="input-field text-sm" placeholder="0" />
            </div>
            <div>
              <label className="text-xs text-gray-500 mb-1 block">Min PPG</label>
              <input type="number" min={0} step={0.1} value={minPpg} onChange={e => setMinPpg(e.target.value)} className="input-field text-sm" placeholder="—" />
            </div>
            <div>
              <label className="text-xs text-gray-500 mb-1 block">Min RPG</label>
              <input type="number" min={0} step={0.1} value={minRpg} onChange={e => setMinRpg(e.target.value)} className="input-field text-sm" placeholder="—" />
            </div>
            <div>
              <label className="text-xs text-gray-500 mb-1 block">Min APG</label>
              <input type="number" min={0} step={0.1} value={minApg} onChange={e => setMinApg(e.target.value)} className="input-field text-sm" placeholder="—" />
            </div>
            <div>
              <label className="text-xs text-gray-500 mb-1 block">Min SPG</label>
              <input type="number" min={0} step={0.1} value={minSpg} onChange={e => setMinSpg(e.target.value)} className="input-field text-sm" placeholder="—" />
            </div>
            <div>
              <label className="text-xs text-gray-500 mb-1 block">Min BPG</label>
              <input type="number" min={0} step={0.1} value={minBpg} onChange={e => setMinBpg(e.target.value)} className="input-field text-sm" placeholder="—" />
            </div>
            <div>
              <label className="text-xs text-gray-500 mb-1 block">Min FG%</label>
              <input type="number" min={0} max={100} step={1} value={minFgPct} onChange={e => setMinFgPct(e.target.value)} className="input-field text-sm" placeholder="—" />
            </div>
            <div>
              <label className="text-xs text-gray-500 mb-1 block">Sort By</label>
              <select value={sortBy} onChange={e => setSortBy(e.target.value)} className="input-field text-sm">
                <option value="skill">Skill Rating</option>
                <option value="games">Games Played</option>
                <option value="wins">Wins</option>
                <option value="name">Name</option>
              </select>
            </div>
          </div>
        )}
      </div>

      {loading ? (
        <div className="glass-card p-8 text-center text-gray-500">Searching...</div>
      ) : results.length === 0 ? (
        <div className="glass-card p-8 text-center text-gray-500">
          {query || showFilters ? 'No players match your criteria' : 'Type a name or username to search. Players who haven\'t played yet won\'t appear in Rankings but are here.'}
        </div>
      ) : (
        <div className="space-y-2">
          {results.map((p, i) => (
            <Link key={p.id} href={`/profile/${p.id}`}
              className="glass-card-hover p-4 flex items-center justify-between animate-slide-up block"
              style={{ animationDelay: `${Math.min(i * 0.02, 0.3)}s` }}>
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-full bg-gold-500/10 flex items-center justify-center text-gold-400 text-sm font-bold">
                  {p.display_name.charAt(0)}
                </div>
                <div>
                  <div className="text-sm font-medium text-white">{p.display_name}</div>
                  <div className="text-xs text-gray-500">@{p.username} · {p.preferred_position || 'Any'} · {p.games_played} games</div>
                </div>
              </div>
              <div className="flex items-center gap-4">
                <div className="text-right">
                  <div className={`text-sm font-bold ${skillColor(p.ai_skill_rating)}`}>{p.ai_skill_rating.toFixed(1)}</div>
                  <div className="text-[10px] text-gray-600">{p.wins}W–{p.losses}L team</div>
                </div>
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}

export default function SearchPage() {
  return (
    <Suspense fallback={<div className="page-container"><div className="glass-card p-12 text-center text-gray-500">Loading...</div></div>}>
      <SearchContent />
    </Suspense>
  );
}
