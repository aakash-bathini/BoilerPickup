'use client';

import { useState, useRef, useEffect } from 'react';
import Link from 'next/link';
import { useRouter, usePathname } from 'next/navigation';
import { useAuth } from '@/lib/auth-context';
import { api } from '@/lib/api';
import { UserSearchResult } from '@/lib/types';

export default function Navbar() {
  const { user, logout } = useAuth();
  const router = useRouter();
  const pathname = usePathname();
  const [mobileOpen, setMobileOpen] = useState(false);
  const [profileOpen, setProfileOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState<UserSearchResult[]>([]);
  const [searchFocused, setSearchFocused] = useState(false);
  const searchRef = useRef<HTMLDivElement>(null);
  const profileRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (searchRef.current && !searchRef.current.contains(e.target as Node)) {
        setSearchFocused(false);
      }
      if (profileRef.current && !profileRef.current.contains(e.target as Node)) {
        setProfileOpen(false);
      }
    }
    document.addEventListener('mousedown', handleClick);
    return () => document.removeEventListener('mousedown', handleClick);
  }, []);

  useEffect(() => {
    if (!searchQuery.trim()) { setSearchResults([]); return; }
    const t = setTimeout(async () => {
      try {
        const r = await api.searchUsers(searchQuery);
        setSearchResults(r);
      } catch { setSearchResults([]); }
    }, 300);
    return () => clearTimeout(t);
  }, [searchQuery]);

  const handleLogout = () => {
    logout();
    router.push('/');
  };

  const navLinks = user ? [
    { href: '/dashboard', label: 'Dashboard' },
    { href: '/games', label: 'Games' },
    { href: '/challenges', label: '1v1 Challenges' },
    { href: '/messages', label: 'Messages' },
    { href: '/leaderboard', label: 'Rankings' },
    { href: '/search', label: 'Search' },
  ] : [];

  return (
    <nav className="sticky top-0 z-50 bg-dark-500/80 backdrop-blur-xl border-b border-gold-500/10">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16">
          <Link href={user ? '/dashboard' : '/'} className="flex items-center gap-2.5 group">
            <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-gold-500 to-gold-700 flex items-center justify-center group-hover:shadow-gold transition-shadow">
              <span className="text-black font-black text-sm">BP</span>
            </div>
            <span className="font-bold text-lg text-white hidden sm:block">Boiler Pickup</span>
          </Link>

          {user && (
            <div className="hidden md:flex items-center gap-1">
              {navLinks.map(l => (
                <Link key={l.href} href={l.href}
                  className={`px-3 py-2 rounded-lg text-sm font-medium transition-all ${
                    pathname === l.href || pathname?.startsWith(l.href + '/')
                      ? 'text-gold-400 bg-gold-500/10'
                      : 'text-gray-400 hover:text-white hover:bg-white/5'
                  }`}>
                  {l.label}
                </Link>
              ))}
            </div>
          )}

          <div className="flex items-center gap-3">
            {user && (
              <div ref={searchRef} className="relative hidden sm:block">
                <input
                  type="text"
                  placeholder="Search players..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  onFocus={() => setSearchFocused(true)}
                  className="w-48 lg:w-64 bg-dark-200/60 border border-gold-500/10 rounded-lg px-3 py-1.5 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-gold-500/30 focus:w-72 transition-all"
                />
                <svg className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                </svg>

                {searchFocused && (searchResults.length > 0 || searchQuery.trim().length > 0) && (
                  <div className="absolute top-full mt-2 w-80 bg-dark-200 border border-gold-500/15 rounded-xl shadow-2xl overflow-hidden animate-scale-in">
                    {searchResults.slice(0, 6).map(u => (
                      <button key={u.id}
                        onClick={() => { router.push(`/profile/${u.id}`); setSearchFocused(false); setSearchQuery(''); }}
                        className="w-full flex items-center gap-3 px-4 py-3 hover:bg-gold-500/5 transition-colors text-left">
                        <div className="w-8 h-8 rounded-full bg-gradient-to-br from-gold-500/20 to-gold-700/20 flex items-center justify-center text-gold-400 text-xs font-bold">
                          {u.display_name.charAt(0)}
                        </div>
                        <div className="flex-1 min-w-0">
                          <div className="text-sm font-medium text-white truncate">{u.display_name}</div>
                          <div className="text-xs text-gray-500">@{u.username} · {u.ai_skill_rating.toFixed(1)} skill</div>
                        </div>
                        <div className="text-xs text-gray-500">{u.preferred_position || '—'}</div>
                      </button>
                    ))}
                    {searchResults.length === 0 && searchQuery.trim() && (
                      <div className="px-4 py-3 text-sm text-gray-500">No players found</div>
                    )}
                    <button
                      onClick={() => { router.push(`/search?q=${encodeURIComponent(searchQuery)}`); setSearchFocused(false); setSearchQuery(''); }}
                      className="w-full flex items-center gap-2 px-4 py-2.5 text-sm text-gold-400 hover:bg-gold-500/5 border-t border-gold-500/10 transition-colors">
                      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 4a1 1 0 011-1h16a1 1 0 011 1v2.586a1 1 0 01-.293.707l-6.414 6.414a1 1 0 00-.293.707V17l-4 4v-6.586a1 1 0 00-.293-.707L3.293 7.293A1 1 0 013 6.586V4z" /></svg>
                      Advanced Search with Filters
                    </button>
                  </div>
                )}
              </div>
            )}

            {user ? (
              <div ref={profileRef} className="relative">
                <button onClick={() => setProfileOpen(!profileOpen)}
                  className="flex items-center gap-2 px-2 py-1.5 rounded-lg hover:bg-white/5 transition-colors">
                  <div className="w-8 h-8 rounded-full bg-gradient-to-br from-gold-500 to-gold-700 flex items-center justify-center text-black text-xs font-bold">
                    {user.display_name.charAt(0)}
                  </div>
                  <span className="text-sm text-white font-medium hidden lg:block">{user.display_name}</span>
                  <svg className={`w-4 h-4 text-gray-400 transition-transform ${profileOpen ? 'rotate-180' : ''}`} fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                  </svg>
                </button>

                {profileOpen && (
                  <div className="absolute right-0 top-full mt-2 w-56 bg-dark-200 border border-gold-500/15 rounded-xl shadow-2xl overflow-hidden animate-scale-in">
                    <div className="px-4 py-3 border-b border-gold-500/10">
                      <div className="text-sm font-medium text-white">{user.display_name}</div>
                    </div>
                    <Link href="/profile" onClick={() => setProfileOpen(false)}
                      className="flex items-center gap-2 px-4 py-2.5 text-sm text-gray-300 hover:bg-gold-500/5 hover:text-white transition-colors">
                      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" /></svg>
                      My Profile
                    </Link>
                    <button onClick={() => { setProfileOpen(false); handleLogout(); }}
                      className="w-full flex items-center gap-2 px-4 py-2.5 text-sm text-red-400 hover:bg-red-500/5 transition-colors">
                      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" /></svg>
                      Sign Out
                    </button>
                  </div>
                )}
              </div>
            ) : (
              <div className="flex items-center gap-2">
                <Link href="/login" className="text-sm text-gray-300 hover:text-white px-3 py-2 rounded-lg transition-colors">Sign In</Link>
                <Link href="/register" className="text-sm bg-gradient-to-r from-gold-500 to-gold-600 text-black font-semibold px-4 py-2 rounded-lg hover:from-gold-400 hover:to-gold-500 transition-all">Sign Up</Link>
              </div>
            )}

            {user && (
              <button onClick={() => setMobileOpen(!mobileOpen)} className="md:hidden p-2 rounded-lg hover:bg-white/5">
                <svg className="w-5 h-5 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  {mobileOpen
                    ? <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                    : <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
                  }
                </svg>
              </button>
            )}
          </div>
        </div>
      </div>

      {mobileOpen && user && (
        <div className="md:hidden border-t border-gold-500/10 bg-dark-500/95 animate-slide-up">
          <div className="px-4 py-3">
            <input
              type="text"
              placeholder="Search players..."
              value={searchQuery}
              onChange={e => setSearchQuery(e.target.value)}
              className="w-full bg-dark-200/60 border border-gold-500/10 rounded-lg px-3 py-2 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-gold-500/30"
            />
          </div>
          <div className="px-2 pb-3 space-y-1">
            {navLinks.map(l => (
              <Link key={l.href} href={l.href}
                onClick={() => setMobileOpen(false)}
                className={`block px-3 py-2.5 rounded-lg text-sm font-medium ${
                  pathname === l.href ? 'text-gold-400 bg-gold-500/10' : 'text-gray-400 hover:text-white hover:bg-white/5'
                }`}>
                {l.label}
              </Link>
            ))}
          </div>
        </div>
      )}
    </nav>
  );
}
