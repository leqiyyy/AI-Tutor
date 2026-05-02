import type { DashboardTone } from '@/types/dashboard';

const toneGradientMap: Record<DashboardTone, string> = {
  blue: 'bg-gradient-to-br from-blue-500 to-cyan-500',
  green: 'bg-gradient-to-br from-emerald-500 to-lime-500',
  purple: 'bg-gradient-to-br from-violet-500 to-fuchsia-500',
  orange: 'bg-gradient-to-br from-orange-500 to-amber-400',
  teal: 'bg-gradient-to-br from-teal-500 to-sky-500',
  red: 'bg-gradient-to-br from-rose-500 to-orange-500',
  amber: 'bg-gradient-to-br from-amber-500 to-yellow-400',
  pink: 'bg-gradient-to-br from-pink-500 to-rose-400',
};

const fallbackTones: DashboardTone[] = ['teal', 'blue', 'purple', 'green', 'orange', 'pink'];

export function getNameInitial(name?: string | null, fallback = '用') {
  const compactName = (name || '').replace(/\s+/g, '').trim();
  const initial = Array.from(compactName)[0] || fallback;
  return /[a-z]/i.test(initial) ? initial.toUpperCase() : initial;
}

export function getCourseCoverGradient(tone?: DashboardTone | string, seed = '') {
  if (tone && tone in toneGradientMap) {
    return toneGradientMap[tone as DashboardTone];
  }
  const codePoints = Array.from(seed).reduce((sum, ch) => sum + ch.charCodeAt(0), 0);
  return toneGradientMap[fallbackTones[codePoints % fallbackTones.length]];
}

export function formatLocalDateTime(value?: string | Date | null, fallback = '-') {
  if (!value) return fallback;
  const date = value instanceof Date ? value : new Date(value);
  if (Number.isNaN(date.getTime())) return typeof value === 'string' ? value : fallback;
  return new Intl.DateTimeFormat('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  }).format(date);
}

export function formatTodayCn(value = new Date()) {
  const weekday = new Intl.DateTimeFormat('zh-CN', { weekday: 'short' }).format(value);
  return `${value.getFullYear()}年${value.getMonth() + 1}月${value.getDate()}日 ${weekday}`;
}
