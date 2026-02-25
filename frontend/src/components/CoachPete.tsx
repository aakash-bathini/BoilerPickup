'use client';

import React, { useState, useRef, useEffect } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { api } from '@/lib/api';
import { useAuth } from '@/lib/auth-context';

function renderMarkdown(text: string): React.ReactNode {
  const parts = text.split(/(\*\*[^*]+\*\*|\*[^*]+\*)/g);
  return parts.map((part, i) => {
    if (part.startsWith('**') && part.endsWith('**')) {
      return <strong key={i} className="font-semibold text-white">{part.slice(2, -2)}</strong>;
    }
    if (part.startsWith('*') && part.endsWith('*') && part.length > 2) {
      return <em key={i} className="italic">{part.slice(1, -1)}</em>;
    }
    return part;
  });
}

interface ChatMsg {
  role: 'user' | 'assistant';
  content: string;
}

interface MatchedPlayer {
  id: number;
  display_name: string;
  username: string;
  ai_skill_rating: number;
}

type MatchType = 'similar' | 'teammate' | null;

// Purdue Pete–inspired mascot: train engineer / boilermaker coach (gold & black)
function PeteMascotIcon({ className = 'w-10 h-10', dark = false }: { className?: string; dark?: boolean }) {
  const face = dark ? '#2a2a2a' : '#1a1a1a';
  const accent = '#CFB991';
  const cap = dark ? '#B89F65' : '#CFB991';
  return (
    <svg viewBox="0 0 64 64" className={className} fill="none">
      <circle cx="32" cy="36" r="18" fill={face} stroke={accent} strokeWidth="2" />
      <path d="M14 28 Q32 16 50 28 L48 32 Q32 22 16 32 Z" fill={cap} stroke="#9A8347" strokeWidth="1" />
      <path d="M18 26 Q32 18 46 26" stroke="#9A8347" strokeWidth="1.5" fill="none" />
      <ellipse cx="26" cy="34" rx="3" ry="3.5" fill={accent} />
      <ellipse cx="38" cy="34" rx="3" ry="3.5" fill={accent} />
      <path d="M24 42 Q32 48 40 42" stroke={accent} strokeWidth="2" strokeLinecap="round" fill="none" />
      <circle cx="32" cy="22" r="4" fill="none" stroke={accent} strokeWidth="1.5" strokeDasharray="2 2" />
    </svg>
  );
}

const QUICK_ACTIONS = [
  { label: 'Find a match', query: 'Find a match' },
  { label: 'Find teammate', query: 'Find me a teammate' },
  { label: 'My stats', query: 'My stats' },
  { label: 'Weather today', query: 'What is the weather at the CoRec?' },
  { label: 'Weather in 2 days', query: 'What is the weather in two days?' },
  { label: 'How can I improve?', query: 'How can I improve?' },
  { label: 'Players on fire', query: 'Who are the players on fire?' },
  { label: '1v1 tips', query: 'Give me 1v1 tips' },
];

const NAV_ACTIONS = [
  { label: 'Create Game', href: '/games/create', icon: '➕' },
  { label: 'Find Games', href: '/games', icon: '🏀' },
  { label: 'Challenges', href: '/challenges', icon: '⚡' },
  { label: 'My Profile', href: '/profile', icon: '👤' },
];

