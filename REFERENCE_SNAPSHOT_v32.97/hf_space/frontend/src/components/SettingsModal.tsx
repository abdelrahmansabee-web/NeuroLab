import { AnimatePresence, motion } from 'framer-motion';
import { X, Server, Sliders } from 'lucide-react';
import { SettingsConfig } from '../types';

interface SettingsModalProps {
  isOpen: boolean;
  onClose: () => void;
  settings: SettingsConfig;
  onSettingsChange: (settings: SettingsConfig) => void;
}

export function SettingsModal({ isOpen, onClose, settings, onSettingsChange }: SettingsModalProps) {
  const handleChange = (key: keyof SettingsConfig, value: string | number) => {
    onSettingsChange({ ...settings, [key]: value });
  };

  return (
    <AnimatePresence>
      {isOpen && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm"
          onClick={onClose}
        >
          <motion.div
            initial={{ scale: 0.9, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            exit={{ scale: 0.9, opacity: 0 }}
            className="glass-card rounded-2xl w-full max-w-lg mx-4 max-h-[80vh] overflow-y-auto"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between px-6 py-4 border-b border-white/10">
              <h2 className="text-lg font-semibold text-white flex items-center gap-2">
                <Sliders size={20} className="text-sky-400" />
                Settings
              </h2>
              <button onClick={onClose} className="p-1 rounded-lg hover:bg-white/10 text-slate-400">
                <X size={20} />
              </button>
            </div>

            <div className="p-6 space-y-6">
              {/* Backend URL */}
              <div>
                <label className="flex items-center gap-2 text-sm font-medium text-slate-300 mb-2">
                  <Server size={14} className="text-sky-400" />
                  Backend URL
                </label>
                <input
                  type="text"
                  value={settings.backendUrl}
                  onChange={(e) => handleChange('backendUrl', e.target.value)}
                  className="w-full bg-slate-800 border border-slate-700 rounded-lg px-4 py-2 text-white text-sm focus:border-sky-500 focus:ring-1 focus:ring-sky-500 outline-none"
                />
              </div>

              {/* Signal Processing */}
              <div>
                <h3 className="text-sm font-semibold text-slate-300 mb-3">Signal Processing</h3>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="text-xs text-slate-400 mb-1 block">Cutoff Frequency (Hz)</label>
                    <input
                      type="number"
                      step="0.5"
                      min="1"
                      max="15"
                      value={settings.cutoffFrequency}
                      onChange={(e) => handleChange('cutoffFrequency', parseFloat(e.target.value))}
                      className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-white text-sm outline-none focus:border-sky-500"
                    />
                  </div>
                  <div>
                    <label className="text-xs text-slate-400 mb-1 block">Filter Order</label>
                    <input
                      type="number"
                      min="2"
                      max="8"
                      value={settings.filterOrder}
                      onChange={(e) => handleChange('filterOrder', parseInt(e.target.value))}
                      className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-white text-sm outline-none focus:border-sky-500"
                    />
                  </div>
                </div>
              </div>

              {/* MediaPipe */}
              <div>
                <h3 className="text-sm font-semibold text-slate-300 mb-3">MediaPipe Pose</h3>
                <div className="grid grid-cols-3 gap-4">
                  <div>
                    <label className="text-xs text-slate-400 mb-1 block">Model Complexity</label>
                    <select
                      value={settings.modelComplexity}
                      onChange={(e) => handleChange('modelComplexity', parseInt(e.target.value))}
                      className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-white text-sm outline-none focus:border-sky-500"
                    >
                      <option value={0}>Lite (0)</option>
                      <option value={1}>Full (1)</option>
                      <option value={2}>Heavy (2)</option>
                    </select>
                  </div>
                  <div>
                    <label className="text-xs text-slate-400 mb-1 block">Detection Conf.</label>
                    <input
                      type="number"
                      step="0.1"
                      min="0.1"
                      max="1.0"
                      value={settings.minDetectionConfidence}
                      onChange={(e) => handleChange('minDetectionConfidence', parseFloat(e.target.value))}
                      className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-white text-sm outline-none focus:border-sky-500"
                    />
                  </div>
                  <div>
                    <label className="text-xs text-slate-400 mb-1 block">Tracking Conf.</label>
                    <input
                      type="number"
                      step="0.1"
                      min="0.1"
                      max="1.0"
                      value={settings.minTrackingConfidence}
                      onChange={(e) => handleChange('minTrackingConfidence', parseFloat(e.target.value))}
                      className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-white text-sm outline-none focus:border-sky-500"
                    />
                  </div>
                </div>
              </div>
            </div>

            <div className="px-6 py-4 border-t border-white/10 flex justify-end">
              <button
                onClick={onClose}
                className="px-4 py-2 bg-sky-500 hover:bg-sky-600 text-white rounded-lg text-sm font-medium transition-colors"
              >
                Done
              </button>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
