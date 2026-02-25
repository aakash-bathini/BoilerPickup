'use client';

import Link from 'next/link';
import { useAuth } from '@/lib/auth-context';
import { useRouter } from 'next/navigation';
import { useEffect } from 'react';

export default function LandingPage() {
  const { user, loading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!loading && user) router.replace('/dashboard');
  }, [user, loading, router]);

  // Skip loading skeleton when clearly not logged in (no token) — instant render
  const hasToken = typeof window !== 'undefined' && !!localStorage.getItem('token');
  const showLoading = loading && hasToken;

  if (showLoading) {
    return (
      <div className="min-h-screen bg-dark-500">
        <div className="max-w-5xl mx-auto px-4 py-28 md:py-36">
          <div className="animate-pulse space-y-6">
            <div className="h-8 bg-dark-300 rounded w-64 mx-auto" />
            <div className="h-16 bg-dark-300 rounded w-96 mx-auto" />
            <div className="h-6 bg-dark-300 rounded w-80 mx-auto" />
            <div className="flex gap-4 justify-center pt-4">
              <div className="h-12 w-32 bg-dark-300 rounded-xl" />
              <div className="h-12 w-24 bg-dark-300 rounded-xl" />
            </div>
          </div>
        </div>
      </div>
    );
  }

  const features = [
    { title: 'AI Matchmaking', desc: 'Neural skill model balances teams for fair, competitive games every time.', icon: 'M13 10V3L4 14h7v7l9-11h-7z' },
    { title: '1v1 Challenges', desc: 'Challenge any player to a 1v1. Wins and losses affect your skill rating.', icon: 'M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5' },
    { title: 'Live Stat Tracking', desc: 'Track PTS, REB, AST, STL, BLK, TOV, and shooting splits every game.', icon: 'M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z' },
    { title: 'Coach Pete AI', desc: 'Sign in to unlock your AI assistant — find teammates, analyze stats, get the weather.', icon: 'M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z' },
  ];

  // Example skill progression (date, rating) — what you'll see on your profile
  const exampleSkillProgression = [
    { date: 'Jan 15', rating: 4.2 },
    { date: 'Jan 18', rating: 4.8 },
    { date: 'Jan 22', rating: 5.1 },
    { date: 'Jan 25', rating: 5.6 },
    { date: 'Jan 28', rating: 5.3 },
    { date: 'Feb 1', rating: 6.0 },
    { date: 'Feb 5', rating: 6.4 },
    { date: 'Feb 8', rating: 6.9 },
    { date: 'Feb 12', rating: 7.1 },
  ];

  const gameTypes = [
    { type: '2v2', court: 'Half Court', desc: 'Quick runs' },
    { type: '3v3', court: 'Half Court', desc: 'Classic pickup' },
    { type: '5v5', court: 'Full Court', desc: 'Full squad' },
  ];

  return (
    <div className="min-h-screen bg-dark-500">
      {/* Hero — background image via CSS (no Next Image) + dark overlay for readability */}
      <section
        className="relative min-h-[70vh] flex flex-col items-center justify-center bg-dark-500 bg-cover bg-center"
        style={{ backgroundImage: `linear-gradient(to bottom, rgba(0,0,0,0.85) 0%, rgba(0,0,0,0.6) 50%, rgba(10,10,10,1) 100%), url(https://images.unsplash.com/photo-1546519638-68e109498ffc?w=1920&q=80)` }}
      >
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_center,rgba(207,185,145,0.06)_0%,transparent_70%)]" />
        <div className="relative z-10 max-w-5xl mx-auto px-4 py-28 md:py-36 text-center">
          <div className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full bg-gold-500/20 border border-gold-500/30 mb-6 animate-fade-in">
            <div className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
            <span className="text-sm text-gold-300 font-medium">France A. Córdova Recreational Sports Center</span>
          </div>
          <h1 className="text-5xl md:text-7xl font-black text-white mb-6 animate-slide-up tracking-tight drop-shadow-lg">
            Find Your <span className="text-transparent bg-clip-text bg-gradient-to-r from-gold-400 to-gold-500">Perfect Game</span>
          </h1>
          <p className="text-xl text-gray-300 max-w-2xl mx-auto mb-10 animate-slide-up drop-shadow" style={{ animationDelay: '0.1s' }}>
            AI-powered pickup basketball at the CoRec. Fair teams. Tracked stats. Real competition.
          </p>
          <div className="flex flex-col sm:flex-row gap-4 justify-center animate-slide-up" style={{ animationDelay: '0.2s' }}>
            <Link href="/register" className="btn-primary text-lg px-8 py-4 shadow-gold">Get Started</Link>
            <Link href="/login" className="btn-secondary text-lg px-8 py-4">Sign In</Link>
          </div>
        </div>
      </section>

      {/* Bold game types — StarkHacks-style big numbers */}
      <section className="py-16 px-4 border-b border-gold-500/10 bg-dark-300/30">
        <div className="max-w-6xl mx-auto">
          <h2 className="text-center text-sm font-semibold text-gray-500 uppercase tracking-widest mb-10">Game Types</h2>
          <div className="grid grid-cols-3 gap-6 md:gap-12">
            {gameTypes.map((g, i) => (
              <div key={g.type} className="text-center group">
                <div className="text-5xl md:text-7xl font-black text-gold-400 group-hover:text-gold-300 transition-colors duration-300" style={{ textShadow: '0 0 40px rgba(207, 185, 145, 0.2)' }}>
                  {g.type}
                </div>
                <div className="text-sm font-medium text-gray-400 mt-1">{g.court}</div>
                <div className="text-xs text-gray-500 mt-0.5">{g.desc}</div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Live preview — skill rating progression (what you'll see on your profile) */}
      <section className="py-20 px-4 border-b border-gold-500/10">
        <div className="max-w-3xl mx-auto">
          <h2 className="text-2xl font-bold text-center text-white mb-2">See Your Progress</h2>
          <p className="text-gray-500 text-center mb-8 max-w-lg mx-auto">Your skill rating (1–10) tracked over time — view this on your profile as you play.</p>
          <div className="glass-card p-6 group hover:border-gold-500/20 transition-colors duration-300">
            <div className="text-sm font-medium text-gray-400 mb-4">Skill Rating Progression</div>
            <p className="text-[10px] text-gray-500 mb-2">Rating up and down over time (example)</p>
            <div className="h-28">
              <svg viewBox="0 0 100 60" className="w-full h-full" preserveAspectRatio="none">
                <polyline
                  fill="none"
                  stroke="#CFB991"
                  strokeWidth="1.5"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  points={exampleSkillProgression.map((d, i) => {
                    const x = (i / Math.max(1, exampleSkillProgression.length - 1)) * 96 + 2;
                    const y = 56 - ((d.rating - 4) / 3.5) * 48;
                    return `${x} ${y}`;
                  }).join(' ')}
                />
              </svg>
            </div>
            <div className="flex justify-between mt-2 text-[10px] text-gray-600">
              <span>{exampleSkillProgression[0]?.date}</span>
              <span>{exampleSkillProgression[exampleSkillProgression.length - 1]?.rating.toFixed(1)}</span>
              <span>{exampleSkillProgression[exampleSkillProgression.length - 1]?.date}</span>
            </div>
          </div>
        </div>
      </section>

      {/* Features */}
      <section className="py-20 px-4">
        <div className="max-w-6xl mx-auto">
          <h2 className="text-3xl font-bold text-center text-white mb-4">Built for Ballers</h2>
          <p className="text-gray-500 text-center mb-14 max-w-xl mx-auto">Everything you need to organize, compete, and improve at pickup basketball.</p>
          <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-6">
            {features.map((f, i) => (
              <div key={f.title} className="glass-card-hover p-6 animate-slide-up transition-all duration-300 group" style={{ animationDelay: `${i * 0.08}s` }}>
                <div className="w-12 h-12 rounded-xl bg-gold-500/10 border border-gold-500/20 flex items-center justify-center mb-4 group-hover:bg-gold-500/15 group-hover:border-gold-500/30 transition-colors">
                  <svg className="w-6 h-6 text-gold-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d={f.icon} />
                  </svg>
                </div>
                <h3 className="text-lg font-semibold text-white mb-2">{f.title}</h3>
                <p className="text-sm text-gray-400 leading-relaxed">{f.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* How it works */}
      <section className="py-20 px-4 bg-dark-300/40">
        <div className="max-w-4xl mx-auto text-center">
          <h2 className="text-3xl font-bold text-white mb-6">How It Works</h2>
          <div className="grid md:grid-cols-3 gap-8">
            {[
              { step: '1', title: 'Create Your Profile', desc: 'Sign up with your Purdue email and set your skill level.' },
              { step: '2', title: 'Find or Create a Game', desc: 'Browse games at your skill level or organize your own at the CoRec.' },
              { step: '3', title: 'Play & Track', desc: 'AI balances teams. Track stats. Climb the leaderboard. Coach Pete helps when you need it.' },
            ].map((s) => (
              <div key={s.step} className="flex flex-col items-center">
                <div className="w-14 h-14 rounded-2xl bg-gradient-to-br from-gold-500 to-gold-700 flex items-center justify-center text-black text-xl font-black mb-4 shadow-gold">{s.step}</div>
                <h3 className="text-lg font-semibold text-white mb-2">{s.title}</h3>
                <p className="text-sm text-gray-400">{s.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="py-20 px-4">
        <div className="max-w-3xl mx-auto text-center glass-card p-12 border border-gold-500/10 hover:border-gold-500/20 transition-colors">
          <h2 className="text-3xl font-bold text-white mb-4">Ready to Ball?</h2>
          <p className="text-gray-400 mb-6">Join the Purdue pickup basketball community. Sign in to unlock Coach Pete — your AI assistant in the corner.</p>
          <Link href="/register" className="btn-primary text-lg px-10 py-4">Create Free Account</Link>
        </div>
      </section>

      <footer className="border-t border-gold-500/10 py-8 px-4">
        <div className="max-w-6xl mx-auto flex flex-col md:flex-row justify-between items-center gap-4">
          <div className="flex items-center gap-2">
            <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-gold-500 to-gold-700 flex items-center justify-center">
              <span className="text-black font-black text-xs">BP</span>
            </div>
            <span className="text-sm text-gray-500">Boiler Pickup — ECE 570 AI Project</span>
          </div>
          <p className="text-xs text-gray-600">Purdue University · France A. Córdova Recreational Sports Center</p>
        </div>
      </footer>
    </div>
  );
}
