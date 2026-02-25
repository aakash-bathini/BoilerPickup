'use client';

import { useEffect, useState, useRef, Suspense } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import Link from 'next/link';
import { useAuth } from '@/lib/auth-context';
import { api } from '@/lib/api';
import { ConversationPreview, Message } from '@/lib/types';
import { timeAgo } from '@/lib/utils';

function MessagesContent() {
  const { user, loading: authLoading } = useAuth();
  const router = useRouter();
  const searchParams = useSearchParams();
  const initialUserId = searchParams.get('user') || searchParams.get('dm');
  const [conversations, setConversations] = useState<ConversationPreview[]>([]);
  const [activeUser, setActiveUser] = useState<number | null>(initialUserId ? Number(initialUserId) : null);
  const [activeName, setActiveName] = useState('');
  const [messages, setMessages] = useState<Message[]>([]);
  const [msgInput, setMsgInput] = useState('');
  const [loading, setLoading] = useState(true);
  const chatEnd = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!authLoading && !user) router.replace('/login');
  }, [user, authLoading, router]);

  useEffect(() => {
    if (initialUserId) {
      setActiveUser(Number(initialUserId));
    }
  }, [initialUserId]);

  useEffect(() => {
    if (!user) return;
    api.getConversations().then(c => {
      setConversations(c);
      if (initialUserId) {
        const conv = c.find(cc => cc.user_id === Number(initialUserId));
        if (conv) setActiveName(conv.display_name);
        else api.getUser(Number(initialUserId)).then(u => setActiveName(u.display_name)).catch(() => {});
      }
      setLoading(false);
    }).catch(() => setLoading(false));
  }, [user, initialUserId]);

  useEffect(() => {
    if (!activeUser) return;
    api.getDmThread(activeUser).then(setMessages).catch(() => {});
    const interval = setInterval(() => {
      api.getDmThread(activeUser).then(setMessages).catch(() => {});
    }, 3000);
    return () => clearInterval(interval);
  }, [activeUser]);

  useEffect(() => {
    chatEnd.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const openConversation = (userId: number, name: string) => {
    setActiveUser(userId);
    setActiveName(name);
  };

  const sendMsg = async () => {
    if (!msgInput.trim() || !activeUser) return;
    try {
      await api.sendMessage({ recipient_id: activeUser, content: msgInput });
      setMsgInput('');
      const msgs = await api.getDmThread(activeUser);
      setMessages(msgs);
      api.getConversations().then(setConversations).catch(() => {});
    } catch { /* ignore */ }
  };

  if (authLoading || !user) return null;

  return (
    <div className="page-container">
      <h1 className="text-2xl font-bold text-white mb-6">Messages</h1>
      <div className="grid md:grid-cols-3 gap-6" style={{ minHeight: '500px' }}>
        <div className="glass-card overflow-hidden">
          <div className="p-4 border-b border-gold-500/10">
            <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-wider">Conversations</h2>
          </div>
          <div className="overflow-y-auto" style={{ maxHeight: '450px' }}>
            {loading ? (
              <div className="p-4 text-center text-gray-600 text-sm">Loading...</div>
            ) : conversations.length === 0 ? (
              <div className="p-6 text-center">
                <p className="text-gray-500 text-sm mb-2">No conversations yet</p>
                <Link href="/search" className="text-gold-400 text-xs hover:text-gold-300">Find players →</Link>
              </div>
            ) : conversations.map(c => (
              <button key={c.user_id} onClick={() => openConversation(c.user_id, c.display_name)}
                className={`w-full text-left p-4 border-b border-gold-500/5 hover:bg-gold-500/5 transition-colors ${
                  activeUser === c.user_id ? 'bg-gold-500/10' : ''
                }`}>
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-full bg-gradient-to-br from-gold-500/20 to-gold-700/20 flex items-center justify-center text-gold-400 text-sm font-bold shrink-0">
                    {c.display_name.charAt(0)}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex justify-between items-center">
                      <span className="text-sm font-medium text-white truncate">{c.display_name}</span>
                      <span className="text-[10px] text-gray-600 shrink-0 ml-2">{timeAgo(c.last_message_time)}</span>
                    </div>
                    <p className="text-xs text-gray-500 truncate mt-0.5">{c.last_message}</p>
                  </div>
                </div>
              </button>
            ))}
          </div>
        </div>

        <div className="md:col-span-2 glass-card flex flex-col">
          {activeUser ? (
            <>
              <div className="p-4 border-b border-gold-500/10 flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className="w-8 h-8 rounded-full bg-gold-500/15 flex items-center justify-center text-gold-400 text-sm font-bold">{(activeName || '?').charAt(0)}</div>
                  <Link href={`/profile/${activeUser}`} className="text-white font-medium hover:text-gold-400 transition-colors">{activeName}</Link>
                </div>
                <Link href={`/profile/${activeUser}`} className="text-xs text-gray-500 hover:text-gold-400 transition-colors">View Profile</Link>
              </div>
              <div className="flex-1 overflow-y-auto p-4 space-y-3" style={{ maxHeight: '380px' }}>
                {messages.length === 0 ? (
                  <div className="text-center text-sm text-gray-600 py-8">Send the first message!</div>
                ) : messages.map(m => (
                  <div key={m.id} className={`flex ${m.sender_id === user.id ? 'justify-end' : 'justify-start'}`}>
                    <div className={`max-w-[75%] rounded-2xl px-4 py-2.5 ${
                      m.sender_id === user.id ? 'bg-gold-500/15 text-white' : 'bg-dark-300 text-gray-200'
                    }`}>
                      {m.sender_id !== user.id && <div className="text-xs text-gold-400 mb-0.5">{m.sender_name}</div>}
                      <div className="text-sm">{m.content}</div>
                      <div className="text-[10px] text-gray-500 mt-1">{timeAgo(m.created_at)}</div>
                    </div>
                  </div>
                ))}
                <div ref={chatEnd} />
              </div>
              <div className="p-3 border-t border-gold-500/10 flex gap-2">
                <input value={msgInput} onChange={e => setMsgInput(e.target.value)}
                  onKeyDown={e => e.key === 'Enter' && sendMsg()}
                  placeholder="Type a message..." className="input-field text-sm py-2" />
                <button onClick={sendMsg} className="btn-primary px-4 py-2 text-sm">Send</button>
              </div>
            </>
          ) : (
            <div className="flex-1 flex items-center justify-center text-gray-600 text-sm">
              Select a conversation or find a player to message
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default function MessagesPage() {
  return (
    <Suspense fallback={<div className="page-container"><div className="glass-card p-12 text-center text-gray-500">Loading...</div></div>}>
      <MessagesContent />
    </Suspense>
  );
}
