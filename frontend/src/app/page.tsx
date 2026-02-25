'use client';

import Link from 'next/link';
import { useAuth } from '@/lib/auth-context';
import { useRouter } from 'next/navigation';
import { useEffect, useRef } from 'react';
import { motion, useScroll, useTransform, Variants } from 'framer-motion';
import { BrainCircuit, Trophy, Activity, MessageSquare, Users, Star, ArrowRight, Target } from 'lucide-react';
import { SkillRatingChart } from '@/components/SkillRatingChart';

const MOCK_CHART_DATA = [
  { timestamp: new Date(Date.now() - 10 * 24 * 60 * 60 * 1000).toISOString(), rating: 4.0 },
  { timestamp: new Date(Date.now() - 8 * 24 * 60 * 60 * 1000).toISOString(), rating: 5.2 },
  { timestamp: new Date(Date.now() - 5 * 24 * 60 * 60 * 1000).toISOString(), rating: 4.8 },
  { timestamp: new Date(Date.now() - 2 * 24 * 60 * 60 * 1000).toISOString(), rating: 6.9 },
  { timestamp: new Date().toISOString(), rating: 7.4 }
];

const FADE_UP: Variants = {
  hidden: { opacity: 0, y: 30 },
  visible: { opacity: 1, y: 0, transition: { duration: 0.6, ease: "easeOut" } }
};

const STAGGER: Variants = {
  hidden: { opacity: 0 },
  visible: { opacity: 1, transition: { staggerChildren: 0.15 } }
};

