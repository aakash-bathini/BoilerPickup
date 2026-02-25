'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/lib/auth-context';
import { api } from '@/lib/api';
import { CareerStatsByType, SkillHistoryEntry } from '@/lib/types';
import { skillColor, positionLabel } from '@/lib/utils';
import { SkillRatingChart } from '@/components/SkillRatingChart';

export default function ProfilePage() {
  const { user, loading: authLoading, refresh: refreshAuth } = useAuth();
  const router = useRouter();
  const [statsByType, setStatsByType] = useState<CareerStatsByType | null>(null);
  const [skillHistory, setSkillHistory] = useState<SkillHistoryEntry[]>([]);
  const [editing, setEditing] = useState(false);
  const [form, setForm] = useState({ display_name: '', height: '', weight: '', preferred_position: '', bio: '' });

  useEffect(() => {
    if (!authLoading && !user) router.replace('/login');
  }, [user, authLoading, router]);

  useEffect(() => {
    if (!user) return;
    refreshAuth();
    Promise.all([
      api.getCareerStatsByGameType(user.id),
      api.getSkillHistory(user.id),
    ]).then(([sbt, sh]) => {
      setStatsByType(sbt);
      setSkillHistory(sh);
    }).catch(() => {});
    setForm({
      display_name: user.display_name, height: user.height || '',
      weight: user.weight ? String(user.weight) : '', preferred_position: user.preferred_position || '',
      bio: user.bio || '',
    });
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user?.id]);

  const handleSave = async () => {
    try {
      await api.updateMe({
        display_name: form.display_name || undefined,
        height: form.height || undefined,
        weight: form.weight ? Number(form.weight) : undefined,
        preferred_position: form.preferred_position || undefined,
        bio: form.bio || undefined,
      } as Partial<typeof user & Record<string, unknown>>);
      setEditing(false);
      window.location.reload();
    } catch { /* ignore */ }
  };

  if (authLoading || !user) return null;

  return (
    <div className="page-container max-w-4xl mx-auto">
      <div className="glass-card p-6 md:p-8 mb-6 animate-slide-up">
        <div className="flex flex-col md:flex-row items-start gap-6">
          <div className="w-20 h-20 rounded-2xl bg-gradient-to-br from-gold-500 to-gold-700 flex items-center justify-center text-black text-3xl font-black shrink-0">
            {user.display_name.charAt(0)}
          </div>
          <div className="flex-1">
            <div className="flex items-center gap-3 mb-1">
              <h1 className="text-2xl font-bold text-white">{user.display_name}</h1>
              <span className="text-sm text-gray-500">@{user.username}</span>
            </div>
            <div className="flex flex-wrap gap-3 text-sm text-gray-400 mb-3">
              <span>{positionLabel(user.preferred_position)}</span>
              {user.height && <span>{user.height}</span>}
              {user.weight && <span>{user.weight} lbs</span>}
            </div>
            {user.bio && <p className="text-sm text-gray-400">{user.bio}</p>}
            <button onClick={() => setEditing(!editing)} className="btn-secondary text-sm mt-3 px-4 py-1.5">
              {editing ? 'Cancel' : 'Edit Profile'}
            </button>
          </div>
          <div className="text-center px-6 py-3 rounded-xl bg-gold-500/10 border border-gold-500/20">
            <div className={`text-3xl font-black ${skillColor(user.ai_skill_rating)}`}>{user.ai_skill_rating.toFixed(1)}</div>
            <div className="text-[10px] text-gray-500 uppercase tracking-wider mt-1">Skill Rating</div>
            <div className="text-xs text-gray-600">{(user.skill_confidence * 100).toFixed(0)}% confident</div>
          </div>
        </div>

        {editing && (
          <div className="mt-6 pt-6 border-t border-gold-500/10 space-y-4 animate-fade-in">
            <div className="grid md:grid-cols-2 gap-4">
              <div><label className="label-text">Display Name</label><input value={form.display_name} onChange={e => setForm(f => ({ ...f, display_name: e.target.value }))} className="input-field" /></div>
              <div><label className="label-text">Position</label>
                <select value={form.preferred_position} onChange={e => setForm(f => ({ ...f, preferred_position: e.target.value }))} className="input-field">
                  <option value="">Any</option>
                  {['PG', 'SG', 'SF', 'PF', 'C'].map(p => <option key={p} value={p}>{p}</option>)}
                </select>
              </div>
              <div><label className="label-text">Height</label><input value={form.height} onChange={e => setForm(f => ({ ...f, height: e.target.value }))} className="input-field" placeholder={`6'2"`} /></div>
              <div><label className="label-text">Weight</label><input type="number" value={form.weight} onChange={e => setForm(f => ({ ...f, weight: e.target.value }))} className="input-field" /></div>
            </div>
            <div><label className="label-text">Bio</label><textarea value={form.bio} onChange={e => setForm(f => ({ ...f, bio: e.target.value }))} className="input-field resize-none" rows={3} /></div>
            <button onClick={handleSave} className="btn-primary">Save Changes</button>
          </div>
        )}
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        {[
          { label: 'Team Games', value: user.games_played },
          { label: 'Team Record', value: `${user.wins}W-${user.losses}L` },
          { label: '1v1 Record', value: `${user.challenge_wins}W-${user.challenge_losses}L` },
          { label: 'Win Rate', value: (user.games_played + user.challenge_wins + user.challenge_losses) > 0 ? `${(((user.wins + user.challenge_wins) / (user.games_played + user.challenge_wins + user.challenge_losses)) * 100).toFixed(0)}%` : '—' },
        ].map(s => (
          <div key={s.label} className="glass-card p-4 text-center animate-slide-up">
            <div className="text-xl font-bold text-white">{s.value}</div>
            <div className="text-xs text-gray-500 mt-1">{s.label}</div>
          </div>
        ))}
      </div>

      {statsByType && (statsByType.five_v_five.games_played > 0 || statsByType.three_v_three.games_played > 0 || statsByType.two_v_two.games_played > 0) ? (
        <div className="glass-card p-6 animate-slide-up mb-6" style={{ animationDelay: '0.1s' }}>
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
        <div className="glass-card p-6 animate-slide-up mb-6">
          <h2 className="text-lg font-semibold text-white mb-4">Skill Rating Progression</h2>
          <SkillRatingChart data={skillHistory} />
        </div>
      ) : (
        <div className="glass-card p-8 text-center text-gray-500 animate-slide-up">
          No stats recorded yet. Play your first game to start tracking!
        </div>
      )}
    </div>
  );
}
