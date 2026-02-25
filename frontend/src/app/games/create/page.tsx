'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/lib/auth-context';
import { api } from '@/lib/api';

const GAME_TYPES = [
  { value: '5v5', label: '5 vs 5', players: 10, court: 'Full Court', desc: 'Classic full squad game' },
  { value: '3v3', label: '3 vs 3', players: 6, court: 'Half Court', desc: 'Fast-paced half court' },
  { value: '2v2', label: '2 vs 2', players: 4, court: 'Half Court', desc: 'Competitive duo game' },
];

export default function CreateGamePage() {
  const { user, loading: authLoading } = useAuth();
  const router = useRouter();
  const [gameType, setGameType] = useState('5v5');
  const [date, setDate] = useState('');
  const [time, setTime] = useState('');
  const [skillMin, setSkillMin] = useState(5);
  const [skillMax, setSkillMax] = useState(9);
  const [courtType, setCourtType] = useState('fullcourt');
  const [notes, setNotes] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [weather, setWeather] = useState<Record<string, unknown>[] | null>(null);

  useEffect(() => {
    if (!authLoading && !user) router.replace('/login');
    api.getWeather().then(w => setWeather(w.forecast as Record<string, unknown>[])).catch(() => {});
  }, [user, authLoading, router]);

  useEffect(() => {
    if (gameType === '5v5') setCourtType('fullcourt');
  }, [gameType]);

  const getWeatherForDate = () => {
    if (!weather || !date) return null;
    return weather.find((d: Record<string, unknown>) => d.date === date);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    if (!date || !time) { setError('Date and time are required'); return; }
    if (skillMin > skillMax) { setError('Minimum skill cannot exceed maximum'); return; }

    setLoading(true);
    try {
      const scheduledTime = `${date}T${time}:00-05:00`;
      const game = await api.createGame({
        game_type: gameType, scheduled_time: scheduledTime,
        skill_min: skillMin, skill_max: skillMax,
        court_type: gameType === '5v5' ? 'fullcourt' : courtType, notes: notes || undefined,
      });
      router.push(`/games/${game.id}`);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to create game');
    } finally {
      setLoading(false);
    }
  };

  if (authLoading || !user) return null;
  const dateWeather = getWeatherForDate();

  return (
    <div className="page-container max-w-2xl mx-auto">
      <h1 className="text-2xl font-bold text-white mb-6 animate-slide-up">Create a Pickup Game</h1>

      <form onSubmit={handleSubmit} className="space-y-6 animate-slide-up" style={{ animationDelay: '0.05s' }}>
        {error && (
          <div className="bg-red-500/10 border border-red-500/20 rounded-xl px-4 py-3 text-sm text-red-400">{error}</div>
        )}

        <div className="glass-card p-6">
          <label className="label-text mb-3 block">Game Type</label>
          <div className="grid grid-cols-3 gap-3">
            {GAME_TYPES.map(gt => (
              <button key={gt.value} type="button" onClick={() => setGameType(gt.value)}
                className={`p-4 rounded-xl border text-center transition-all ${
                  gameType === gt.value
                    ? 'bg-gold-500/10 border-gold-500/40 shadow-gold'
                    : 'bg-dark-300/50 border-gold-500/10 hover:border-gold-500/20'
                }`}>
                <div className={`text-2xl font-black ${gameType === gt.value ? 'text-gold-400' : 'text-gray-400'}`}>{gt.value}</div>
                <div className="text-xs text-gray-500 mt-1">{gt.court}</div>
              </button>
            ))}
          </div>
        </div>

        <div className="glass-card p-6">
          <label className="label-text mb-3 block">When</label>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="text-xs text-gray-500 mb-1 block">Date</label>
              <input type="date" value={date} onChange={e => setDate(e.target.value)} required className="input-field" />
            </div>
            <div>
              <label className="text-xs text-gray-500 mb-1 block">Time (EST)</label>
              <input type="time" value={time} onChange={e => setTime(e.target.value)} required className="input-field" />
            </div>
          </div>
          {dateWeather && (
            <div className="mt-3 flex items-center gap-2 text-sm bg-blue-500/5 border border-blue-500/10 rounded-lg px-3 py-2">
              <svg className="w-4 h-4 text-blue-400 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 15a4 4 0 004 4h9a5 5 0 10-.1-9.999 5.002 5.002 0 10-9.78 2.096A4.001 4.001 0 003 15z" /></svg>
              <span className="text-gray-400">
                {String(dateWeather.description)} · {String(dateWeather.high)}°F / {String(dateWeather.low)}°F · {String(dateWeather.precip_chance)}% rain
              </span>
            </div>
          )}
        </div>

        <div className="glass-card p-6">
          <label className="label-text mb-3 block">Skill Range ({Number(skillMin).toFixed(1)} - {Number(skillMax).toFixed(1)})</label>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="text-xs text-gray-500 mb-1 block">Minimum</label>
              <input type="number" min={1} max={10} step={0.1} value={skillMin} onChange={e => setSkillMin(Number(e.target.value))} className="input-field" />
            </div>
            <div>
              <label className="text-xs text-gray-500 mb-1 block">Maximum</label>
              <input type="number" min={1} max={10} step={0.1} value={skillMax} onChange={e => setSkillMax(Number(e.target.value))} className="input-field" />
            </div>
          </div>
          <div className="mt-2 h-2 bg-dark-300 rounded-full overflow-hidden">
            <div className="h-full bg-gradient-to-r from-gold-500/60 to-gold-400" style={{ marginLeft: `${((skillMin - 1) / 9) * 100}%`, width: `${((skillMax - skillMin) / 9) * 100}%` }} />
          </div>
        </div>

        {gameType !== '5v5' && (
          <div className="glass-card p-6">
            <label className="label-text mb-3 block">Court Type</label>
            <div className="grid grid-cols-2 gap-3">
              {['fullcourt', 'halfcourt'].map(ct => (
                <button key={ct} type="button" onClick={() => setCourtType(ct)}
                  className={`p-3 rounded-xl border text-center transition-all ${
                    courtType === ct ? 'bg-gold-500/10 border-gold-500/40' : 'bg-dark-300/50 border-gold-500/10 hover:border-gold-500/20'
                  }`}>
                  <span className={courtType === ct ? 'text-gold-400 font-medium' : 'text-gray-400'}>
                    {ct === 'fullcourt' ? 'Full Court' : 'Half Court'}
                  </span>
                </button>
              ))}
            </div>
          </div>
        )}

        <div className="glass-card p-6">
          <label className="label-text mb-3 block">Notes (optional)</label>
          <textarea value={notes} onChange={e => setNotes(e.target.value)} rows={3}
            placeholder="Any details about the game..." className="input-field resize-none" />
        </div>

        <button type="submit" disabled={loading} className="btn-primary w-full text-lg py-4">
          {loading ? 'Creating...' : 'Create Game'}
        </button>
      </form>
    </div>
  );
}
