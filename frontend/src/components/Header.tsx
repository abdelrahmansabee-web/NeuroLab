import { Settings, HelpCircle, Brain } from 'lucide-react';

interface HeaderProps {
  onSettingsClick: () => void;
  onHelpClick: () => void;
}

export function Header({ onSettingsClick, onHelpClick }: HeaderProps) {
  return (
    <header className="sticky top-0 z-50 glass-card border-b border-white/10">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-sky-500 to-blue-600 flex items-center justify-center">
            <Brain className="text-white" size={22} />
          </div>
          <div>
            <h1 className="text-xl font-bold text-white tracking-tight">
              KinematicsAI Lab
            </h1>
            <p className="text-xs text-slate-400">
              Stroke Rehabilitation Kinematic Analysis
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={onHelpClick}
            className="p-2 rounded-lg text-slate-400 hover:text-white hover:bg-white/10 transition-colors"
            title="Help"
          >
            <HelpCircle size={20} />
          </button>
          <button
            onClick={onSettingsClick}
            className="p-2 rounded-lg text-slate-400 hover:text-white hover:bg-white/10 transition-colors"
            title="Settings"
          >
            <Settings size={20} />
          </button>
        </div>
      </div>
    </header>
  );
}
