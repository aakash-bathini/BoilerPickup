export function formatEST(dateStr: string): string {
  const date = new Date(dateStr);
  return date.toLocaleString('en-US', {
    timeZone: 'America/New_York',
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
    hour12: true,
  }) + ' EST';
}

export function formatESTShort(dateStr: string): string {
  const date = new Date(dateStr);
  return date.toLocaleString('en-US', {
    timeZone: 'America/New_York',
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
    hour12: true,
  });
}

export function formatESTTime(dateStr: string): string {
  const date = new Date(dateStr);
  return date.toLocaleString('en-US', {
    timeZone: 'America/New_York',
    hour: 'numeric',
    minute: '2-digit',
    hour12: true,
  });
}

export function timeAgo(dateStr: string): string {
  const now = new Date();
  const date = new Date(dateStr);
  const diff = Math.floor((now.getTime() - date.getTime()) / 1000);

  if (diff < 60) return 'just now';
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  return `${Math.floor(diff / 86400)}d ago`;
}

export function skillColor(rating: number): string {
  if (rating <= 3) return 'text-blue-400';
  if (rating <= 5) return 'text-emerald-400';
  if (rating <= 7) return 'text-gold-400';
  if (rating <= 9) return 'text-orange-400';
  return 'text-red-400';
}

export function skillBg(rating: number): string {
  if (rating <= 3) return 'bg-blue-500/15 border-blue-500/30';
  if (rating <= 5) return 'bg-emerald-500/15 border-emerald-500/30';
  if (rating <= 7) return 'bg-gold-500/15 border-gold-500/30';
  if (rating <= 9) return 'bg-orange-500/15 border-orange-500/30';
  return 'bg-red-500/15 border-red-500/30';
}

export function statusColor(status: string): string {
  switch (status) {
    case 'open': return 'bg-emerald-500/15 text-emerald-400 border-emerald-500/25';
    case 'full': return 'bg-amber-500/15 text-amber-400 border-amber-500/25';
    case 'in_progress': return 'bg-blue-500/15 text-blue-400 border-blue-500/25';
    case 'completed': return 'bg-gray-500/15 text-gray-400 border-gray-500/25';
    default: return 'bg-gray-500/15 text-gray-400 border-gray-500/25';
  }
}

export function positionLabel(pos: string | null): string {
  const map: Record<string, string> = { PG: 'Point Guard', SG: 'Shooting Guard', SF: 'Small Forward', PF: 'Power Forward', C: 'Center' };
  return pos ? map[pos] || pos : 'Any Position';
}
