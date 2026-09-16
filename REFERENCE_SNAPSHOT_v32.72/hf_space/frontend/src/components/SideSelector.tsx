import { AffectedSide } from '../types';

interface SideSelectorProps {
  selectedSide: AffectedSide;
  onSideChange: (side: AffectedSide) => void;
  disabled: boolean;
}

export function SideSelector({ selectedSide, onSideChange, disabled }: SideSelectorProps) {
  return (
    <div className="glass-card rounded-xl p-4 h-full flex flex-col justify-center">
      <h3 className="text-sm font-semibold text-slate-300 mb-3 text-center">Affected Side</h3>

      <div className="flex flex-col gap-3">
        {(['R', 'L'] as AffectedSide[]).map((side) => (
          <button
            key={side}
            onClick={() => !disabled && onSideChange(side)}
            disabled={disabled}
            className={`relative px-4 py-3 rounded-xl font-semibold text-sm transition-all duration-200 ${
              selectedSide === side
                ? 'bg-sky-500/20 text-sky-300 border-2 border-sky-500/50 shadow-lg shadow-sky-500/10'
                : 'bg-slate-700/30 text-slate-400 border-2 border-transparent hover:border-slate-600'
            } ${disabled ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'}`}
          >
            <div className="flex items-center gap-3">
              {/* Body icon */}
              <div className="relative w-8 h-12">
                <svg viewBox="0 0 32 48" className="w-full h-full">
                  {/* Head */}
                  <circle cx="16" cy="6" r="5" fill="none" stroke="currentColor" strokeWidth="1.5" />
                  {/* Body */}
                  <line x1="16" y1="11" x2="16" y2="30" stroke="currentColor" strokeWidth="1.5" />
                  {/* Left arm */}
                  <line
                    x1="16" y1="16" x2="4" y2="24"
                    stroke={side === 'L' ? '#f87171' : 'currentColor'}
                    strokeWidth={side === 'L' ? '2.5' : '1.5'}
                  />
                  {/* Right arm */}
                  <line
                    x1="16" y1="16" x2="28" y2="24"
                    stroke={side === 'R' ? '#f87171' : 'currentColor'}
                    strokeWidth={side === 'R' ? '2.5' : '1.5'}
                  />
                  {/* Legs */}
                  <line x1="16" y1="30" x2="8" y2="44" stroke="currentColor" strokeWidth="1.5" />
                  <line x1="16" y1="30" x2="24" y2="44" stroke="currentColor" strokeWidth="1.5" />
                </svg>
              </div>
              <div className="text-left">
                <div className="text-base font-bold">{side === 'R' ? 'Right' : 'Left'}</div>
                <div className="text-xs opacity-70">{side === 'R' ? 'الجانب الأيمن' : 'الجانب الأيسر'}</div>
              </div>
            </div>

            {selectedSide === side && (
              <div className="absolute top-1 right-2 w-2 h-2 rounded-full bg-sky-400 animate-pulse" />
            )}
          </button>
        ))}
      </div>
    </div>
  );
}
