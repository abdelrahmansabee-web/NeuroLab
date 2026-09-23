/**
 * One Google Drive slot per document kind in a patient folder.
 * Re-export updates that file; dated / alias names of the same kind are leftovers.
 */

const PHASES = ["pre", "post", "healthy", "baseline"];

function sanitize(name) {
  return String(name || "").trim().replace(/[^\w.\-]/g, "_").slice(0, 180);
}

function basename(name) {
  return String(name || "").replace(/\\/g, "/").split("/").pop() || "";
}

function normPhase(phase) {
  const p = String(phase || "").trim().toLowerCase();
  if (p === "baseline" || p === "healthy" || p === "healthy_side") return "healthy";
  if (p === "pre" || p === "post") return p;
  return "";
}

function stemOf(filename) {
  const base = basename(filename);
  const i = base.lastIndexOf(".");
  return (i > 0 ? base.slice(0, i) : base).toLowerCase();
}

export function documentKind(name) {
  const raw = basename(name);
  if (!raw) return null;
  const lower = raw.toLowerCase();
  const stem = stemOf(lower);

  if (lower.endsWith(".pdf")) return "clinic_report";

  if (lower.endsWith(".json")) {
    for (const phase of PHASES) {
      const np = normPhase(phase);
      if (stem === `${phase}_validation_overlay` || stem === `${np}_validation_overlay`) {
        return `${np}_validation_overlay`;
      }
      if (stem === `${phase}_kinematics` || stem === `${np}_kinematics`) {
        return `${np}_kinematics`;
      }
    }
    return null;
  }

  if (!/\.(mp4|mov|m4v|webm)$/i.test(lower)) return null;

  if (stem.endsWith("_validation_original") || (stem.endsWith("_original") && !stem.endsWith("_validation_original"))) {
    const base = stem.endsWith("_validation_original")
      ? stem.slice(0, -"_validation_original".length)
      : stem.slice(0, -"_original".length);
    const np = normPhase(base);
    return np ? `${np}_validation_original` : null;
  }

  for (const phase of PHASES) {
    const np = normPhase(phase);
    const aliases = [
      `${phase}_validation`,
      `${phase}_validation_unified`,
      `${phase}_unified_validation`,
      `${np}_validation`,
      `${np}_validation_unified`,
      `${np}_unified_validation`,
    ];
    if (aliases.includes(stem)) return `${np}_validation`;
  }
  return null;
}

export function canonicalDriveName(name, patientKey = "") {
  const kind = documentKind(name);
  if (!kind) return null;
  if (kind === "clinic_report") {
    const key = sanitize(patientKey).slice(0, 120);
    if (key) return `${key}.pdf`;
    const stem = stemOf(name);
    if (stem.startsWith("report_") || stem === "clinic_report" || stem === "report") {
      return "clinic_report.pdf";
    }
    return `${sanitize(stem) || "report"}.pdf`;
  }
  if (kind.endsWith("_validation_original")) {
    return `${kind.slice(0, -"_validation_original".length)}_validation_original.mp4`;
  }
  if (kind.endsWith("_validation_overlay")) {
    return `${kind.slice(0, -"_validation_overlay".length)}_validation_overlay.json`;
  }
  if (kind.endsWith("_kinematics")) {
    return `${kind.slice(0, -"_kinematics".length)}_kinematics.json`;
  }
  if (kind.endsWith("_validation")) {
    return `${kind.slice(0, -"_validation".length)}_validation.mp4`;
  }
  return null;
}

/** Stable Drive PDF name for this patient. Local download can still use a readable label. */
export function clinicReportDriveName(patientKey) {
  const key = sanitize(patientKey).slice(0, 120);
  return key ? `${key}.pdf` : "clinic_report.pdf";
}

/** Same folder key the clinic app uses when backing up a patient. */
export function patientDriveKeyFromDemographics(demographics, fallbackId) {
  const d = demographics || {};
  const id = String(d.participantId || fallbackId || "").trim();
  const name = String(d.name || d.fullName || "").trim();
  if (!id && !name) return "";
  const slug = (s) => String(s).replace(/[^\w.\-]/g, "_").slice(0, 100);
  if (id && name) return slug(`${id}_${name}`);
  return slug(id || name);
}

export function driveNameCandidates(primaryName) {
  const names = [primaryName];
  const mapped = canonicalDriveName(primaryName);
  if (mapped) names.push(mapped);
  const kind = documentKind(primaryName);
  if (kind === "clinic_report") {
    names.push("clinic_report.pdf", "report.pdf");
  } else if (kind && kind.endsWith("_validation_original")) {
    const phase = kind.slice(0, -"_validation_original".length);
    names.push(`${phase}_validation_original.mp4`, `${phase}_original.mp4`);
  } else if (kind && kind.endsWith("_validation") && !kind.includes("original") && !kind.includes("overlay")) {
    const phase = kind.slice(0, -"_validation".length);
    names.push(
      `${phase}_validation.mp4`,
      `${phase}_validation.webm`,
      `${phase}_validation_unified.mp4`,
      `${phase}_validation_unified.webm`,
    );
  }
  return [...new Set(names.filter(Boolean))];
}
