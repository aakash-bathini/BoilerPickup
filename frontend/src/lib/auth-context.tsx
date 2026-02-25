'use client';

import { createContext, useContext, useState, useEffect, useCallback, useRef, ReactNode } from 'react';
import { User } from './types';
import { api } from './api';

const INACTIVITY_TIMEOUT_MS = 4 * 60 * 60 * 1000; // 4 hours

interface AuthContextType {
  user: User | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
  refresh: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType>({
  user: null,
  loading: true,
  login: async () => {},
  logout: () => {},
  refresh: async () => {},
});

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const lastActivityRef = useRef(Date.now());
  const inactivityTimerRef = useRef<NodeJS.Timeout | null>(null);

  const doLogout = useCallback(() => {
    api.logout();
    setUser(null);
  }, []);

  const refresh = useCallback(async () => {
    const done = () => setLoading(false);
    try {
      const token = localStorage.getItem('token');
      if (!token) {
        setUser(null);
        done();
        return;
      }
      // Timeout: if backend is down/slow, don't block the UI forever
      const timeout = setTimeout(done, 2000);
      const me = await api.getMe();
      clearTimeout(timeout);
      setUser(me);
    } catch {
      setUser(null);
      localStorage.removeItem('token');
    } finally {
      done();
    }
  }, []);

  const resetInactivityTimer = useCallback(() => {
    lastActivityRef.current = Date.now();
    localStorage.setItem('bp_last_activity', String(Date.now()));
    if (inactivityTimerRef.current) clearTimeout(inactivityTimerRef.current);
    inactivityTimerRef.current = setTimeout(() => {
      if (localStorage.getItem('token')) {
        doLogout();
        window.location.href = '/login';
      }
    }, INACTIVITY_TIMEOUT_MS);
  }, [doLogout]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  useEffect(() => {
    // Check if session expired while away
    const lastActivity = localStorage.getItem('bp_last_activity');
    if (lastActivity && Date.now() - Number(lastActivity) > INACTIVITY_TIMEOUT_MS) {
      if (localStorage.getItem('token')) {
        doLogout();
      }
    }

    const events = ['mousedown', 'keydown', 'scroll', 'touchstart'];
    const handler = () => resetInactivityTimer();
    events.forEach(e => window.addEventListener(e, handler, { passive: true }));
    resetInactivityTimer();

    // Refresh user data when tab becomes visible again
    const handleVisibility = () => {
      if (document.visibilityState === 'visible' && localStorage.getItem('token')) {
        refresh();
        resetInactivityTimer();
      }
    };
    document.addEventListener('visibilitychange', handleVisibility);

    return () => {
      events.forEach(e => window.removeEventListener(e, handler));
      document.removeEventListener('visibilitychange', handleVisibility);
      if (inactivityTimerRef.current) clearTimeout(inactivityTimerRef.current);
    };
  }, [doLogout, refresh, resetInactivityTimer]);

  const login = async (email: string, password: string) => {
    await api.login(email, password);
    resetInactivityTimer();
    await refresh();
  };

  return (
    <AuthContext.Provider value={{ user, loading, login, logout: doLogout, refresh }}>
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => useContext(AuthContext);
