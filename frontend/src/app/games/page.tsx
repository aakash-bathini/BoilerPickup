'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { useAuth } from '@/lib/auth-context';
import { api } from '@/lib/api';
import { Game } from '@/lib/types';
import { formatESTShort, statusColor } from '@/lib/utils';

const TYPE_TABS = ['All', '5v5', '3v3', '2v2'];
const STATUS_TABS = ['Open', 'In Progress', 'Completed'];

export default function GamesPage() {
  const { user, loading: authLoading } = useAuth();
  const router = useRouter();
  const [games, setGames] = useState<Game[]>([]);
  const [loading, setLoading] = useState(true);
  const [typeFilter, setTypeFilter] = useState('All');
  const [statusFilter, setStatusFilter] = useState('Open');

  useEffect(() => {
    if (!authLoading && !user) router.replace('/login');
  }, [user, authLoading, router]);

  useEffect(() => {
    if (!user) return;
    setLoading(true);
    const filters: { game_type?: string; status?: string } = {};
    if (typeFilter !== 'All') filters.game_type = typeFilter;
    filters.status = statusFilter === 'Open' ? 'open' : statusFilter === 'In Progress' ? 'in_progress' : 'completed';
    api.listGames(filters).then(setGames).catch(() => setGames([])).finally(() => setLoading(false));
  }, [user, typeFilter, statusFilter]);

  if (authLoading || !user) return null;

  return (
    <div className="page-container">
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 mb-6">
        <div>
          <h1 className="text-2xl font-bold text-white">Find Games</h1>
          <p className="text-sm text-gray-500">Games matched to your skill level ({user.ai_skill_rating.toFixed(1)})</p>
        </div>
        <Link href="/games/create" className="btn-primary flex items-center gap-2">
          <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" /></svg>
          Create Game
        </Link>
      </div>

      <div className="flex flex-wrap gap-2 mb-4">
        {TYPE_TABS.map(t => (
          <button key={t} onClick={() => setTypeFilter(t)}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition-all ${
              typeFilter === t ? 'bg-gold-500/20 text-gold-400 border border-gold-500/30' : 'text-gray-400 hover:text-white hover:bg-white/5'
            }`}>{t}</button>
        ))}
        <div className="w-px bg-gold-500/10 mx-2" />
        {STATUS_TABS.map(s => (
          <button key={s} onClick={() => setStatusFilter(s)}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition-all ${
              statusFilter === s ? 'bg-gold-500/20 text-gold-400 border border-gold-500/30' : 'text-gray-400 hover:text-white hover:bg-white/5'
            }`}>{s}</button>
        ))}
      </div>

      {loading ? (
        <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-4">
          {[1, 2, 3].map(i => (
            <div key={i} className="glass-card p-6 animate-pulse">
              <div className="h-4 bg-dark-50 rounded w-1/3 mb-4" />
              <div className="h-3 bg-dark-50 rounded w-2/3 mb-2" />
              <div className="h-3 bg-dark-50 rounded w-1/2" />
            </div>
          ))}
        </div>
      ) : games.length === 0 ? (
        <div className="glass-card p-12 text-center">
          <svg className="w-16 h-16 mx-auto text-gray-600 mb-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1} d="M20 13V6a2 2 0 00-2-2H6a2 2 0 00-2 2v7m16 0v5a2 2 0 01-2 2H6a2 2 0 01-2-2v-5m16 0h-2.586a1 1 0 00-.707.293l-2.414 2.414a1 1 0 01-.707.293h-3.172a1 1 0 01-.707-.293l-2.414-2.414A1 1 0 006.586 13H4" /></svg>
          <div className="text-gray-400 mb-2">No games found</div>
          <p className="text-sm text-gray-600 mb-4">No {typeFilter !== 'All' ? typeFilter : ''} games are currently {statusFilter.toLowerCase()}</p>
          <Link href="/games/create" className="btn-primary inline-block">Create One</Link>
        </div>
      ) : (
        <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-4">
          {games.map((g, i) => (
            <Link key={g.id} href={`/games/${g.id}`}
              className="glass-card-hover p-5 animate-slide-up cursor-pointer" style={{ animationDelay: `${Math.min(i * 0.02, 0.3)}s` }}>
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-2">
                  <span className="px-2.5 py-1 rounded-lg bg-gold-500/10 text-gold-400 text-sm font-bold">{g.game_type}</span>
                  <span className="text-xs text-gray-500">{g.court_type === 'halfcourt' ? 'Half Court' : 'Full Court'}</span>
                </div>
                <span className={`badge ${statusColor(g.status)}`}>{g.status.replace('_', ' ')}</span>
              </div>
              <div className="text-sm text-gray-300 mb-2">{formatESTShort(g.scheduled_time)}</div>
              <div className="flex items-center justify-between text-xs text-gray-500">
                <span>Skill {g.skill_min.toFixed(1)}-{g.skill_max.toFixed(1)}</span>
                <span>{g.participants.length}/{g.max_players} players</span>
              </div>
              {(g.status === 'full' || g.status === 'in_progress') && g.win_prediction != null && (
                <div className="mt-2 flex items-center gap-2 text-xs">
                  <span className="text-gray-500">Win predictor:</span>
                  <span className={g.win_prediction >= 0.5 ? 'text-gold-400 font-medium' : 'text-gray-400'}>A {(g.win_prediction * 100).toFixed(0)}%</span>
                  <span className="text-gray-600">—</span>
                  <span className={g.win_prediction < 0.5 ? 'text-gold-400 font-medium' : 'text-gray-400'}>B {((1 - g.win_prediction) * 100).toFixed(0)}%</span>
                </div>
              )}
              {g.creator_name && (
                <div className="mt-2 text-xs text-gray-600">by {g.creator_name}</div>
              )}
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
