'use client';

import { useMemo } from 'react';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  TimeScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  Filler,
} from 'chart.js';
import { Line } from 'react-chartjs-2';
import 'chartjs-adapter-date-fns';

ChartJS.register(
  CategoryScale,
  LinearScale,
  TimeScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  Filler,
);

export interface SkillHistoryEntry {
  timestamp: string;
  rating: number;
}

export function SkillRatingChart({ data }: { data: SkillHistoryEntry[] }) {
  const chartData = useMemo(() => {
    if (data.length === 0) return null;
    return {
      datasets: [
        {
          label: 'AI Skill Rating',
          data: data.map(d => ({ x: new Date(d.timestamp).getTime(), y: d.rating })),
          borderColor: '#CFB991',
          borderWidth: 3,
          backgroundColor: (context: any) => {
            const ctx = context.chart.ctx;
            const gradient = ctx.createLinearGradient(0, 0, 0, context.chart.height || 200);
            gradient.addColorStop(0, 'rgba(207, 185, 145, 0.4)'); // Gold start
            gradient.addColorStop(1, 'rgba(207, 185, 145, 0.0)'); // Fade to transparent
            return gradient;
          },
          fill: true,
          tension: 0.4, // Smooth spline
          pointBackgroundColor: '#121212',
          pointBorderColor: '#CFB991',
          pointBorderWidth: 2,
          pointRadius: 3,
          pointHoverRadius: 6,
          pointHoverBackgroundColor: '#CFB991',
          pointHoverBorderColor: '#fff',
          pointHoverBorderWidth: 2,
        },
      ],
    };
  }, [data]);

  const options = useMemo(
    () => ({
      responsive: true,
      maintainAspectRatio: false,
      interaction: {
        mode: 'index' as const,
        intersect: false,
      },
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: 'rgba(5, 5, 5, 0.95)',
          titleColor: '#888',
          bodyColor: '#fff',
          bodyFont: { size: 14, weight: 'bold' as const },
          borderColor: 'rgba(207, 185, 145, 0.3)',
          borderWidth: 1,
          padding: 12,
          cornerRadius: 8,
          displayColors: false,
          callbacks: {
            title: (items: { raw: { x: number; y: number } }[]) => {
              if (items[0]?.raw?.x) {
                const d = new Date(items[0].raw.x);
                return d.toLocaleString(undefined, {
                  month: 'short',
                  day: 'numeric',
                  year: 'numeric',
                  hour: 'numeric',
                  minute: '2-digit',
                });
              }
              return '';
            },
            label: (ctx: { raw: { y: number } }) => `Rating: ${ctx.raw.y.toFixed(1)} OVR`,
          },
        },
      },
      scales: {
        x: {
          type: 'time' as const,
          time: {
            unit: 'day' as const,
            displayFormats: {
              day: 'MMM d',
              month: 'MMM yyyy',
            },
          },
          grid: {
            color: 'rgba(255, 255, 255, 0.03)',
            drawBorder: false,
          },
          ticks: {
            color: '#555',
            maxRotation: 0,
            autoSkip: true,
            maxTicksLimit: 6,
            font: { size: 11, family: 'monospace' },
          },
        },
        y: {
          min: 1, // Normalized 1-10 range mapping
          max: 10,
          grid: {
            color: (ctx: any) => {
              const val = ctx.tick.value;
              // Add visual subtle markers for theoretical tiers
              if (val === 8.5) return 'rgba(207, 185, 145, 0.2)'; // Hall of Fame Outline
              if (val === 6) return 'rgba(255, 255, 255, 0.1)';   // Silver / Gold divide
              return 'rgba(255, 255, 255, 0.02)';
            },
            drawBorder: false,
          },
          ticks: {
            stepSize: 1,
            color: (ctx: any) => {
              const val = ctx.tick.value;
              if (val >= 8.5) return '#CFB991'; // Gold
              if (val >= 6) return '#aaa';     // Silver
              return '#666';                   // Bronze
            },
            font: { size: 10, weight: 'bold' as const },
            callback: (value: number) => {
              if (value === 10) return 'HOF (10)';
              if (value === 8) return 'Elite (8)';
              if (value === 5) return 'Pro (5)';
              if (value === 2) return 'Rook (2)';
              return '';
            },
          },
        },
      },
    }),
    [],
  );

  if (!chartData || data.length === 0) return null;

  return (
    <div className="mt-4 relative bg-zinc-950/50 rounded-2xl p-4 border border-white/5 shadow-inner">
      <div className="absolute top-4 right-4 flex items-center gap-2 z-10">
        <div className="w-2 h-2 rounded-full bg-gold-500 animate-pulse"></div>
        <span className="text-[10px] uppercase font-bold text-gray-400 tracking-wider text-shadow-sm">Tracking</span>
      </div>
      <div className="text-[11px] font-bold text-gray-500 uppercase tracking-widest mb-4">Overall Rating (OVR) Progression</div>
      <div className="h-64 w-full min-h-[250px]">
        <Line data={chartData as any} options={options as any} />
      </div>
    </div>
  );
}
