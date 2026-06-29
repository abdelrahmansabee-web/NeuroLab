import { useMemo, useState } from 'react';
import { ChartDataPoint, PhaseMarkers } from '../types';

interface KinematicsChartProps {
  data: ChartDataPoint[];
  phaseMarkers: PhaseMarkers;
  title: string;
}

type ChartVariable = 'speed' | 'elbowAngle' | 'trunkDisp';

const variableConfig: Record<ChartVariable, { label: string; color: string; unit: string }> = {
  speed: { label: 'Wrist Speed', color: '#38bdf8', unit: 'm/s' },
  elbowAngle: { label: 'Elbow Angle', color: '#a78bfa', unit: 'deg' },
  trunkDisp: { label: 'Trunk Displacement', color: '#fb7185', unit: 'SW' },
};

export function KinematicsChart({ data, phaseMarkers, title }: KinematicsChartProps) {
  const [activeVar, setActiveVar] = useState<ChartVariable>('speed');

  const chartConfig = variableConfig[activeVar];

  // Compute chart dimensions
  const chartWidth = 800;
  const chartHeight = 300;
  const padding = { top: 20, right: 30, bottom: 40, left: 60 };
  const plotW = chartWidth - padding.left - padding.right;
  const plotH = chartHeight - padding.top - padding.bottom;

  const { path, yMin, yMax, xMin, xMax } = useMemo(() => {
    if (data.length === 0) return { path: '', yMin: 0, yMax: 1, xMin: 0, xMax: 1 };

    const values = data.map((d) => d[activeVar]);
    const times = data.map((d) => d.time);
    const yMin = Math.min(...values) * 0.9;
    const yMax = Math.max(...values) * 1.1;
    const xMin = Math.min(...times);
    const xMax = Math.max(...times);

    const xScale = (v: number) => padding.left + ((v - xMin) / (xMax - xMin)) * plotW;
    const yScale = (v: number) => padding.top + plotH - ((v - yMin) / (yMax - yMin)) * plotH;

    const pathParts = data.map((d, i) => {
      const x = xScale(d.time);
      const y = yScale(d[activeVar]);
      return `${i === 0 ? 'M' : 'L'} ${x.toFixed(1)} ${y.toFixed(1)}`;
    });

    return { path: pathParts.join(' '), yMin, yMax, xMin, xMax };
  }, [data, activeVar, plotW, plotH, padding]);

  const xScale = (v: number) => padding.left + ((v - xMin) / (xMax - xMin)) * plotW;
  const yScale = (v: number) => padding.top + plotH - ((v - yMin) / (yMax - yMin)) * plotH;

  // Phase marker lines
  const phaseLines = [
    { time: phaseMarkers.onset, label: 'Onset', color: '#fbbf24' },
    { time: phaseMarkers.reachEnd, label: 'Reach End', color: '#38bdf8' },
    { time: phaseMarkers.wipeEnd, label: 'Wipe End', color: '#a78bfa' },
    { time: phaseMarkers.returnEnd, label: 'Return', color: '#34d399' },
  ].filter((p) => p.time >= xMin && p.time <= xMax);

  // Y-axis ticks
  const yTicks = Array.from({ length: 5 }, (_, i) => yMin + (i / 4) * (yMax - yMin));

  // X-axis ticks
  const xTickCount = 6;
  const xTicks = Array.from({ length: xTickCount }, (_, i) => xMin + (i / (xTickCount - 1)) * (xMax - xMin));

  return (
    <div className="glass-card rounded-xl p-6">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-white font-semibold">{title}</h3>
        <div className="flex gap-2">
          {(Object.entries(variableConfig) as [ChartVariable, typeof variableConfig.speed][]).map(
            ([key, cfg]) => (
              <button
                key={key}
                onClick={() => setActiveVar(key)}
                className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                  activeVar === key
                    ? 'bg-white/15 text-white'
                    : 'bg-white/5 text-slate-400 hover:bg-white/10'
                }`}
                style={activeVar === key ? { borderBottom: `2px solid ${cfg.color}` } : {}}
              >
                {cfg.label}
              </button>
            )
          )}
        </div>
      </div>

      <svg viewBox={`0 0 ${chartWidth} ${chartHeight}`} className="w-full" preserveAspectRatio="xMidYMid meet">
        {/* Grid lines */}
        {yTicks.map((tick, i) => (
          <line
            key={`y-${i}`}
            x1={padding.left}
            y1={yScale(tick)}
            x2={chartWidth - padding.right}
            y2={yScale(tick)}
            stroke="rgba(255,255,255,0.07)"
            strokeWidth="1"
          />
        ))}

        {/* Phase markers */}
        {phaseLines.map((p, i) => (
          <g key={`phase-${i}`}>
            <line
              x1={xScale(p.time)}
              y1={padding.top}
              x2={xScale(p.time)}
              y2={padding.top + plotH}
              stroke={p.color}
              strokeWidth="1"
              strokeDasharray="4 3"
              opacity={0.6}
            />
            <text
              x={xScale(p.time)}
              y={padding.top - 5}
              fill={p.color}
              fontSize="9"
              textAnchor="middle"
              fontFamily="monospace"
            >
              {p.label}
            </text>
          </g>
        ))}

        {/* Data line */}
        <path d={path} fill="none" stroke={chartConfig.color} strokeWidth="2" opacity={0.9} />

        {/* Y-axis labels */}
        {yTicks.map((tick, i) => (
          <text
            key={`yl-${i}`}
            x={padding.left - 8}
            y={yScale(tick) + 4}
            fill="#94a3b8"
            fontSize="10"
            textAnchor="end"
            fontFamily="monospace"
          >
            {tick.toFixed(tick < 1 ? 2 : 1)}
          </text>
        ))}

        {/* X-axis labels */}
        {xTicks.map((tick, i) => (
          <text
            key={`xl-${i}`}
            x={xScale(tick)}
            y={chartHeight - 8}
            fill="#94a3b8"
            fontSize="10"
            textAnchor="middle"
            fontFamily="monospace"
          >
            {tick.toFixed(1)}s
          </text>
        ))}

        {/* Axis labels */}
        <text
          x={chartWidth / 2}
          y={chartHeight - 0}
          fill="#64748b"
          fontSize="11"
          textAnchor="middle"
        >
          Time (sec)
        </text>
        <text
          x={15}
          y={chartHeight / 2}
          fill="#64748b"
          fontSize="11"
          textAnchor="middle"
          transform={`rotate(-90, 15, ${chartHeight / 2})`}
        >
          {chartConfig.label} ({chartConfig.unit})
        </text>
      </svg>
    </div>
  );
}
