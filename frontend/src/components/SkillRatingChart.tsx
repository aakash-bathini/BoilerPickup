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
          label: 'Skill Rating',
          data: data.map(d => ({ x: new Date(d.timestamp).getTime(), y: d.rating })),
          borderColor: '#CFB991',
          backgroundColor: 'rgba(207, 185, 145, 0.1)',
          fill: true,
          tension: 0.3,
          pointBackgroundColor: '#CFB991',
          pointBorderColor: '#0A0A0A',
          pointBorderWidth: 1,
          pointRadius: 4,
          pointHoverRadius: 6,
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
          backgroundColor: 'rgba(10, 10, 10, 0.95)',
          titleColor: '#CFB991',
          bodyColor: '#e5e7eb',
          borderColor: 'rgba(207, 185, 145, 0.3)',
          borderWidth: 1,
          padding: 12,
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
            label: (ctx: { raw: { y: number } }) => `Rating: ${ctx.raw.y.toFixed(1)}`,
          },
        },
      },
      scales: {
        x: {
          type: 'time' as const,
          time: {
            unit: 'day' as const,
            displayFormats: {
              millisecond: 'HH:mm',
              second: 'HH:mm',
              minute: 'HH:mm',
              hour: 'MMM d, HH:mm',
              day: 'MMM d',
              week: 'MMM d',
              month: 'MMM yyyy',
              year: 'yyyy',
            },
          },
          grid: { color: 'rgba(207, 185, 145, 0.08)' },
          ticks: {
            color: '#6b7280',
            maxRotation: 45,
            minRotation: 0,
          },
        },
        y: {
          min: 0,
          max: 10,
          grid: { color: 'rgba(207, 185, 145, 0.08)' },
          ticks: {
            stepSize: 1,
            color: '#6b7280',
            callback: (value: number) => (Number.isInteger(value) ? value : ''),
          },
        },
      },
    }),
    [],
  );

  if (!chartData || data.length === 0) return null;

  return (
    <div className="mt-2">
      <div className="text-[10px] text-gray-500 mb-1">Rating (1–10) over time</div>
      <div className="h-56 w-full min-h-[200px]">
        <Line data={chartData} options={options} />
      </div>
    </div>
  );
}
