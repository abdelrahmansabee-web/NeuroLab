import { useState, useCallback, useEffect } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import {
  Play,
  RotateCcw,
  ChevronDown,
  ChevronUp,
  BarChart3,
  Clock,
  Maximize2,
  RefreshCw,
  Activity,
  Zap,
  AlertCircle,
  Info,
  Film,
  Columns2,
  LayoutGrid,
  Loader2,
} from 'lucide-react';
import {
  Header,
  VideoUploader,
  SideSelector,
  ResultsTable,
  KinematicsChart,
  DownloadPanel,
  ProcessingStatus,
  MetricCard,
  SettingsModal,
  HelpModal,
  DemoModeIndicator,
} from './components';
import {
  AffectedSide,
  VideoPhase,
  VideoUploads,
  ProcessingResult,
  BiomechanicalVariable,
  SettingsConfig,
  ChartDataPoint,
  PhaseMarkers,
} from './types';
import {
  processVideo,
  downloadFile,
  downloadFromUrl,
  downloadAllAsZip,
  createMockChartData,
  createMockPhaseMarkers,
} from './services/api';

// ─── Initial State ──────────────────────────────────────────────────────────

const initialVideoFile = {
  file: null,
  preview: null,
  status: 'idle' as const,
  progress: 0,
};

const initialSettings: SettingsConfig = {
  backendUrl: 'http://localhost:8000',
  cutoffFrequency: 3.0,
  filterOrder: 4,
  modelComplexity: 2,
  minDetectionConfidence: 0.6,
  minTrackingConfidence: 0.6,
};

// ─── App Component ──────────────────────────────────────────────────────────

