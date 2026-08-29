import { Download, FileText, Film, Package } from 'lucide-react';
import { VideoPhase, ProcessingResult } from '../types';

interface DownloadPanelProps {
  results: {
    pre: ProcessingResult | null;
    post: ProcessingResult | null;
  };
  onDownload: (phase: VideoPhase, type: 'csv' | 'trc' | 'video' | 'all') => void;
}

const phaseConfig: Record<VideoPhase, { label: string; color: string }> = {
  pre: { label: 'Pre-Treatment', color: 'amber' },
  post: { label: 'Post-Treatment', color: 'emerald' },
};

export function DownloadPanel({ results, onDownload }: DownloadPanelProps) {
  const phases: VideoPhase[] = ['pre', 'post'];
  const availablePhases = phases.filter((p) => results[p] !== null);

  if (availablePhases.length === 0) return null;

  return (
    <div className="grid md:grid-cols-2 gap-4">
      {availablePhases.map((phase) => {
        const config = phaseConfig[phase];
        const result = results[phase]!;
        const hasVideo = !!result.validationVideoUrl;

        return (
          <div key={phase} className="glass-card rounded-xl p-4">
            <h3 className={`text-sm font-semibold text-${config.color}-400 mb-3`}>
              {config.label}
            </h3>

            <div className="space-y-2">
              <button
                onClick={() => onDownload(phase, 'csv')}
                className="w-full flex items-center gap-2 px-3 py-2 rounded-lg bg-white/5 hover:bg-white/10 text-slate-300 text-sm transition-colors"
              >
                <FileText size={14} className="text-emerald-400" />
                <span>CSV Data</span>
                <Download size={12} className="ml-auto text-slate-500" />
              </button>

              <button
                onClick={() => onDownload(phase, 'trc')}
                className="w-full flex items-center gap-2 px-3 py-2 rounded-lg bg-white/5 hover:bg-white/10 text-slate-300 text-sm transition-colors"
              >
                <FileText size={14} className="text-sky-400" />
                <span>TRC Motion</span>
                <Download size={12} className="ml-auto text-slate-500" />
              </button>

              {hasVideo && (
                <button
                  onClick={() => onDownload(phase, 'video')}
                  className="w-full flex items-center gap-2 px-3 py-2 rounded-lg bg-white/5 hover:bg-white/10 text-slate-300 text-sm transition-colors"
                >
                  <Film size={14} className="text-purple-400" />
                  <span>Validation Video</span>
                  <Download size={12} className="ml-auto text-slate-500" />
                </button>
              )}

              <button
                onClick={() => onDownload(phase, 'all')}
                className="w-full flex items-center gap-2 px-3 py-2 rounded-lg bg-sky-500/10 hover:bg-sky-500/20 text-sky-300 text-sm font-medium transition-colors mt-2"
              >
                <Package size={14} />
                <span>Download All</span>
                <Download size={12} className="ml-auto" />
              </button>
            </div>
          </div>
        );
      })}
    </div>
  );
}
