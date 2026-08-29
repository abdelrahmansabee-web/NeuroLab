import { BiomechanicalVariable } from '../types';
import { TrendingDown, TrendingUp, Minus } from 'lucide-react';

interface ResultsTableProps {
  variables: BiomechanicalVariable[];
  hasPreResults: boolean;
  hasPostResults: boolean;
}

/**
 * Compute the delta change between pre and post values,
 * taking into account the clinical improvement direction.
 */
function computeDelta(variable: BiomechanicalVariable): {
  text: string;
  isImprovement: boolean | null;
} | null {
  const preVal = parseFloat(variable.pre);
  const postVal = parseFloat(variable.post);

  if (isNaN(preVal) || isNaN(postVal) || preVal === 0) return null;

  const rawChange = postVal - preVal;
  const percentChange = Math.abs(rawChange / preVal) * 100;

  let isImprovement: boolean | null = null;

  switch (variable.improvementDirection) {
    case 'lower':
    case 'lower_count':
      // Lower is better: improvement if post < pre
      isImprovement = postVal < preVal;
      break;
    case 'higher':
      // Higher is better: improvement if post > pre
      isImprovement = postVal > preVal;
      break;
    case 'closer_to_zero':
      // Closer to zero is better (SPARC is negative, closer to 0 = smoother)
      isImprovement = Math.abs(postVal) < Math.abs(preVal);
      break;
  }

  const arrow = rawChange > 0 ? '↑' : rawChange < 0 ? '↓' : '→';

  return {
    text: `${arrow} ${percentChange.toFixed(1)}%`,
    isImprovement,
  };
}

const categoryLabels: Record<string, { label: string; color: string }> = {
  temporal: { label: 'Temporal', color: 'text-amber-400' },
  spatial: { label: 'Spatial', color: 'text-sky-400' },
  compensation: { label: 'Pathological Compensation', color: 'text-rose-400' },
  joint: { label: 'Joint Kinematics', color: 'text-purple-400' },
  smoothness: { label: 'Smoothness', color: 'text-emerald-400' },
};

export function ResultsTable({ variables, hasPreResults, hasPostResults }: ResultsTableProps) {
  // Group variables by category
  const grouped = variables.reduce<Record<string, BiomechanicalVariable[]>>((acc, v) => {
    if (!acc[v.category]) acc[v.category] = [];
    acc[v.category].push(v);
    return acc;
  }, {});

  const showDelta = hasPreResults && hasPostResults;

  return (
    <div className="glass-card rounded-xl overflow-hidden">
      <div className="px-6 py-4 border-b border-white/10">
        <h2 className="text-lg font-semibold text-white">Kinematic Variables</h2>
        <p className="text-sm text-slate-400 mt-1">
          Biomechanical analysis results across treatment phases
        </p>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full">
          <thead>
            <tr className="border-b border-white/10">
              <th className="text-left px-6 py-3 text-xs font-medium text-slate-400 uppercase tracking-wider">
                Variable
              </th>
              <th className="text-center px-4 py-3 text-xs font-medium text-slate-400 uppercase tracking-wider">
                Unit
              </th>
              {hasPreResults && (
                <th className="text-center px-4 py-3 text-xs font-medium text-amber-400 uppercase tracking-wider">
                  Pre
                </th>
              )}
              {hasPostResults && (
                <th className="text-center px-4 py-3 text-xs font-medium text-emerald-400 uppercase tracking-wider">
                  Post
                </th>
              )}
              {showDelta && (
                <th className="text-center px-4 py-3 text-xs font-medium text-slate-400 uppercase tracking-wider">
                  Δ Change
                </th>
              )}
            </tr>
          </thead>
          <tbody>
            {Object.entries(grouped).map(([category, vars]) => {
              const catConfig = categoryLabels[category] || { label: category, color: 'text-slate-400' };
              return (
                <tbody key={category}>
                  {/* Category header row */}
                  <tr className="bg-white/5">
                    <td
                      colSpan={10}
                      className={`px-6 py-2 text-xs font-bold uppercase tracking-wider ${catConfig.color}`}
                    >
                      {catConfig.label}
                    </td>
                  </tr>
                  {vars.map((v) => {
                    const delta = showDelta ? computeDelta(v) : null;
                    return (
                      <tr key={v.id} className="border-b border-white/5 hover:bg-white/5 transition-colors">
                        <td className="px-6 py-3">
                          <div className="text-sm text-white font-medium">{v.name}</div>
                          <div className="text-xs text-slate-500">{v.description}</div>
                        </td>
                        <td className="text-center px-4 py-3 text-xs text-slate-500">{v.unit}</td>
                        {hasPreResults && (
                          <td className="text-center px-4 py-3 text-sm text-slate-200 font-mono">
                            {v.pre || '—'}
                          </td>
                        )}
                        {hasPostResults && (
                          <td className="text-center px-4 py-3 text-sm text-slate-200 font-mono">
                            {v.post || '—'}
                          </td>
                        )}
                        {showDelta && (
                          <td className="text-center px-4 py-3">
                            {delta ? (
                              <span
                                className={`inline-flex items-center gap-1 text-sm font-semibold ${
                                  delta.isImprovement === true
                                    ? 'text-emerald-400'
                                    : delta.isImprovement === false
                                    ? 'text-red-400'
                                    : 'text-slate-400'
                                }`}
                              >
                                {delta.isImprovement === true ? (
                                  <TrendingUp size={14} />
                                ) : delta.isImprovement === false ? (
                                  <TrendingDown size={14} />
                                ) : (
                                  <Minus size={14} />
                                )}
                                {delta.text}
                              </span>
                            ) : (
                              <span className="text-slate-600">—</span>
                            )}
                          </td>
                        )}
                      </tr>
                    );
                  })}
                </tbody>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* Legend */}
      {showDelta && (
        <div className="px-6 py-3 border-t border-white/10 flex items-center gap-6 text-xs text-slate-500">
          <span className="flex items-center gap-1">
            <span className="w-2 h-2 rounded-full bg-emerald-400" />
            Clinical Improvement
          </span>
          <span className="flex items-center gap-1">
            <span className="w-2 h-2 rounded-full bg-red-400" />
            Clinical Deterioration
          </span>
          <span className="flex items-center gap-1">
            <span className="w-2 h-2 rounded-full bg-slate-400" />
            Neutral
          </span>
        </div>
      )}
    </div>
  );
}
