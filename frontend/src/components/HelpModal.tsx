import { AnimatePresence, motion } from 'framer-motion';
import { X, HelpCircle } from 'lucide-react';

interface HelpModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export function HelpModal({ isOpen, onClose }: HelpModalProps) {
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
            className="glass-card rounded-2xl w-full max-w-2xl mx-4 max-h-[80vh] overflow-y-auto"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between px-6 py-4 border-b border-white/10">
              <h2 className="text-lg font-semibold text-white flex items-center gap-2">
                <HelpCircle size={20} className="text-sky-400" />
                How to Use
              </h2>
              <button onClick={onClose} className="p-1 rounded-lg hover:bg-white/10 text-slate-400">
                <X size={20} />
              </button>
            </div>

            <div className="p-6 space-y-6 text-slate-300 text-sm">
              <section>
                <h3 className="text-white font-semibold mb-2">1. Setup Backend</h3>
                <p className="text-slate-400">
                  Install Python dependencies and run the FastAPI backend:
                </p>
                <pre className="bg-slate-800 rounded-lg p-3 mt-2 text-xs text-slate-300 overflow-x-auto">
{`cd backend
pip install -r requirements.txt
python main.py`}
                </pre>
              </section>

              <section>
                <h3 className="text-white font-semibold mb-2">2. Select Affected Side</h3>
                <p className="text-slate-400">
                  Choose the patient's affected side (Right or Left) before uploading videos.
                </p>
              </section>

              <section>
                <h3 className="text-white font-semibold mb-2">3. Upload Videos</h3>
                <p className="text-slate-400">
                  Upload up to 3 videos for different treatment phases: Pre-Treatment, During-Treatment, and Post-Treatment.
                  Videos should capture the upper limb reaching-wiping task from a frontal view.
                </p>
              </section>

              <section>
                <h3 className="text-white font-semibold mb-2">4. Process & Analyze</h3>
                <p className="text-slate-400">
                  Click "Process Videos" to extract pose landmarks and compute 14 biomechanical variables including:
                </p>
                <ul className="list-disc list-inside mt-2 space-y-1 text-slate-400">
                  <li><strong>Temporal:</strong> Onset time, reaching/wiping/total duration</li>
                  <li><strong>Spatial:</strong> Path lengths (reaching & wiping)</li>
                  <li><strong>Compensation:</strong> Trunk displacement, rotation, shoulder hiking</li>
                  <li><strong>Joint:</strong> Elbow extension range</li>
                  <li><strong>Smoothness:</strong> SPARC & Number of Velocity Peaks (NVP)</li>
                </ul>
              </section>

              <section>
                <h3 className="text-white font-semibold mb-2">5. Interpret Δ Change</h3>
                <p className="text-slate-400">
                  The delta column shows changes between Pre and Post treatment:
                </p>
                <ul className="list-disc list-inside mt-2 space-y-1">
                  <li><span className="text-emerald-400">Green ↑/↓</span> = Clinical improvement</li>
                  <li><span className="text-red-400">Red ↑/↓</span> = Clinical deterioration</li>
                </ul>
                <p className="text-slate-500 mt-2 text-xs">
                  Each variable has its own improvement direction (e.g., lower time = better, higher elbow range = better,
                  SPARC closer to 0 = smoother).
                </p>
              </section>

              <section>
                <h3 className="text-white font-semibold mb-2">6. Download Results</h3>
                <p className="text-slate-400">
                  Download CSV data, TRC motion files (OpenSim compatible), and validation videos.
                </p>
              </section>
            </div>

            <div className="px-6 py-4 border-t border-white/10 flex justify-end">
              <button
                onClick={onClose}
                className="px-4 py-2 bg-sky-500 hover:bg-sky-600 text-white rounded-lg text-sm font-medium transition-colors"
              >
                Got it
              </button>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
