'use client';

import { useState, useEffect, Suspense } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import Link from 'next/link';
import { api, ApiError } from '@/lib/api';

function VerifyContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const email = searchParams.get('email') || '';
  const [code, setCode] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [resending, setResending] = useState(false);

  useEffect(() => {
    if (!email || !email.toLowerCase().endsWith('@purdue.edu')) {
      router.replace('/register');
    }
  }, [email, router]);

  const handleVerify = async () => {
    if (!code || code.length !== 6) {
      setError('Enter the 6-digit code from your email');
      return;
    }
    setError('');
    setLoading(true);
    try {
      await api.verifyEmail(email, code);
      router.push('/login?verified=true');
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Verification failed');
    } finally {
      setLoading(false);
    }
  };

  const handleResend = async () => {
    setError('');
    setResending(true);
    try {
      await api.resendVerificationCode(email);
      setError('');
      alert('New code sent! Check your email.');
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not resend code');
    } finally {
      setResending(false);
    }
  };

  if (!email) return null;

  return (
    <div className="min-h-[calc(100vh-4rem)] flex items-center justify-center px-4 py-8">
      <div className="w-full max-w-md animate-scale-in">
        <div className="text-center mb-8">
          <h1 className="text-3xl font-bold text-white">Verify Your Email</h1>
          <p className="text-gray-400 mt-2">
            We sent a 6-digit code to <span className="text-gold-400">{email}</span>
          </p>
        </div>

        <div className="glass-card p-8">
          {error && (
            <div className="bg-red-500/10 border border-red-500/20 rounded-xl px-4 py-3 text-sm text-red-400 mb-6">{error}</div>
          )}

          <div>
            <label className="label-text">Verification Code</label>
            <input
              type="text"
              inputMode="numeric"
              maxLength={6}
              value={code}
              onChange={e => setCode(e.target.value.replace(/\D/g, ''))}
              placeholder="000000"
              className="input-field text-center text-2xl tracking-[0.5em] font-mono"
            />
          </div>

          <button onClick={handleVerify} disabled={loading} className="btn-primary w-full mt-6 py-3">
            {loading ? 'Verifying...' : 'Verify & Continue'}
          </button>

          <p className="text-center text-sm text-gray-500 mt-4">
            Didn&apos;t receive the code?{' '}
            <button onClick={handleResend} disabled={resending} className="text-gold-400 hover:text-gold-300 font-medium">
              {resending ? 'Sending...' : 'Resend'}
            </button>
          </p>
        </div>

        <p className="text-center text-sm text-gray-500 mt-6">
          <Link href="/login" className="text-gold-400 hover:text-gold-300 font-medium">Back to Sign in</Link>
        </p>
      </div>
    </div>
  );
}

export default function VerifyPage() {
  return (
    <Suspense fallback={<div className="min-h-[calc(100vh-4rem)] flex items-center justify-center"><div className="text-gray-500">Loading...</div></div>}>
      <VerifyContent />
    </Suspense>
  );
}
