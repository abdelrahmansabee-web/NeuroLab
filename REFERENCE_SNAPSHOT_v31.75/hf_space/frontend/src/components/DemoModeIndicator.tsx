import { AlertTriangle } from 'lucide-react';

interface DemoModeIndicatorProps {
  isDemo: boolean;
  backendUrl: string;
}

export function DemoModeIndicator({ isDemo, backendUrl }: DemoModeIndicatorProps) {
  if (!isDemo) return null;

  return (
    <div className="fixed bottom-4 right-4 z-40">
      <div className="glass-card rounded-xl px-4 py-3 border border-amber-500/30 max-w-xs">
        <div className="flex items-center gap-2 mb-1">
          <AlertTriangle size={14} className="text-amber-400" />
          <span className="text-xs font-semibold text-amber-400">Demo Mode</span>
        </div>
        <p className="text-xs text-slate-400">
          Backend at <code className="text-amber-300">{backendUrl}</code> is not reachable.
          Showing mock data for preview.
        </p>
      </div>
    </div>
  );
}
