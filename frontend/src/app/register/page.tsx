'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { api, ApiError } from '@/lib/api';

const POSITIONS = [
  { value: 'PG', label: 'Point Guard' },
  { value: 'SG', label: 'Shooting Guard' },
  { value: 'SF', label: 'Small Forward' },
  { value: 'PF', label: 'Power Forward' },
  { value: 'C', label: 'Center' },
];

const SKILL_LABELS: Record<number, string> = {
  1: 'Beginner', 2: 'Novice', 3: 'Learning', 4: 'Intermediate',
  5: 'Average', 6: 'Above Average', 7: 'Good', 8: 'Great', 9: 'Elite', 10: 'Pro',
};

export default function RegisterPage() {
  const router = useRouter();
  const [step, setStep] = useState(1);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [resending, setResending] = useState(false);
  const [code, setCode] = useState('');
  const [form, setForm] = useState({
    email: '', username: '', password: '', confirmPassword: '',
    display_name: '', height: '', weight: '', preferred_position: '',
    self_reported_skill: 5,
  });

  const update = (field: string, value: string | number) => {
    setForm(prev => ({ ...prev, [field]: value }));
    setError('');
  };

  const validateStep1 = () => {
    const email = form.email.toLowerCase();
    if (!email.endsWith('@purdue.edu') && !email.endsWith('@purdoo.com')) {
      setError('Must use a @purdue.edu or @purdoo.com email');
      return false;
    }
    if (form.username.length < 3) { setError('Username must be at least 3 characters'); return false; }
    if (form.password.length < 6) { setError('Password must be at least 6 characters'); return false; }
    if (form.password !== form.confirmPassword) { setError('Passwords do not match'); return false; }
    return true;
  };

  const validateStep2 = () => {
    if (!form.display_name.trim()) { setError('Display name is required'); return false; }
    return true;
  };

  const handleNext = () => {
    setError('');
    if (step === 1 && !validateStep1()) return;
    if (step === 2 && !validateStep2()) return;
    setStep(s => s + 1);
  };

  const handleSendCode = async () => {
    setError('');
    setLoading(true);
    try {
      const msg = await api.register({
        email: form.email,
        username: form.username,
        password: form.password,
        display_name: form.display_name,
        height: form.height || undefined,
        weight: form.weight ? Number(form.weight) : undefined,
        preferred_position: form.preferred_position || undefined,
        self_reported_skill: form.self_reported_skill,
      });
      if (form.email.toLowerCase().endsWith('@purdoo.com')) {
        await api.login(form.email, form.password);
        router.push('/dashboard');
      } else {
        setStep(4);
        setCode('');
      }
    } catch (err: unknown) {
      setError(err instanceof ApiError ? err.message : err instanceof Error ? err.message : 'Registration failed');
    } finally {
      setLoading(false);
    }
  };

  const handleVerifyAndCreate = async () => {
    if (!code || code.length !== 6) {
      setError('Enter the 6-digit code from your email');
      return;
    }
    setError('');
    setLoading(true);
    try {
      await api.verifyEmail(form.email, code);
      router.push('/login?verified=true');
    } catch (err: unknown) {
      setError(err instanceof ApiError ? err.message : 'Verification failed');
    } finally {
      setLoading(false);
    }
  };

  const handleResend = async () => {
    setError('');
    setResending(true);
    try {
      await api.resendVerificationCode(form.email);
      setCode('');
      setError('');
      alert('New code sent! Check your email.');
    } catch (err: unknown) {
      setError(err instanceof ApiError ? err.message : 'Could not resend code');
    } finally {
      setResending(false);
    }
  };

  return (
    <div className="min-h-[calc(100vh-4rem)] flex items-center justify-center px-4 py-8">
      <div className="w-full max-w-lg animate-scale-in">
        <div className="text-center mb-8">
          <h1 className="text-3xl font-bold text-white">Join Boiler Pickup</h1>
          <p className="text-gray-400 mt-2">Create your account and start playing</p>
        </div>

        <div className="flex items-center justify-center gap-2 mb-8">
          {[1, 2, 3, 4].map(s => (
            <div key={s} className="flex items-center gap-2">
              <div className={`w-8 h-8 rounded-lg flex items-center justify-center text-xs font-bold transition-all ${
                s < step ? 'bg-gold-500 text-black' :
                s === step ? 'bg-gold-500/20 text-gold-400 border border-gold-500/40' :
                'bg-dark-200 text-gray-500'
              }`}>{s}</div>
              {s < 4 && <div className={`w-4 h-0.5 ${s < step ? 'bg-gold-500' : 'bg-dark-200'}`} />}
            </div>
          ))}
        </div>

        <div className="glass-card p-8">
          {error && (
            <div className="bg-red-500/10 border border-red-500/20 rounded-xl px-4 py-3 text-sm text-red-400 mb-6">{error}</div>
          )}

          {step === 1 && (
            <div className="space-y-4 animate-fade-in">
              <h2 className="text-xl font-semibold text-white mb-4">Account Details</h2>
              <div>
                <label className="label-text">Purdue Email</label>
                <input type="email" value={form.email} onChange={e => update('email', e.target.value)}
                  placeholder="boilermaker@purdue.edu" className="input-field" />
              </div>
              <div>
                <label className="label-text">Username</label>
                <input type="text" value={form.username} onChange={e => update('username', e.target.value)}
                  placeholder="Choose a username" className="input-field" />
              </div>
              <div>
                <label className="label-text">Password</label>
                <input type="password" value={form.password} onChange={e => update('password', e.target.value)}
                  placeholder="Min 6 characters" className="input-field" />
              </div>
              <div>
                <label className="label-text">Confirm Password</label>
                <input type="password" value={form.confirmPassword} onChange={e => update('confirmPassword', e.target.value)}
                  placeholder="Confirm your password" className="input-field" />
              </div>
            </div>
          )}

          {step === 2 && (
            <div className="space-y-4 animate-fade-in">
              <h2 className="text-xl font-semibold text-white mb-4">Player Info</h2>
              <div>
                <label className="label-text">Display Name</label>
                <input type="text" value={form.display_name} onChange={e => update('display_name', e.target.value)}
                  placeholder="How others will see you" className="input-field" />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="label-text">Height</label>
                  <input type="text" value={form.height} onChange={e => update('height', e.target.value)}
                    placeholder={`6'2"`} className="input-field" />
                </div>
                <div>
                  <label className="label-text">Weight (lbs)</label>
                  <input type="number" value={form.weight} onChange={e => update('weight', e.target.value)}
                    placeholder="180" className="input-field" />
                </div>
              </div>
              <div>
                <label className="label-text">Preferred Position</label>
                <select value={form.preferred_position} onChange={e => update('preferred_position', e.target.value)} className="input-field">
                  <option value="">Any Position</option>
                  {POSITIONS.map(p => <option key={p.value} value={p.value}>{p.label} ({p.value})</option>)}
                </select>
              </div>
            </div>
          )}

          {step === 3 && (
            <div className="space-y-6 animate-fade-in">
              <h2 className="text-xl font-semibold text-white mb-4">Self-Reported Skill</h2>
              <p className="text-sm text-gray-400">Be honest — our AI will adjust your rating based on actual performance.</p>
              <div className="text-center py-4">
                <div className="text-6xl font-black text-gold-400 mb-2">{form.self_reported_skill}</div>
                <div className="text-lg text-gray-300 font-medium">{SKILL_LABELS[form.self_reported_skill]}</div>
              </div>
              <input type="range" min={1} max={10} value={form.self_reported_skill}
                onChange={e => update('self_reported_skill', Number(e.target.value))}
                className="w-full h-2 bg-dark-300 rounded-full appearance-none cursor-pointer
                  [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-6
                  [&::-webkit-slider-thumb]:h-6 [&::-webkit-slider-thumb]:rounded-full
                  [&::-webkit-slider-thumb]:bg-gold-500 [&::-webkit-slider-thumb]:shadow-gold" />
              <div className="flex justify-between text-xs text-gray-500">
                <span>Beginner</span><span>Pro</span>
              </div>
            </div>
          )}

          {step === 4 && (
            <div className="space-y-4 animate-fade-in">
              <h2 className="text-xl font-semibold text-white mb-4">Verify Your Email</h2>
              <p className="text-sm text-gray-400">
                We sent a 6-digit code to <span className="text-gold-400">{form.email}</span>. Enter it below to create your account.
              </p>
              <div>
                <label className="label-text">Verification Code</label>
                <input
                  type="text"
                  inputMode="numeric"
                  maxLength={6}
                  value={code}
                  onChange={e => { setCode(e.target.value.replace(/\D/g, '')); setError(''); }}
                  placeholder="000000"
                  className="input-field text-center text-2xl tracking-[0.5em] font-mono"
                />
              </div>
              <button onClick={handleVerifyAndCreate} disabled={loading} className="btn-primary w-full py-3">
                {loading ? 'Verifying...' : 'Verify & Create Account'}
              </button>
              <p className="text-center text-sm text-gray-500">
                Didn&apos;t receive the code?{' '}
                <button onClick={handleResend} disabled={resending} className="text-gold-400 hover:text-gold-300 font-medium">
                  {resending ? 'Sending...' : 'Resend'}
                </button>
              </p>
            </div>
          )}

          <div className="flex justify-between mt-8">
            {step > 1 && step < 4 ? (
              <button onClick={() => setStep(s => s - 1)} className="btn-secondary px-6 py-2.5">Back</button>
            ) : (
              <div />
            )}
            {step < 3 ? (
              <button onClick={handleNext} className="btn-primary px-6 py-2.5">Continue</button>
            ) : step === 3 ? (
              <button onClick={handleSendCode} disabled={loading} className="btn-primary px-8 py-2.5">
                {loading ? 'Sending Code...' : 'Send Verification Code'}
              </button>
            ) : null}
          </div>
        </div>
        <p className="text-center text-sm text-gray-500 mt-6">
          Already have an account? <Link href="/login" className="text-gold-400 hover:text-gold-300 font-medium">Sign in</Link>
        </p>
      </div>
    </div>
  );
}