export default function CoachPete() {
  const router = useRouter();
  const { user, refresh: refreshAuth } = useAuth();

  // Coach Pete only available when logged in — needs your data to help
  if (!user) return null;
  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState<ChatMsg[]>([
    { role: 'assistant', content: "Hey! I'm Coach Pete — your AI assistant for Boiler Pickup. Ask me anything: find a teammate, check your stats, get the weather, or I can take you anywhere on the site." },
  ]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [matchPopup, setMatchPopup] = useState<MatchedPlayer[] | null>(null);
  const [matchType, setMatchType] = useState<MatchType>(null);
  const chatEnd = useRef<HTMLDivElement>(null);

  useEffect(() => {
    chatEnd.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const send = async () => {
    if (!input.trim() || loading) return;
    const msg = input.trim();
    setInput('');
    setMessages(prev => [...prev, { role: 'user', content: msg }]);
    setLoading(true);
    setMatchPopup(null);
    setMatchType(null);
    try {
      const res = await api.chatWithPete(msg);
      setMessages(prev => [...prev, { role: 'assistant', content: res.reply }]);
      const players = (res.data?.matched_players as MatchedPlayer[] | undefined) ?? null;
      const type = (res.data?.match_type as MatchType) ?? 'similar';
      if (players?.length) {
        setMatchPopup(players);
        setMatchType(type);
      }
    } catch {
      setMessages(prev => [...prev, { role: 'assistant', content: "Sorry, I couldn't process that right now. Try again!" }]);
    } finally {
      setLoading(false);
    }
  };

  const goToProfileToChallenge = (player: MatchedPlayer) => {
    setMatchPopup(null);
    setMatchType(null);
    setOpen(false);
    router.push(`/profile/${player.id}?challenge=1`);
  };

  const handleNavAction = (href: string) => {
    setOpen(false);
    router.push(href);
  };

  return (
    <>
      {/* FAB: Purdue Pete mascot button */}
      <button
        onClick={() => setOpen(!open)}
        className={`fixed bottom-6 right-6 z-50 rounded-2xl overflow-hidden transition-all duration-300 ease-out ${
          open
            ? 'w-12 h-12 bg-dark-300 border border-gold-500/30 shadow-lg rotate-0'
            : 'w-16 h-16 bg-gradient-to-br from-gold-500 to-gold-700 shadow-gold-lg border-2 border-gold-400/40 animate-pete-idle hover:scale-105 active:scale-95'
        }`}
        title="Coach Pete"
      >
        {open ? (
          <span className="flex items-center justify-center w-full h-full text-black">
            <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </span>
        ) : (
          <span className="flex items-center justify-center w-full h-full p-1">
            <PeteMascotIcon className="w-12 h-12" dark={false} />
          </span>
        )}
      </button>

      {/* Chat panel */}
      {open && (
        <div
          className="fixed bottom-24 right-6 z-50 w-[400px] max-w-[calc(100vw-2rem)] rounded-2xl overflow-hidden flex flex-col animate-slide-up-fade"
          style={{
            height: '560px',
            background: 'linear-gradient(180deg, rgba(26,26,26,0.98) 0%, rgba(10,10,10,0.99) 100%)',
            boxShadow: '0 25px 50px -12px rgba(0,0,0,0.5), 0 0 0 1px rgba(207,185,145,0.1)',
            backdropFilter: 'blur(20px)',
          }}
        >
          {/* Header */}
          <div className="px-4 py-3.5 flex items-center gap-3 border-b border-gold-500/15 bg-gradient-to-r from-gold-500/8 to-transparent">
            <div className="w-11 h-11 rounded-xl bg-gradient-to-br from-gold-500 to-gold-700 flex items-center justify-center shadow-lg border border-gold-400/20">
              <PeteMascotIcon className="w-7 h-7" dark={true} />
            </div>
            <div className="flex-1 min-w-0">
              <div className="text-sm font-bold text-white">Coach Pete</div>
              <div className="text-[10px] text-gray-500 truncate">AI Assistant · Boiler Pickup</div>
            </div>
          </div>

          {/* Quick nav — simplify using the site */}
          <div className="px-3 py-2 border-b border-gold-500/10 flex flex-wrap gap-1.5">
            {NAV_ACTIONS.map((a, i) => (
              <button
                key={a.href}
                onClick={() => handleNavAction(a.href)}
                className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-[11px] font-medium text-gray-400 hover:text-gold-400 hover:bg-gold-500/10 border border-transparent hover:border-gold-500/20 transition-all duration-200"
                style={{ animationDelay: `${i * 50}ms` }}
              >
                <span>{a.icon}</span>
                <span>{a.label}</span>
              </button>
            ))}
          </div>

          {/* Messages */}
          <div className="flex-1 overflow-y-auto p-4 space-y-3 min-h-0">
            {messages.map((m, i) => (
              <div
                key={i}
                className={`flex ${m.role === 'user' ? 'justify-end' : 'justify-start'} animate-message-in`}
                style={{ animationDelay: `${i * 30}ms` }}
              >
                <div
                  className={`max-w-[88%] rounded-2xl px-4 py-2.5 text-sm leading-relaxed ${
                    m.role === 'user'
                      ? 'bg-gold-500/20 text-white border border-gold-500/20'
                      : 'bg-dark-300/80 text-gray-200 border border-gold-500/5'
                  }`}
                >
                  {m.content.split('\n').map((line, li) => (
                    <p key={li} className={li > 0 ? 'mt-1.5' : ''}>{renderMarkdown(line)}</p>
                  ))}
                </div>
              </div>
            ))}
            {loading && (
              <div className="flex justify-start animate-message-in">
                <div className="rounded-2xl px-4 py-3 bg-dark-300/80 border border-gold-500/5">
                  <div className="flex gap-1.5">
                    <span className="w-2 h-2 rounded-full bg-gold-500/60 animate-bounce" style={{ animationDelay: '0ms' }} />
                    <span className="w-2 h-2 rounded-full bg-gold-500/60 animate-bounce" style={{ animationDelay: '150ms' }} />
                    <span className="w-2 h-2 rounded-full bg-gold-500/60 animate-bounce" style={{ animationDelay: '300ms' }} />
                  </div>
                </div>
              </div>
            )}
            <div ref={chatEnd} />
          </div>

          {/* Input + quick prompts */}
          <div className="p-3 border-t border-gold-500/10 bg-dark-400/30">
            <div className="flex gap-2 mb-2">
              <input
                value={input}
                onChange={e => setInput(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && send()}
                placeholder="Ask Coach Pete..."
                className="flex-1 bg-dark-300/90 border border-gold-500/10 rounded-xl px-3.5 py-2.5 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-gold-500/40 focus:ring-1 focus:ring-gold-500/20 transition-all"
              />
              <button
                onClick={send}
                disabled={loading}
                className="px-4 py-2.5 rounded-xl bg-gold-500/25 text-gold-400 hover:bg-gold-500/35 disabled:opacity-50 transition-all font-medium"
              >
                Send
              </button>
            </div>
            <div className="flex flex-wrap gap-1.5">
              {QUICK_ACTIONS.map(q => (
                <button
                  key={q.label}
                  onClick={() => {
                    if (loading) return;
                    setMessages(prev => [...prev, { role: 'user', content: q.query }]);
                    setLoading(true);
                    setMatchPopup(null);
                    setMatchType(null);
                    api.chatWithPete(q.query).then(res => {
                      setMessages(prev => [...prev, { role: 'assistant', content: res.reply }]);
                      const players = (res.data?.matched_players as MatchedPlayer[] | undefined) ?? null;
                      const type = (res.data?.match_type as MatchType) ?? 'similar';
                      if (players?.length) {
                        setMatchPopup(players);
                        setMatchType(type);
                      }
                    }).catch(() => {
                      setMessages(prev => [...prev, { role: 'assistant', content: "Sorry, I couldn't process that right now. Try again!" }]);
                    }).finally(() => setLoading(false));
                  }}
                  className="text-[10px] px-2.5 py-1 rounded-lg bg-dark-300/60 text-gray-500 hover:text-gold-400 hover:bg-gold-500/10 transition-colors"
                >
                  {q.label}
                </button>
              ))}
            </div>
          </div>

          {/* Match / Teammate popup overlay */}
          {matchPopup && matchPopup.length > 0 && (
            <div className="absolute inset-0 bg-black/80 backdrop-blur-sm flex flex-col items-center justify-center p-4 animate-fade-in">
              <div
                className="w-full max-h-[75%] overflow-y-auto rounded-xl p-4 animate-scale-in"
                style={{
                  background: 'linear-gradient(180deg, rgba(26,26,26,0.98) 0%, rgba(14,14,14,0.99) 100%)',
                  border: '1px solid rgba(207,185,145,0.2)',
                  boxShadow: '0 20px 40px rgba(0,0,0,0.4)',
                }}
              >
                <div className="flex items-center justify-between mb-4">
                  <h3 className="text-sm font-bold text-white">
                    {matchType === 'teammate' ? '🤝 Teammates for You' : '🎯 Your Matches'}
                  </h3>
                  <button
                    onClick={() => { setMatchPopup(null); setMatchType(null); }}
                    className="p-1 rounded-lg text-gray-500 hover:text-white hover:bg-white/10 transition-colors"
                  >
                    <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                    </svg>
                  </button>
                </div>
                <div className="space-y-2">
                  {matchPopup.map((p, i) => (
                    <div
                      key={p.id}
                      className="flex items-center justify-between gap-3 p-3 rounded-xl bg-dark-300/60 border border-gold-500/10 hover:border-gold-500/20 transition-colors"
                      style={{ animationDelay: `${i * 60}ms` }}
                    >
                      <div className="min-w-0">
                        <div className="text-sm font-semibold text-white truncate">{p.display_name}</div>
                        <div className="text-[10px] text-gray-500">@{p.username} · {p.ai_skill_rating.toFixed(1)} skill</div>
                      </div>
                      <div className="flex gap-2 shrink-0">
                        <button
                          onClick={() => goToProfileToChallenge(p)}
                          className="px-2.5 py-1.5 rounded-lg text-[11px] font-medium bg-gold-500/20 text-gold-400 hover:bg-gold-500/30 transition-colors"
                        >
                          Challenge 1v1
                        </button>
                        <Link
                          href={`/messages?user=${p.id}`}
                          onClick={() => setMatchPopup(null)}
                          className="px-2.5 py-1.5 rounded-lg text-[11px] font-medium bg-dark-400 text-gray-300 hover:bg-dark-500 transition-colors"
                        >
                          Message
                        </Link>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}
        </div>
      )}
    </>
  );
}