export default function LandingPage() {
  const { user, loading } = useAuth();
  const router = useRouter();
  const targetRef = useRef<HTMLDivElement>(null);
  const { scrollYProgress } = useScroll({
    target: targetRef,
    offset: ["start start", "end start"]
  });

  const yBg = useTransform(scrollYProgress, [0, 1], ["0%", "30%"]);
  const opacityBg = useTransform(scrollYProgress, [0, 0.8], [1, 0]);

  useEffect(() => {
    if (!loading && user) router.replace('/dashboard');
  }, [user, loading, router]);

  const hasToken = typeof window !== 'undefined' && !!localStorage.getItem('token');
  const showLoading = loading && hasToken;

  if (showLoading) {
    return (
      <div className="min-h-screen bg-[#050505] flex items-center justify-center">
        <div className="w-10 h-10 border-2 border-gold-500 border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  const features = [
    { title: 'Smart Matchmaking', desc: 'Our analytics engine evaluates player skill sets to construct perfectly balanced teams trained on real NBA data. Every game is competitive.', icon: <BrainCircuit className="w-6 h-6" /> },
    { title: '1v1 Prove It', desc: 'Challenge rivals directly. Your Elo rating rises with every victory—the ultimate way to climb the ranks.', icon: <Trophy className="w-6 h-6" /> },
    { title: 'Pro-Level Analytics', desc: 'Track points, rebounds, assists, and shooting percentages. Watch your custom dashboard light up with real data.', icon: <Activity className="w-6 h-6" /> },
    { title: 'Coach Pete Assistant', desc: 'Your personal AI scout. Find complementary teammates, analyze your shooting slumps, and check court conditions.', icon: <MessageSquare className="w-6 h-6" /> },
  ];



  return (
    <div className="min-h-screen bg-[#030303] text-zinc-100 overflow-hidden font-sans selection:bg-gold-500/30">
      {/* Dynamic Hero Section */}
      <section ref={targetRef} className="relative min-h-[100vh] flex items-center justify-center overflow-hidden pt-20">
        <motion.div
          className="absolute inset-0 z-0 bg-cover bg-center"
          style={{
            y: yBg,
            opacity: opacityBg,
            backgroundImage: `url('https://images.unsplash.com/photo-1519861531473-9200262188bf?q=80&w=2071&auto=format&fit=crop')`
          }}
        />
        <div className="absolute inset-0 z-0 bg-gradient-to-b from-[#030303]/90 via-[#030303]/70 to-[#030303]" />

        <div className="relative z-10 max-w-6xl mx-auto px-6 grid lg:grid-cols-2 gap-12 items-center">
          <motion.div
            initial="hidden"
            animate="visible"
            variants={STAGGER}
            className="flex flex-col gap-6"
          >
            <motion.div variants={FADE_UP} className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full bg-gold-400/10 border border-gold-400/20 backdrop-blur-md w-fit">
              <span className="relative flex h-2 w-2">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-gold-400 opacity-75"></span>
                <span className="relative inline-flex rounded-full h-2 w-2 bg-gold-500"></span>
              </span>
              <span className="text-sm font-medium text-gold-200 tracking-wide">Purdue CoRec Pickup</span>
            </motion.div>

            <motion.h1 variants={FADE_UP} className="text-6xl md:text-[7rem] font-black tracking-tighter leading-[0.9] text-transparent bg-clip-text bg-gradient-to-r from-gold-400 via-gold-200 to-gold-600 drop-shadow-[0_0_15px_rgba(207,185,145,0.3)] pb-2 flex flex-col md:flex-row items-start md:items-center gap-0 md:gap-4">
              <span className="text-6xl md:text-[6rem]">🏀</span> BOILER PICKUP
            </motion.h1>
            <motion.h2 variants={FADE_UP} className="text-3xl md:text-5xl font-black tracking-tight text-white mt-1">
              RULE THE HARDWOOD.
            </motion.h2>

            <motion.p variants={FADE_UP} className="text-lg md:text-xl text-zinc-400 max-w-lg leading-relaxed font-light">
              Elevate your game. Elite skill-based matchmaking, precise metric tracking, and pure competition.
              Built for the players who want more than just a run.
            </motion.p>

            <motion.div variants={FADE_UP} className="flex flex-col sm:flex-row gap-4 mt-4">
              <Link href="/register" className="group relative inline-flex items-center justify-center px-8 py-4 text-sm font-bold text-black bg-gold-500 rounded-xl overflow-hidden transition-all hover:scale-[1.02] shadow-[0_0_40px_-10px_rgba(207,185,145,0.4)]">
                <span className="absolute w-0 h-0 transition-all duration-500 ease-out bg-white rounded-full group-hover:w-56 group-hover:h-56 opacity-10"></span>
                <span>Get on the Court</span>
                <ArrowRight className="ml-2 w-4 h-4 group-hover:translate-x-1 transition-transform" />
              </Link>
              <Link href="/login" className="inline-flex items-center justify-center px-8 py-4 text-sm font-medium text-white border border-white/10 rounded-xl bg-white/5 backdrop-blur-md hover:bg-white/10 transition-colors">
                Sign In
              </Link>
            </motion.div>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, scale: 0.9, rotate: -5 }}
            animate={{ opacity: 1, scale: 1, rotate: 0 }}
            transition={{ duration: 1, ease: "easeOut", delay: 0.2 }}
            className="hidden lg:block relative"
          >
            <div className="absolute inset-0 bg-gold-500/20 blur-[100px] rounded-full" />
            <div className="relative bg-[#050505] p-6 rounded-[2rem] border border-white/10 backdrop-blur-xl shadow-2xl skew-y-[-2deg] transform-gpu">
              <div className="w-[450px] h-[300px] mb-8 relative z-10">
                <SkillRatingChart data={MOCK_CHART_DATA} />
              </div>
              <div className="absolute bottom-6 left-6 -right-6 flex justify-between px-6 py-4 bg-[#0a0a0a]/80 backdrop-blur-lg rounded-2xl border border-white/10 shadow-2xl">
                <div>
                  <div className="text-zinc-400 text-xs font-semibold uppercase tracking-wider">Win Probability</div>
                  <div className="text-white text-2xl font-black mt-1 flex items-center">
                    68.2%
                    <span className="text-emerald-400 text-sm ml-2 flex items-center bg-emerald-400/10 px-2 py-0.5 rounded border border-emerald-400/20">Favored</span>
                  </div>
                </div>
                <div className="text-right">
                  <div className="text-zinc-400 text-xs font-semibold uppercase tracking-wider">AI Skill Rating</div>
                  <div className="text-gold-400 text-2xl font-black mt-1">7.4 <span className="text-zinc-500 text-sm">/ 10</span></div>
                </div>
              </div>
            </div>
          </motion.div>
        </div>
      </section>

      {/* Feature Grid */}
      <section className="py-32 relative">
        <div className="absolute top-0 inset-x-0 h-px bg-gradient-to-r from-transparent via-white/10 to-transparent" />
        <div className="max-w-6xl mx-auto px-6">
          <motion.div
            initial="hidden"
            whileInView="visible"
            viewport={{ once: true, margin: "-100px" }}
            variants={STAGGER}
            className="mb-20"
          >
            <motion.h2 variants={FADE_UP} className="text-4xl md:text-5xl font-bold mb-4 tracking-tight">The Future of Pickup.</motion.h2>
            <motion.p variants={FADE_UP} className="text-zinc-400 max-w-2xl text-lg font-light">Eliminate the uneven squads. Our ML pipeline analyzes vast stat histories to organize the most competitive games possible.</motion.p>
          </motion.div>

          <motion.div
            initial="hidden"
            whileInView="visible"
            viewport={{ once: true, margin: "-100px" }}
            variants={STAGGER}
            className="grid md:grid-cols-2 lg:grid-cols-4 gap-6"
          >
            {features.map((f, i) => (
              <motion.div key={i} variants={FADE_UP} className="group p-8 rounded-3xl bg-zinc-900/30 border border-white/5 hover:bg-zinc-900/50 hover:border-gold-500/30 transition-all duration-500 relative overflow-hidden">
                <div className="absolute -inset-px bg-gradient-to-br from-gold-500/20 to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-500 rounded-3xl -z-10" />
                <div className="w-12 h-12 rounded-2xl bg-gold-400/10 text-gold-400 flex items-center justify-center mb-6 group-hover:scale-110 transition-transform duration-500 shadow-inner border border-gold-400/20">
                  {f.icon}
                </div>
                <h3 className="text-xl font-bold mb-3 text-white group-hover:text-gold-100 transition-colors">{f.title}</h3>
                <p className="text-sm text-zinc-400 leading-relaxed font-light">{f.desc}</p>
              </motion.div>
            ))}
          </motion.div>
        </div>
      </section>

      {/* Trajectory / Graph Section */}
      <section className="py-24 bg-zinc-950 relative overflow-hidden">
        <div className="max-w-6xl mx-auto px-6 grid md:grid-cols-2 gap-16 items-center relative z-10">
          <motion.div
            initial={{ opacity: 0, x: -40 }}
            whileInView={{ opacity: 1, x: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.8 }}
          >
            <h2 className="text-4xl font-bold mb-6 tracking-tight">Prove your worth. <br /><span className="text-zinc-500 text-3xl font-medium tracking-normal">Watch your stock rise.</span></h2>
            <p className="text-zinc-400 mb-8 font-light leading-relaxed">
              Start at baseline and forge your legacy. The dynamic Glicko-2 rating system updates precisely after every game based on the strength of your opponents and your on-court efficiency.
            </p>
            <ul className="space-y-4">
              {[
                { label: 'Defeat tough opponents to climb faster', icon: <Star className="w-5 h-5 text-gold-500" /> },
                { label: 'High individual efficiency boosts your rating', icon: <Activity className="w-5 h-5 text-gold-500" /> },
                { label: 'Compete in 1v1s for raw ranking power', icon: <Users className="w-5 h-5 text-gold-500" /> }
              ].map((item, i) => (
                <li key={i} className="flex items-center gap-4 text-zinc-300">
                  <div className="p-1.5 rounded-lg bg-white/5 border border-white/10">{item.icon}</div>
                  <span className="font-medium text-sm">{item.label}</span>
                </li>
              ))}
            </ul>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            whileInView={{ opacity: 1, scale: 1 }}
            viewport={{ once: true }}
            transition={{ duration: 0.8, delay: 0.2 }}
            className="grid grid-cols-2 gap-4 relative z-10"
          >
            {[
              { label: 'Team Record', value: '4W-1L', sub: '80% Win Rate', icon: <Users className="w-5 h-5 text-zinc-400" /> },
              { label: '1v1 Record', value: '7W-2L', sub: '77% Win Rate', icon: <Target className="w-5 h-5 text-orange-400" /> },
              { label: 'Skill Certainty', value: '92%', sub: 'Rating Consistency', icon: <Activity className="w-5 h-5 text-blue-400" />, bar: 0.92 },
              { label: 'Player Rating', value: '7.4', sub: 'High Confidence', icon: <Trophy className="w-5 h-5 text-gold-400" /> }
            ].map((s) => (
              <div key={s.label} className="bg-[#050505] border border-white/5 hover:border-white/10 p-6 rounded-3xl shadow-xl transition-all duration-300">
                <div className="flex justify-between items-start mb-4">
                  <div className="p-2 bg-white/5 rounded-xl border border-white/5">
                    {s.icon}
                  </div>
                </div>
                <div className="text-2xl font-black text-white tracking-tight mb-1">{s.value}</div>
                <div className="text-sm text-zinc-500 font-medium">{s.label}</div>
                <div className="text-xs text-zinc-600 mt-1">{s.sub}</div>
                {s.bar != null && (
                  <div className="mt-3 h-1.5 rounded-full bg-zinc-800 overflow-hidden">
                    <div
                      className="h-full rounded-full bg-gradient-to-r from-zinc-500 to-white transition-all duration-1000 ease-out"
                      style={{ width: `${s.bar * 100}%` }}
                    />
                  </div>
                )}
              </div>
            ))}
          </motion.div>
        </div>
      </section >

      {/* CTA Footer */}
      < section className="py-24 px-6 relative" >
        <motion.div
          initial={{ opacity: 0, y: 40 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.8 }}
          className="max-w-4xl mx-auto bg-gradient-to-br from-gold-500/10 to-transparent border border-gold-500/20 rounded-[2.5rem] p-12 md:p-20 text-center relative overflow-hidden"
        >
          <div className="absolute top-0 left-1/2 -translate-x-1/2 w-1/2 h-px bg-gradient-to-r from-transparent via-gold-400 to-transparent" />
          <h2 className="text-4xl md:text-5xl font-black mb-6 text-white tracking-tight">Step onto the court.</h2>
          <p className="text-xl text-zinc-400 mb-10 max-w-xl mx-auto font-light">
            Join the Purdue pickup basketball community where every shot, rebound, and win builds your legacy.
          </p>
          <Link href="/register" className="inline-flex items-center justify-center px-10 py-5 text-base font-bold text-black bg-gold-400 hover:bg-gold-300 rounded-2xl transition-all hover:scale-105 hover:shadow-[0_0_50px_-10px_rgba(207,185,145,0.5)]">
            Create Free Account
          </Link>
        </motion.div>
      </section >

      {/* Footer */}
      < footer className="py-8 px-6 border-t border-white/5 bg-[#030303]" >
        <div className="max-w-6xl mx-auto flex justify-between items-center text-sm font-medium text-zinc-600">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-gold-500/10 flex items-center justify-center text-xl">🏀</div>
            Boiler Pickup
          </div>
          <div>Purdue University • CoRec</div>
        </div>
      </footer >
    </div >
  );
}
