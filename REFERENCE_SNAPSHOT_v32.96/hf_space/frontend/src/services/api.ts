import {
  VideoPhase,
  ProcessingResult,
  BiomechanicalVariable,
  SettingsConfig,
  ChartDataPoint,
  PhaseMarkers,
  MetricsPayload
} from '../types';

// ─── Backend Communication ──────────────────────────────────────────────────

/**
 * Check if the backend is reachable
 */
export async function checkBackendHealth(backendUrl: string): Promise<boolean> {
  try {
    const response = await fetch(`${backendUrl}/health`, { 
      method: 'GET',
      signal: AbortSignal.timeout(3000)
    });
    return response.ok;
  } catch {
    return false;
  }
}

/**
 * Convert backend metrics response into display variables with correct
 * clinical improvement directions.
 */
function metricsToVariables(metrics: MetricsPayload, phase: VideoPhase): BiomechanicalVariable[] {
  const vars: BiomechanicalVariable[] = [
    {
      id: 'onset_time',
      name: 'Onset Time',
      description: 'Time to movement initiation',
      unit: 'sec',
      category: 'temporal',
      pre: '', post: '',
      improvementDirection: 'lower',
    },
    {
      id: 'reaching_duration',
      name: 'Reaching Duration',
      description: 'Duration of reaching phase',
      unit: 'sec',
      category: 'temporal',
      pre: '', post: '',
      improvementDirection: 'lower',
    },
    {
      id: 'wiping_duration',
      name: 'Wiping Duration',
      description: 'Duration of wiping phase',
      unit: 'sec',
      category: 'temporal',
      pre: '', post: '',
      improvementDirection: 'lower',
    },
    {
      id: 'total_duration',
      name: 'Total Task Duration',
      description: 'Total movement time from onset to return',
      unit: 'sec',
      category: 'temporal',
      pre: '', post: '',
      improvementDirection: 'lower',
    },
    {
      id: 'reaching_path_length',
      name: 'Reaching Path Length',
      description: '3D path length during reaching (shorter = more direct)',
      unit: 'm',
      category: 'spatial',
      pre: '', post: '',
      improvementDirection: 'lower',
    },
    {
      id: 'wiping_path_length',
      name: 'Wiping Path Length',
      description: '3D path length during wiping',
      unit: 'm',
      category: 'spatial',
      pre: '', post: '',
      improvementDirection: 'lower',
    },
    {
      id: 'trunk_displacement',
      name: 'Trunk Displacement',
      description: 'Trunk displacement normalized to shoulder width',
      unit: 'SW',
      category: 'compensation',
      pre: '', post: '',
      improvementDirection: 'lower',
    },
    {
      id: 'trunk_rotation',
      name: 'Trunk Rotation',
      description: 'Range of trunk axial rotation',
      unit: 'deg',
      category: 'compensation',
      pre: '', post: '',
      improvementDirection: 'lower',
    },
    {
      id: 'shoulder_compensation',
      name: 'Shoulder Compensation',
      description: 'Duration of shoulder hiking compensation',
      unit: 'sec',
      category: 'compensation',
      pre: '', post: '',
      improvementDirection: 'lower',
    },
    {
      id: 'elbow_extension_range',
      name: 'Elbow Extension Range',
      description: 'Range of elbow extension during reaching',
      unit: 'deg',
      category: 'joint',
      pre: '', post: '',
      improvementDirection: 'higher',
    },
    {
      id: 'sparc_reaching',
      name: 'SPARC (Reaching)',
      description: 'Spectral arc length smoothness metric (closer to 0 = smoother)',
      unit: '–',
      category: 'smoothness',
      pre: '', post: '',
      improvementDirection: 'closer_to_zero',
    },
    {
      id: 'sparc_full',
      name: 'SPARC (Full)',
      description: 'SPARC for entire movement',
      unit: '–',
      category: 'smoothness',
      pre: '', post: '',
      improvementDirection: 'closer_to_zero',
    },
    {
      id: 'nvp_reaching',
      name: 'NVP (Reaching)',
      description: 'Number of velocity peaks in reaching',
      unit: 'count',
      category: 'smoothness',
      pre: '', post: '',
      improvementDirection: 'lower_count',
    },
    {
      id: 'nvp_wiping',
      name: 'NVP (Wiping)',
      description: 'Number of velocity peaks in wiping',
      unit: 'count',
      category: 'smoothness',
      pre: '', post: '',
      improvementDirection: 'lower_count',
    },
  ];

  // Assign values to the correct phase column
  const metricMap: Record<string, string> = {
    onset_time: metrics.onset_time,
    reaching_duration: metrics.reaching_duration,
    wiping_duration: metrics.wiping_duration,
    total_duration: metrics.total_duration,
    reaching_path_length: metrics.reaching_path_length,
    wiping_path_length: metrics.wiping_path_length,
    trunk_displacement: metrics.trunk_displacement,
    trunk_rotation: metrics.trunk_rotation,
    shoulder_compensation: metrics.shoulder_compensation,
    elbow_extension_range: metrics.elbow_extension_range,
    sparc_reaching: metrics.sparc_reaching,
    sparc_full: metrics.sparc_full,
    nvp_reaching: metrics.nvp_reaching,
    nvp_wiping: metrics.nvp_wiping,
  };

  return vars.map(v => ({
    ...v,
    [phase]: metricMap[v.id] || '',
  }));
}

