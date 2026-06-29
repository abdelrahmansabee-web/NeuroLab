import { useCallback, useRef } from 'react';
import { Upload, X, Film, CheckCircle, AlertCircle, Loader2 } from 'lucide-react';
import { VideoPhase, VideoFile } from '../types';

interface VideoUploaderProps {
  phase: VideoPhase;
  videoFile: VideoFile;
  onFileSelect: (phase: VideoPhase, file: File) => void;
  onRemove: (phase: VideoPhase) => void;
  disabled: boolean;
}

const phaseLabels: Record<VideoPhase, { label: string; color: string }> = {
  pre: { label: 'Pre-Treatment', color: 'from-amber-500 to-orange-500' },
  post: { label: 'Post-Treatment', color: 'from-emerald-500 to-green-500' },
};

export function VideoUploader({ phase, videoFile, onFileSelect, onRemove, disabled }: VideoUploaderProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const config = phaseLabels[phase];

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      if (disabled) return;
      const file = e.dataTransfer.files[0];
      if (file && file.type.startsWith('video/')) {
        onFileSelect(phase, file);
      }
    },
    [disabled, onFileSelect, phase]
  );

  const handleChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0];
      if (file) {
        onFileSelect(phase, file);
      }
    },
    [onFileSelect, phase]
  );

  const statusIcon = () => {
    switch (videoFile.status) {
      case 'processing':
        return <Loader2 className="animate-spin text-sky-400" size={16} />;
      case 'completed':
        return <CheckCircle className="text-emerald-400" size={16} />;
      case 'error':
        return <AlertCircle className="text-red-400" size={16} />;
      default:
        return null;
    }
  };

  return (
    <div className="glass-card rounded-xl overflow-hidden">
      {/* Phase header */}
      <div className={`bg-gradient-to-r ${config.color} px-4 py-2 flex items-center justify-between`}>
        <span className="text-white font-semibold text-sm">{config.label}</span>
        {statusIcon()}
      </div>

      {/* Upload area */}
      <div className="p-4">
        {videoFile.file ? (
          <div className="space-y-3">
            {/* File info */}
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2 min-w-0">
                <Film size={14} className="text-slate-400 flex-shrink-0" />
                <span className="text-xs text-slate-300 truncate">{videoFile.file.name}</span>
              </div>
              <button
                onClick={() => onRemove(phase)}
                disabled={disabled}
                className="p-1 rounded hover:bg-red-500/20 text-slate-400 hover:text-red-400 transition-colors flex-shrink-0"
              >
                <X size={14} />
              </button>
            </div>

            {/* Progress bar */}
            {videoFile.status === 'processing' && (
              <div className="w-full bg-slate-700 rounded-full h-1.5">
                <div
                  className="bg-sky-500 h-1.5 rounded-full transition-all duration-300"
                  style={{ width: `${videoFile.progress}%` }}
                />
              </div>
            )}

            {/* Error message */}
            {videoFile.status === 'error' && videoFile.error && (
              <p className="text-xs text-red-400">{videoFile.error}</p>
            )}
          </div>
        ) : (
          <div
            onDrop={handleDrop}
            onDragOver={(e) => e.preventDefault()}
            onClick={() => !disabled && inputRef.current?.click()}
            className={`border-2 border-dashed border-slate-600 rounded-lg p-6 text-center cursor-pointer hover:border-sky-500/50 hover:bg-sky-500/5 transition-colors ${
              disabled ? 'opacity-50 cursor-not-allowed' : ''
            }`}
          >
            <Upload className="mx-auto text-slate-500 mb-2" size={24} />
            <p className="text-sm text-slate-400">
              Drop video or <span className="text-sky-400">browse</span>
            </p>
            <p className="text-xs text-slate-600 mt-1">.mp4, .mov, .avi</p>
          </div>
        )}
      </div>

      <input
        ref={inputRef}
        type="file"
        accept="video/*"
        onChange={handleChange}
        className="hidden"
      />
    </div>
  );
}