function App() {
  // ── State ──
  const [affectedSide, setAffectedSide] = useState<AffectedSide>('R');
  const [videos, setVideos] = useState<VideoUploads>({
    pre: { ...initialVideoFile },
    post: { ...initialVideoFile },
  });
  const [results, setResults] = useState<{
    pre: ProcessingResult | null;
    post: ProcessingResult | null;
  }>({
    pre: null,
    post: null,
  });
  const [isProcessing, setIsProcessing] = useState(false);
  const [currentProcessingPhase, setCurrentProcessingPhase] = useState<VideoPhase | null>(null);
  const [currentStep, setCurrentStep] = useState(0);
  const [showSettings, setShowSettings] = useState(false);
  const [showHelp, setShowHelp] = useState(false);
  const [settings, setSettings] = useState<SettingsConfig>(initialSettings);
  const [expandedSections, setExpandedSections] = useState({
    upload: true,
    validation: true,
    metrics: true,
    chart: true,
    download: true,
  });
  const [validationViewMode, setValidationViewMode] = useState<'tabs' | 'compare'>('tabs');
  const [activeValidationTab, setActiveValidationTab] = useState<VideoPhase>('pre');
  const [chartData, setChartData] = useState<ChartDataPoint[]>([]);
  const [phaseMarkers] = useState<PhaseMarkers>(createMockPhaseMarkers());
  const [error, setError] = useState<string | null>(null);
  const [isDemoMode, setIsDemoMode] = useState(true);

  // ── Load chart data when results change ──
  useEffect(() => {
    const firstResult = results.pre || results.post;
    if (firstResult) {
      setChartData(createMockChartData(firstResult.frameCount, firstResult.fps));
    }
  }, [results]);

  // ── File selection handler ──
  const handleFileSelect = useCallback((phase: VideoPhase, file: File) => {
    const preview = URL.createObjectURL(file);
    setVideos((prev) => ({
      ...prev,
      [phase]: {
        file,
        preview,
        status: 'idle' as const,
        progress: 0,
      },
    }));
    setError(null);
  }, []);

  // ── File removal handler ──
  const handleFileRemove = useCallback((phase: VideoPhase) => {
    setVideos((prev) => {
      if (prev[phase].preview) {
        URL.revokeObjectURL(prev[phase].preview!);
      }
      return {
        ...prev,
        [phase]: { ...initialVideoFile },
      };
    });
    setResults((prev) => ({
      ...prev,
      [phase]: null,
    }));
  }, []);

  // ── Process all uploaded videos ──
  const handleProcessAll = useCallback(async () => {
    const phases: VideoPhase[] = ['pre', 'post'];
    const videosToProcess = phases.filter((phase) => videos[phase].file);

    if (videosToProcess.length === 0) {
      setError('Please upload at least one video to process.');
      return;
    }

    setIsProcessing(true);
    setError(null);

    for (const phase of videosToProcess) {
      setCurrentProcessingPhase(phase);
      setCurrentStep(0);

      setVideos((prev) => ({
        ...prev,
        [phase]: { ...prev[phase], status: 'processing', progress: 0 },
      }));

      try {
        const { result, usedMockData } = await processVideo(
          videos[phase].file!,
          affectedSide,
          phase,
          settings,
          (progress, step) => {
            setCurrentStep(step);
            setVideos((prev) => ({
              ...prev,
              [phase]: { ...prev[phase], progress },
            }));
          }
        );

        setIsDemoMode(usedMockData);
        setResults((prev) => ({
          ...prev,
          [phase]: result,
        }));

        setVideos((prev) => ({
          ...prev,
          [phase]: { ...prev[phase], status: 'completed', progress: 100 },
        }));
      } catch (err) {
        setVideos((prev) => ({
          ...prev,
          [phase]: {
            ...prev[phase],
            status: 'error',
            error: err instanceof Error ? err.message : 'Processing failed',
          },
        }));
      }
    }

    setIsProcessing(false);
    setCurrentProcessingPhase(null);
  }, [videos, affectedSide, settings]);

  // ── Reset everything ──
  const handleReset = useCallback(() => {
    Object.values(videos).forEach((v) => {
      if (v.preview) URL.revokeObjectURL(v.preview);
    });
    setVideos({
      pre: { ...initialVideoFile },
      post: { ...initialVideoFile },
    });
    setResults({ pre: null, post: null });
    setError(null);
    setChartData([]);
  }, [videos]);

  // ── Download handler ──
  const handleDownload = useCallback(
    (phase: VideoPhase, type: 'csv' | 'trc' | 'video' | 'all') => {
      const result = results[phase];
      if (!result) return;

      switch (type) {
        case 'csv':
          if (result.csvContent) {
            downloadFile(result.csvContent, `kinematics_${phase}_data.csv`, 'text/csv');
          } else if (result.links.csv) {
            downloadFromUrl(result.links.csv, `kinematics_${phase}_data.csv`);
          }
          break;
        case 'trc':
          if (result.trcContent) {
            downloadFile(result.trcContent, `kinematics_${phase}_motion.trc`, 'text/plain');
          } else if (result.links.trc) {
            downloadFromUrl(result.links.trc, `kinematics_${phase}_motion.trc`);
          }
          break;
        case 'video':
          if (result.validationVideoUrl) {
            window.open(result.validationVideoUrl, '_blank');
          }
          break;
        case 'all':
          downloadAllAsZip(phase, result.csvContent, result.trcContent, result.validationVideoUrl || null);
          break;
      }
    },
    [results]
  );

  // ── Combine variables from all phases ──
  const combineVariables = (): BiomechanicalVariable[] => {
    const variableMap = new Map<string, BiomechanicalVariable>();

    (['pre', 'post'] as VideoPhase[]).forEach((phase) => {
      const phaseResults = results[phase];
      if (phaseResults) {
        phaseResults.variables.forEach((v) => {
          const existing = variableMap.get(v.id);
          if (existing) {
            // Merge phase value into existing variable
            variableMap.set(v.id, {
              ...existing,
              pre: v.pre || existing.pre,
              post: v.post || existing.post,
            });
          } else {
            variableMap.set(v.id, { ...v });
          }
        });
      }
    });

    return Array.from(variableMap.values());
  };

  const combinedVariables = combineVariables();
  const hasAnyResults = !!(results.pre || results.post);
  const hasAnyVideos = !!(videos.pre.file || videos.post.file);

  // ── Toggle section ──
  const toggleSection = (section: keyof typeof expandedSections) => {
    setExpandedSections((prev) => ({
      ...prev,
      [section]: !prev[section],
    }));
  };

  // ── Summary metrics for dashboard cards ──
  const getSummaryMetrics = () => {
    if (!hasAnyResults) return null;

    const firstResult = results.pre || results.post;
    if (!firstResult) return null;

    const m = firstResult.metrics;
    return {
      totalDuration: parseFloat(m.total_duration) || 0,
      reachingPath: parseFloat(m.reaching_path_length) || 0,
      elbowRange: parseFloat(m.elbow_extension_range) || 0,
      sparc: parseFloat(m.sparc_reaching) || 0,
      trunkDisp: parseFloat(m.trunk_displacement) || 0,
      nvp: parseInt(m.nvp_reaching) || 0,
    };
  };

  const summaryMetrics = getSummaryMetrics();

  // ── Render ──
  return (
    <div className="min-h-screen flex flex-col">
      {/* Background grid */}
      <div className="neural-bg">
        <svg width="100%" height="100%" className="opacity-30">
          <defs>
            <pattern id="grid" width="40" height="40" patternUnits="userSpaceOnUse">
              <path d="M 40 0 L 0 0 0 40" fill="none" stroke="rgba(14,165,233,0.1)" strokeWidth="1" />
            </pattern>
          </defs>
          <rect width="100%" height="100%" fill="url(#grid)" />
        </svg>
      </div>

      <Header onSettingsClick={() => setShowSettings(true)} onHelpClick={() => setShowHelp(true)} />

      <main className="flex-1 max-w-7xl mx-auto w-full px-4 sm:px-6 lg:px-8 py-8">
        {/* Error Alert */}
        <AnimatePresence>
          {error && (
            <motion.div
              initial={{ opacity: 0, y: -20 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -20 }}
              className="mb-6 flex items-center gap-3 px-4 py-3 rounded-xl bg-red-500/10 border border-red-500/30"
            >
              <AlertCircle className="text-red-400" size={20} />
              <span className="text-red-300">{error}</span>
              <button onClick={() => setError(null)} className="ml-auto text-red-400 hover:text-red-300">
                ×
              </button>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Backend Notice */}
        {!hasAnyResults && (
          <div className="mb-6 flex items-start gap-3 px-4 py-3 rounded-xl bg-amber-500/10 border border-amber-500/30">
            <Info className="text-amber-400 flex-shrink-0 mt-0.5" size={20} />
            <div>
              <p className="text-amber-300 font-medium">Backend Connection</p>
              <p className="text-amber-200/70 text-sm">
                This application requires a Python/FastAPI backend for full video processing. 
                Demo mode with mock data is active when the backend is unavailable.
              </p>
            </div>
          </div>
        )}

        {/* ═══════ Upload Section ═══════ */}
        <section className="mb-8">
          <button
            onClick={() => toggleSection('upload')}
            className="w-full flex items-center justify-between px-4 py-3 rounded-xl glass-card mb-4"
          >
            <h2 className="text-lg font-semibold text-white flex items-center gap-2">
              <BarChart3 className="text-sky-400" size={20} />
              Video Upload & Configuration
            </h2>
            {expandedSections.upload ? (
              <ChevronUp className="text-slate-400" />
            ) : (
              <ChevronDown className="text-slate-400" />
            )}
          </button>

          <AnimatePresence>
            {expandedSections.upload && (
              <motion.div
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: 'auto' }}
                exit={{ opacity: 0, height: 0 }}
                className="overflow-hidden"
              >
                <div className="grid lg:grid-cols-4 gap-6">
                  <div className="lg:col-span-1">
                    <SideSelector
                      selectedSide={affectedSide}
                      onSideChange={setAffectedSide}
                      disabled={isProcessing}
                    />
                  </div>
                  <div className="lg:col-span-3 grid md:grid-cols-2 gap-4">
                    {(['pre', 'post'] as VideoPhase[]).map((phase) => (
                      <VideoUploader
                        key={phase}
                        phase={phase}
                        videoFile={videos[phase]}
                        onFileSelect={handleFileSelect}
                        onRemove={handleFileRemove}
                        disabled={isProcessing}
                      />
                    ))}
                  </div>
                </div>

                <div className="flex justify-center gap-4 mt-6">
                  <button
                    onClick={handleProcessAll}
                    disabled={!hasAnyVideos || isProcessing}
                    className={`btn-primary px-8 py-3 rounded-xl font-semibold flex items-center gap-2 ${
                      !hasAnyVideos || isProcessing ? 'opacity-50 cursor-not-allowed' : ''
                    }`}
                  >
                    <Play size={18} />
                    Process Videos
                  </button>
                  <button
                    onClick={handleReset}
                    disabled={isProcessing}
                    className="px-6 py-3 rounded-xl font-medium bg-slate-700/50 text-slate-300 hover:bg-slate-600/50 transition-colors flex items-center gap-2"
                  >
                    <RotateCcw size={18} />
                    Reset
                  </button>
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </section>

        {/* ═══════ Summary Metrics ═══════ */}
        {hasAnyResults && summaryMetrics && (
          <section className="mb-8">
            <button
              onClick={() => toggleSection('metrics')}
              className="w-full flex items-center justify-between px-4 py-3 rounded-xl glass-card mb-4"
            >
              <h2 className="text-lg font-semibold text-white flex items-center gap-2">
                <Activity className="text-emerald-400" size={20} />
                Quick Summary
              </h2>
              {expandedSections.metrics ? (
                <ChevronUp className="text-slate-400" />
              ) : (
                <ChevronDown className="text-slate-400" />
              )}
            </button>

            <AnimatePresence>
              {expandedSections.metrics && (
                <motion.div
                  initial={{ opacity: 0, height: 0 }}
                  animate={{ opacity: 1, height: 'auto' }}
                  exit={{ opacity: 0, height: 0 }}
                  className="overflow-hidden"
                >
                  <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
                    <MetricCard title="Total Duration" value={summaryMetrics.totalDuration} unit="sec" icon={Clock} color="amber" />
                    <MetricCard title="Reaching Path" value={summaryMetrics.reachingPath} unit="m" icon={Maximize2} color="sky" />
                    <MetricCard title="Elbow Range" value={summaryMetrics.elbowRange} unit="deg" icon={RefreshCw} color="purple" />
                    <MetricCard title="SPARC" value={summaryMetrics.sparc} unit="–" icon={Zap} color="emerald" />
                    <MetricCard title="Trunk Disp." value={summaryMetrics.trunkDisp} unit="SW" icon={Activity} color="rose" />
                    <MetricCard title="NVP" value={summaryMetrics.nvp} unit="peaks" icon={BarChart3} color="amber" />
                  </div>
                </motion.div>
              )}
            </AnimatePresence>
          </section>
        )}

        {/* ═══════ Validation Video ═══════ */}
        {(hasAnyResults || (currentProcessingPhase && videos[currentProcessingPhase].status === 'processing')) && (
          <section className="mb-8">
            <button
              onClick={() => toggleSection('validation')}
              className="w-full flex items-center justify-between px-4 py-3 rounded-xl glass-card mb-4"
            >
              <h2 className="text-lg font-semibold text-white flex items-center gap-2">
                <Film className="text-purple-400" size={20} />
                Validation Video
              </h2>
              {expandedSections.validation ? (
                <ChevronUp className="text-slate-400" />
              ) : (
                <ChevronDown className="text-slate-400" />
              )}
            </button>

            <AnimatePresence>
              {expandedSections.validation && (
                <motion.div
                  initial={{ opacity: 0, height: 0 }}
                  animate={{ opacity: 1, height: 'auto' }}
                  exit={{ opacity: 0, height: 0 }}
                  className="overflow-hidden"
                >
                  <div className="glass-card rounded-xl overflow-hidden">
                    {/* View mode toggle */}
                    <div className="flex items-center justify-between px-6 py-4 border-b border-white/10">
                      <div className="flex items-center gap-2">
                        {(['pre', 'post'] as VideoPhase[]).map((phase) => {
                          const isActive = validationViewMode === 'tabs' && activeValidationTab === phase;
                          const isAvailable = !!results[phase]?.validationVideoUrl ||
                            (currentProcessingPhase === phase && videos[phase].status === 'processing');
                          const label = phase === 'pre' ? 'Pre-Treatment' : 'Post-Treatment';
                          const color = phase === 'pre' ? 'amber' : 'emerald';
                          return (
                            <button
                              key={phase}
                              onClick={() => {
                                setValidationViewMode('tabs');
                                setActiveValidationTab(phase);
                              }}
                              disabled={!isAvailable}
                              className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
                                isActive
                                  ? `bg-${color}-500/20 text-${color}-400`
                                  : isAvailable
                                  ? 'text-slate-400 hover:text-white hover:bg-white/5'
                                  : 'text-slate-600 cursor-not-allowed'
                              }`}
                            >
                              {label}
                            </button>
                          );
                        })}
                      </div>

                      <div className="flex items-center bg-white/5 rounded-lg p-1">
                        <button
                          onClick={() => setValidationViewMode('tabs')}
                          className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition-colors ${
                            validationViewMode === 'tabs'
                              ? 'bg-slate-700 text-white'
                              : 'text-slate-400 hover:text-white'
                          }`}
                        >
                          <LayoutGrid size={14} />
                          Tabs
                        </button>
                        <button
                          onClick={() => setValidationViewMode('compare')}
                          disabled={!(results.pre?.validationVideoUrl && results.post?.validationVideoUrl)}
                          className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition-colors ${
                            validationViewMode === 'compare'
                              ? 'bg-slate-700 text-white'
                              : results.pre?.validationVideoUrl && results.post?.validationVideoUrl
                              ? 'text-slate-400 hover:text-white'
                              : 'text-slate-600 cursor-not-allowed'
                          }`}
                        >
                          <Columns2 size={14} />
                          Side-by-Side
                        </button>
                      </div>
                    </div>

                    {/* Video player area */}
                    <div className="p-6">
                      {validationViewMode === 'tabs' ? (
                        <div className="w-full">
                          {(() => {
                            const phase = activeValidationTab;
                            const result = results[phase];
                            const isProcessingPhase = currentProcessingPhase === phase && videos[phase].status === 'processing';

                            if (isProcessingPhase && !result?.validationVideoUrl) {
                              return (
                                <div className="aspect-video bg-black/50 rounded-xl flex flex-col items-center justify-center text-slate-400">
                                  <Loader2 className="animate-spin text-sky-400 mb-3" size={32} />
                                  <p className="text-sm">Generating validation video for {phase === 'pre' ? 'Pre-Treatment' : 'Post-Treatment'}...</p>
                                </div>
                              );
                            }

                            if (result?.validationVideoUrl) {
                              return (
                                <video
                                  src={result.validationVideoUrl}
                                  className="w-full rounded-xl aspect-video bg-black"
                                  controls
                                  muted
                                  playsInline
                                />
                              );
                            }

                            return (
                              <div className="aspect-video bg-black/50 rounded-xl flex flex-col items-center justify-center text-slate-500">
                                <Film size={32} className="mb-3 opacity-50" />
                                <p className="text-sm">No validation video available for {phase === 'pre' ? 'Pre-Treatment' : 'Post-Treatment'}</p>
                              </div>
                            );
                          })()}
                        </div>
                      ) : (
                        <div className="grid md:grid-cols-2 gap-4">
                          {(['pre', 'post'] as VideoPhase[]).map((phase) => {
                            const result = results[phase];
                            const label = phase === 'pre' ? 'Pre-Treatment' : 'Post-Treatment';
                            return (
                              <div key={phase} className="space-y-2">
                                <p className={`text-sm font-medium text-center ${
                                  phase === 'pre' ? 'text-amber-400' : 'text-emerald-400'
                                }`}>
                                  {label}
                                </p>
                                {result?.validationVideoUrl ? (
                                  <video
                                    src={result.validationVideoUrl}
                                    className="w-full rounded-xl aspect-video bg-black"
                                    controls
                                    muted
                                    playsInline
                                  />
                                ) : (
                                  <div className="aspect-video bg-black/50 rounded-xl flex items-center justify-center text-slate-500">
                                    <span className="text-sm">Not available</span>
                                  </div>
                                )}
                              </div>
                            );
                          })}
                        </div>
                      )}
                    </div>
                  </div>
                </motion.div>
              )}
            </AnimatePresence>
          </section>
        )}

        {/* ═══════ Results Table ═══════ */}
        {hasAnyResults && (
          <section className="mb-8">
            <ResultsTable
              variables={combinedVariables}
              hasPreResults={!!results.pre}
              hasPostResults={!!results.post}
            />
          </section>
        )}

        {/* ═══════ Kinematic Chart ═══════ */}
        {hasAnyResults && chartData.length > 0 && (
          <section className="mb-8">
            <button
              onClick={() => toggleSection('chart')}
              className="w-full flex items-center justify-between px-4 py-3 rounded-xl glass-card mb-4"
            >
              <h2 className="text-lg font-semibold text-white flex items-center gap-2">
                <BarChart3 className="text-sky-400" size={20} />
                Kinematic Profile
              </h2>
              {expandedSections.chart ? (
                <ChevronUp className="text-slate-400" />
              ) : (
                <ChevronDown className="text-slate-400" />
              )}
            </button>

            <AnimatePresence>
              {expandedSections.chart && (
                <motion.div
                  initial={{ opacity: 0, height: 0 }}
                  animate={{ opacity: 1, height: 'auto' }}
                  exit={{ opacity: 0, height: 0 }}
                  className="overflow-hidden"
                >
                  <KinematicsChart data={chartData} phaseMarkers={phaseMarkers} title="Movement Analysis" />
                </motion.div>
              )}
            </AnimatePresence>
          </section>
        )}

        {/* ═══════ Download Section ═══════ */}
        {hasAnyResults && (
          <section className="mb-8">
            <button
              onClick={() => toggleSection('download')}
              className="w-full flex items-center justify-between px-4 py-3 rounded-xl glass-card mb-4"
            >
              <h2 className="text-lg font-semibold text-white flex items-center gap-2">
                <BarChart3 className="text-emerald-400" size={20} />
                Download Results
              </h2>
              {expandedSections.download ? (
                <ChevronUp className="text-slate-400" />
              ) : (
                <ChevronDown className="text-slate-400" />
              )}
            </button>

            <AnimatePresence>
              {expandedSections.download && (
                <motion.div
                  initial={{ opacity: 0, height: 0 }}
                  animate={{ opacity: 1, height: 'auto' }}
                  exit={{ opacity: 0, height: 0 }}
                  className="overflow-hidden"
                >
                  <DownloadPanel results={results} onDownload={handleDownload} />
                </motion.div>
              )}
            </AnimatePresence>
          </section>
        )}
      </main>

      {/* Footer */}
      <footer className="mt-auto py-6 border-t border-white/5">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 flex flex-col md:flex-row items-center justify-between gap-4">
          <p className="text-sm text-slate-500">
            KinematicsAI Lab — Stroke Rehabilitation Kinematic Analysis System
          </p>
          <div className="flex items-center gap-4 text-xs text-slate-600">
            <span>MediaPipe Pose</span>
            <span>•</span>
            <span>Butterworth Filter</span>
            <span>•</span>
            <span>OpenSim Compatible</span>
          </div>
        </div>
      </footer>

      {/* Overlays */}
      <ProcessingStatus
        isProcessing={isProcessing}
        currentStep={currentStep}
        totalSteps={6}
        currentPhase={
          currentProcessingPhase
            ? currentProcessingPhase.charAt(0).toUpperCase() + currentProcessingPhase.slice(1)
            : ''
        }
      />
      <SettingsModal
        isOpen={showSettings}
        onClose={() => setShowSettings(false)}
        settings={settings}
        onSettingsChange={setSettings}
      />
      <HelpModal isOpen={showHelp} onClose={() => setShowHelp(false)} />
      <DemoModeIndicator isDemo={isDemoMode} backendUrl={settings.backendUrl} />
    </div>
  );
}

export default App;
