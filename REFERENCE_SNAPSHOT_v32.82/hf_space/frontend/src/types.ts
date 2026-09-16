// ─── Core Types ──────────────────────────────────────────────────────────────

export type AffectedSide = 'R' | 'L';

export type VideoPhase = 'pre' | 'post';

export type VideoStatus = 'idle' | 'processing' | 'completed' | 'error';

// ─── Video File ─────────────────────────────────────────────────────────────

export interface VideoFile {
  file: File | null;
  preview: string | null;
  status: VideoStatus;
  progress: number;
  error?: string;
}

export interface VideoUploads {
  pre: VideoFile;
  post: VideoFile;
}

// ─── Processing Results ─────────────────────────────────────────────────────

export interface ProcessingResult {
  phase: VideoPhase;
  side: string;
  metrics: MetricsPayload;
  meta: {
    frameCount: number;
    fps: number;
    segmentation: {
      onset: number;
      reach_end: number;
      wipe_end: number;
      return_end: number;
    };
  };
  links: {
    csv: string;
    trc: string;
    video: string;
  };
  csvContent: string;
  trcContent: string;
  validationVideoUrl: string;
  frameCount: number;
  fps: number;
  variables: BiomechanicalVariable[];
}

export interface MetricsPayload {
  onset_time: string;
  reaching_duration: string;
  wiping_duration: string;
  total_duration: string;
  reaching_path_length: string;
  reaching_path_normalized: string;
  wiping_path_length: string;
  wiping_path_normalized: string;
  trunk_displacement: string;
  trunk_rotation: string;
  elbow_extension_range: string;
  shoulder_compensation: string;
  shoulder_displacement_extent: string;
  sparc_reaching: string;
  sparc_full: string;
  nvp_reaching: string;
  nvp_wiping: string;
}

// ─── Display Variables ──────────────────────────────────────────────────────

export interface BiomechanicalVariable {
  id: string;
  name: string;
  description: string;
  unit: string;
  category: 'temporal' | 'spatial' | 'compensation' | 'joint' | 'smoothness';
  pre: string;
  post: string;
  /** 
   * Direction of clinical improvement:
   * 'lower' = lower is better (e.g., time, compensation)
   * 'higher' = higher is better (e.g., elbow range)
   * 'closer_to_zero' = closer to 0 is better (e.g., SPARC)
   * 'lower_count' = fewer peaks is better (e.g., NVP)
   */
  improvementDirection: 'lower' | 'higher' | 'closer_to_zero' | 'lower_count';
}

// ─── Chart ──────────────────────────────────────────────────────────────────

export interface ChartDataPoint {
  time: number;
  speed: number;
  elbowAngle: number;
  trunkDisp: number;
}

export interface PhaseMarkers {
  onset: number;
  reachEnd: number;
  wipeEnd: number;
  returnEnd: number;
}

// ─── Settings ───────────────────────────────────────────────────────────────

export interface SettingsConfig {
  backendUrl: string;
  cutoffFrequency: number;
  filterOrder: number;
  modelComplexity: number;
  minDetectionConfidence: number;
  minTrackingConfidence: number;
}