/**
 * Process a video file through the backend.
 * Falls back to mock data if backend is unreachable.
 */
export async function processVideo(
  file: File,
  side: string,
  phase: VideoPhase,
  settings: SettingsConfig,
  onProgress: (progress: number, step: number) => void
): Promise<{ result: ProcessingResult; usedMockData: boolean }> {
  
  onProgress(5, 0);

  // Check backend availability
  const isBackendUp = await checkBackendHealth(settings.backendUrl);

  if (isBackendUp) {
    return processWithBackend(file, side, phase, settings, onProgress);
  } else {
    console.warn('Backend unreachable. Using demo mode with mock data.');
    return processWithMockData(file, phase, onProgress);
  }
}

async function processWithBackend(
  file: File,
  side: string,
  phase: VideoPhase,
  settings: SettingsConfig,
  onProgress: (progress: number, step: number) => void
): Promise<{ result: ProcessingResult; usedMockData: boolean }> {
  
  onProgress(10, 1); // Uploading

  const formData = new FormData();
  formData.append('file', file);

  const sideParam = side === 'R' ? 'R' : 'L';
  const url = `${settings.backendUrl}/process-kinematics?side=${sideParam}&phase=${phase}`;

  onProgress(20, 2); // Processing landmarks

  const response = await fetch(url, {
    method: 'POST',
    body: formData,
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({ detail: 'Unknown error' }));
    throw new Error(errorData.detail || `Server error: ${response.status}`);
  }

  onProgress(60, 3); // Computing kinematics

  const data = await response.json();

  if (!data.success) {
    throw new Error('Processing failed on the server');
  }

  onProgress(80, 4); // Building results

  const variables = metricsToVariables(data.metrics, phase);

  onProgress(95, 5); // Finalizing

  const result: ProcessingResult = {
    phase,
    side: data.side,
    metrics: data.metrics,
    meta: {
      frameCount: data.meta.frame_count,
      fps: data.meta.fps,
      segmentation: data.meta.segmentation,
    },
    links: data.links,
    csvContent: '', // Will be fetched on demand for download
    trcContent: '',
    validationVideoUrl: data.links.video,
    frameCount: data.meta.frame_count,
    fps: data.meta.fps,
    variables,
  };

  onProgress(100, 5);

  return { result, usedMockData: false };
}

async function processWithMockData(
  file: File,
  phase: VideoPhase,
  onProgress: (progress: number, step: number) => void
): Promise<{ result: ProcessingResult; usedMockData: boolean }> {
  
  // Simulate processing steps with delays
  const steps = [
    { progress: 15, step: 1, delay: 400 },
    { progress: 35, step: 2, delay: 600 },
    { progress: 55, step: 3, delay: 500 },
    { progress: 75, step: 4, delay: 400 },
    { progress: 90, step: 5, delay: 300 },
  ];

  for (const s of steps) {
    await new Promise(r => setTimeout(r, s.delay));
    onProgress(s.progress, s.step);
  }

  const mockMetrics: MetricsPayload = {
    onset_time: phase === 'pre' ? '0.450' : '0.224',
    reaching_duration: phase === 'pre' ? '1.250' : '0.644',
    wiping_duration: phase === 'pre' ? '2.150' : '1.155',
    total_duration: phase === 'pre' ? '4.850' : '2.625',
    reaching_path_length: phase === 'pre' ? '0.420' : '0.350',
    reaching_path_normalized: phase === 'pre' ? '1.680' : '1.400',
    wiping_path_length: phase === 'pre' ? '0.680' : '0.550',
    wiping_path_normalized: phase === 'pre' ? '2.720' : '2.200',
    trunk_displacement: phase === 'pre' ? '0.250' : '0.156',
    trunk_rotation: phase === 'pre' ? '15.20' : '12.74',
    elbow_extension_range: phase === 'pre' ? '45.3' : '58.7',
    shoulder_compensation: phase === 'pre' ? '1.850' : '1.235',
    shoulder_displacement_extent: phase === 'pre' ? '0.180' : '0.110',
    sparc_reaching: phase === 'pre' ? '-2.85' : '-1.95',
    sparc_full: phase === 'pre' ? '-3.25' : '-2.35',
    nvp_reaching: phase === 'pre' ? '5' : '3',
    nvp_wiping: phase === 'pre' ? '8' : '4',
  };

  const variables = metricsToVariables(mockMetrics, phase);
  const fps = 30;
  const frameCount = Math.round(parseFloat(mockMetrics.total_duration) * fps + 15);

  const mockCsv = generateMockCsv(frameCount, fps);
  const mockTrc = generateMockTrc(frameCount, fps);

  onProgress(100, 5);

  const result: ProcessingResult = {
    phase,
    side: 'R',
    metrics: mockMetrics,
    meta: {
      frameCount,
      fps,
      segmentation: {
        onset: 10,
        reach_end: Math.round(frameCount * 0.3),
        wipe_end: Math.round(frameCount * 0.7),
        return_end: frameCount - 5,
      }
    },
    links: { csv: '', trc: '', video: '' },
    csvContent: mockCsv,
    trcContent: mockTrc,
    validationVideoUrl: '',
    frameCount,
    fps,
    variables,
  };

  return { result, usedMockData: true };
}


