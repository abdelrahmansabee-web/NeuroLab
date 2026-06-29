import { AnimatePresence, motion } from 'framer-motion';
import { Loader2 } from 'lucide-react';

interface ProcessingStatusProps {
  isProcessing: boolean;
  currentStep: number;
  totalSteps: number;
  currentPhase: string;
}

const stepLabels = [
  'Initializing...',
  'Uploading video...',
  'Extracting pose landmarks...',
  'Computing kinematics...',
  'Building results...',
  'Finalizing...',
];

export function ProcessingStatus({ isProcessing, currentStep, totalSteps, currentPhase }: ProcessingStatusProps) {
  return (
    <AnimatePresence>
      {isProcessing && (
        <motion.div
          initial={{ opacity: 0, y: 50 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: 50 }}
          className="fixed bottom-6 left-1/2 -translate-x-1/2 z-50"
        >
          <div className="glass-card rounded-2xl px-6 py-4 shadow-2xl border border-sky-500/30 flex items-center gap-4 min-w-[320px]">
            <Loader2 className="animate-spin text-sky-400" size={24} />
            <div className="flex-1">
              <div className="flex items-center justify-between mb-1">
                <span className="text-sm font-medium text-white">
                  Processing {currentPhase}
                </span>
                <span className="text-xs text-slate-400">
                  Step {Math.min(currentStep + 1, totalSteps)}/{totalSteps}
                </span>
              </div>
              <p className="text-xs text-slate-400 mb-2">
                {stepLabels[currentStep] || 'Processing...'}
              </p>
              <div className="w-full bg-slate-700 rounded-full h-1.5">
                <motion.div
                  className="bg-gradient-to-r from-sky-500 to-blue-500 h-1.5 rounded-full"
                  initial={{ width: '0%' }}
                  animate={{ width: `${((currentStep + 1) / totalSteps) * 100}%` }}
                  transition={{ duration: 0.3 }}
                />
              </div>
            </div>
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
