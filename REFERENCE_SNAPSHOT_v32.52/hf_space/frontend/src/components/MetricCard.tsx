import { LucideIcon } from 'lucide-react';

interface MetricCardProps {
  title: string;
  value: number;
  unit: string;
  icon: LucideIcon;
  color: 'amber' | 'sky' | 'purple' | 'emerald' | 'rose';
}

const colorMap = {
  amber: {
    bg: 'bg-amber-500/10',
    border: 'border-amber-500/20',
    icon: 'text-amber-400',
    value: 'text-amber-300',
  },
  sky: {
    bg: 'bg-sky-500/10',
    border: 'border-sky-500/20',
    icon: 'text-sky-400',
    value: 'text-sky-300',
  },
  purple: {
    bg: 'bg-purple-500/10',
    border: 'border-purple-500/20',
    icon: 'text-purple-400',
    value: 'text-purple-300',
  },
  emerald: {
    bg: 'bg-emerald-500/10',
    border: 'border-emerald-500/20',
    icon: 'text-emerald-400',
    value: 'text-emerald-300',
  },
  rose: {
    bg: 'bg-rose-500/10',
    border: 'border-rose-500/20',
    icon: 'text-rose-400',
    value: 'text-rose-300',
  },
};

export function MetricCard({ title, value, unit, icon: Icon, color }: MetricCardProps) {
  const c = colorMap[color];

  return (
    <div className={`${c.bg} border ${c.border} rounded-xl p-4 text-center`}>
      <Icon className={`${c.icon} mx-auto mb-2`} size={20} />
      <div className={`text-2xl font-bold ${c.value} font-mono`}>
        {typeof value === 'number' ? (
          Number.isInteger(value) ? value : value.toFixed(2)
        ) : value}
      </div>
      <div className="text-xs text-slate-500 mt-1">{unit}</div>
      <div className="text-xs text-slate-400 mt-1 font-medium">{title}</div>
    </div>
  );
}