// ─── Download Utilities ─────────────────────────────────────────────────────

export function downloadFile(content: string, filename: string, mimeType: string): void {
  const blob = new Blob([content], { type: mimeType });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

export async function downloadFromUrl(url: string, filename: string): Promise<void> {
  try {
    const response = await fetch(url);
    const blob = await response.blob();
    const blobUrl = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = blobUrl;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(blobUrl);
  } catch {
    window.open(url, '_blank');
  }
}

export async function downloadAllAsZip(
  phase: string,
  csvContent: string,
  trcContent: string,
  videoUrl: string | null
): Promise<void> {
  // Without JSZip, download files individually
  if (csvContent) {
    downloadFile(csvContent, `kinematics_${phase}_data.csv`, 'text/csv');
  }
  if (trcContent) {
    setTimeout(() => {
      downloadFile(trcContent, `kinematics_${phase}_motion.trc`, 'text/plain');
    }, 500);
  }
  if (videoUrl) {
    setTimeout(() => {
      window.open(videoUrl, '_blank');
    }, 1000);
  }
}


// ─── Mock Data Generators ───────────────────────────────────────────────────

function generateMockCsv(frames: number, fps: number): string {
  const headers = ['Frame', 'Time_sec', 'R_Shoulder_X', 'R_Shoulder_Y', 'R_Wrist_X', 'R_Wrist_Y'];
  const rows = [headers.join(',')];
  for (let i = 0; i < frames; i++) {
    const t = i / fps;
    rows.push(`${i + 1},${t.toFixed(4)},${(Math.random() * 0.1).toFixed(5)},${(Math.random() * 0.1).toFixed(5)},${(Math.random() * 0.2).toFixed(5)},${(Math.random() * 0.2).toFixed(5)}`);
  }
  return rows.join('\n');
}

function generateMockTrc(frames: number, fps: number): string {
  let content = `PathFileType\t4\t(X/Y/Z)\toutput_motion.trc\n`;
  content += `${fps}\t${fps}\t${frames}\t33\tm\t${fps}\t1\t${frames}\n`;
  content += `Frame#\tTime\tNose\n`;
  content += `\t\tX1\tY1\tZ1\n\n`;
  for (let i = 0; i < frames; i++) {
    content += `${i + 1}\t${(i / fps).toFixed(4)}\t0.00000\t0.00000\t0.00000\n`;
  }
  return content;
}

export function createMockChartData(frameCount: number, fps: number): ChartDataPoint[] {
  const data: ChartDataPoint[] = [];
  for (let i = 0; i < frameCount; i++) {
    const t = i / fps;
    const phase = t / (frameCount / fps);
    data.push({
      time: parseFloat(t.toFixed(3)),
      speed: Math.max(0, Math.sin(phase * Math.PI * 3) * 2.5 + Math.random() * 0.3),
      elbowAngle: 90 + Math.sin(phase * Math.PI * 2) * 40 + Math.random() * 2,
      trunkDisp: Math.abs(Math.sin(phase * Math.PI * 1.5)) * 0.15 + Math.random() * 0.02,
    });
  }
  return data;
}

export function createMockPhaseMarkers(): PhaseMarkers {
  return {
    onset: 0.45,
    reachEnd: 1.7,
    wipeEnd: 3.85,
    returnEnd: 4.85,
  };
}
