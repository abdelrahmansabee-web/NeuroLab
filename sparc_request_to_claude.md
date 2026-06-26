# SPARC Analysis Request for Claude

## Data
3 CSV files (pre, post, baseline) — MediaPipe pose landmarks, 30fps, ~25s each.

## Task Description
Multi-phase "reach and wipe" task performed by stroke patient:
1. Forward reach (hand to table)
2. Wipe right (along table edge)
3. Wipe left (back along table)
4. Return (hand back to rest)

Each phase is a point-to-point movement with brief pauses between phases.

## How to compute SPARC
The standard SPARC (Spectral Arc Length, Balasubramanian et al. 2015, JNER):

1. Get velocity signal v(t) from palm midpoint (RIGHT_WRIST + RIGHT_INDEX / 2)
2. Compute FFT magnitude spectrum |V(ω)|
3. Normalize by DC: ˆV(ω) = |V(ω)| / |V(0)|
4. Adaptive cutoff ω₀ at 95% cumulative spectral energy
5. SPARC = -∫₀^ω₀ √[1/ω₀² + (d log(ˆV(ω))/dω)²] dω

Standard range: healthy ≈ -1.5 to -2.5, mild stroke ≈ -3 to -5, severe ≈ -5 to -10.

## Questions for Claude

1. Should SPARC be computed per-phase (4 separate values) or over the whole active window?
2. If per-phase, what's the best way to detect phase boundaries automatically?
3. Does SPARC work well for this multi-phase task, or is there a better smoothness metric?
4. Compare pre-vs-post-vs-baseline SPARC values — do the changes make clinical sense?
5. Current Pause % uses fixed 0.03 velocity threshold — is this appropriate for stroke patients?
