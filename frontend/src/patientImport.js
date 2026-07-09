/**
 * Import patient session from NeuroLab JSON export or Clinical Report PDF.
 */

import * as pdfjsLib from "pdfjs-dist/build/pdf";

pdfjsLib.GlobalWorkerOptions.workerSrc = `${process.env.PUBLIC_URL || ""}/pdf.worker.min.js`;

const SECTION_KEYS = ["demographics", "ipaq", "vas", "vams", "motorchange", "kgia", "wmft", "kinematics"];

const KVIQ_LABELS = [
  "Neck forward–backward flexion",
  "Neck forward-backward flexion",
  "Shoulder elevation (shrug)",
  "Forward arm raise",
  "Elbow flexion",
  "Thumb-to-finger opposition",
  "Forward trunk lean",
  "Knee extension",
  "Hip abduction",
  "Foot tapping",
  "Foot external rotation",
];

const KIN_PDF_VARS = [
  { re: /SPARC/i, key: "sparc" },
  { re: /Trunk\s*Ratio|Trunk\/Palm/i, key: "trunk_ratio" },
  { re: /Shoulder Vert|Shoulder elevation/i, key: "shoulder_vert_norm" },
  { re: /Elbow angle/i, key: "elbow_angle_mean" },
  { re: /Movement time|Duration/i, key: "movement_time_sec" },
  { re: /Peak Velocity/i, key: "peak_velocity_px_s" },
];

const WMFT_PDF = [
  { re: /Hand to Table \(front\).*Ability Rating/i, id: "1" },
  { re: /Hand to Box \(front\).*Ability Rating/i, id: "2" },
  { re: /Extend Elbow \(no weight\).*Ability Rating/i, id: "3" },
  { re: /Lift Can \(front\).*Ability Rating/i, id: "4" },
];

function dash(v) {
  return v === "—" || v === "-" || v === "" || v == null ? null : v;
}

function num(v) {
  const d = dash(v);
  if (d == null) return null;
  const n = parseFloat(String(d).replace(",", "."));
  return Number.isFinite(n) ? n : null;
}

function str(v) {
  if (v == null || v === "") return undefined;
  return String(v);
}

/** Normalize one patient record to NeuroLab fd shape. */
export function normalizeImportedPatient(raw) {
  const p = { ...raw };
  SECTION_KEYS.forEach((k) => {
    if (!p[k] || typeof p[k] !== "object") p[k] = {};
  });

  const d = { ...p.demographics };
  ["participantId", "group", "age", "sex", "strokeType", "side", "mas", "mrc", "height", "weight", "shoulderWidth", "timeSinceStroke"].forEach((f) => {
    if (d[f] != null && d[f] !== "") d[f] = String(d[f]);
  });
  p.demographics = d;

  const kin = { ...p.kinematics };
  const analysisResults = { ...(kin.analysisResults || {}) };
  const resultMap = [
    ["result_pre", "pre", "status_pre"],
    ["result_post", "post", "status_post"],
    ["result_baseline", "baseline", "status_baseline"],
  ];
  resultMap.forEach(([rk, pk, sk]) => {
    if (kin[rk] && typeof kin[rk] === "object" && Object.keys(kin[rk]).length > 0) {
      analysisResults[pk] = { ...kin[rk] };
      if (!kin[sk]) kin[sk] = "completed";
    }
  });
  if (Object.keys(analysisResults).length > 0) kin.analysisResults = analysisResults;
  p.kinematics = kin;

  return p;
}

/** Parse JSON text — array or single patient object. */
export function parsePatientJson(text) {
  const data = JSON.parse(text);
  const raw = Array.isArray(data) ? data[0] : data;
  if (!raw || typeof raw !== "object") throw new Error("JSON must contain a patient object or array");
  if (!raw.demographics && !raw.ipaq && !raw.vas) {
    throw new Error("Unrecognized JSON — export from NeuroLab Report section");
  }
  return normalizeImportedPatient(raw);
}

/** Extract all page text from a PDF file. */
export async function extractPdfText(file) {
  const buf = await file.arrayBuffer();
  const pdf = await pdfjsLib.getDocument({ data: buf }).promise;
  const parts = [];
  for (let i = 1; i <= pdf.numPages; i++) {
    const page = await pdf.getPage(i);
    const content = await page.getTextContent();
    parts.push(content.items.map((it) => it.str).join(" "));
  }
  return parts.join("\n");
}

function findKviqIndex(label) {
  const norm = label.toLowerCase().replace(/[–—]/g, "-").trim();
  for (let i = 0; i < KVIQ_LABELS.length; i++) {
    const k = KVIQ_LABELS[i].toLowerCase().replace(/[–—]/g, "-");
    if (norm.includes(k) || k.includes(norm)) return i;
  }
  return -1;
}

/** Parse NeuroLab Clinical Assessment Report PDF text. */
export function parseClinicalReportPdf(text) {
  const patient = {
    demographics: {},
    ipaq: {},
    vas: {},
    vams: {},
    motorchange: {},
    kgia: {},
    wmft: {},
    kinematics: {},
  };

  if (/AOMI Group/i.test(text)) patient.demographics.group = "1";
  else if (/Control Group/i.test(text)) patient.demographics.group = "2";

  const idM = text.match(/ID:\s*(\d+)/i);
  if (idM) patient.demographics.participantId = idM[1];

  const dateLine = text.match(/\d{1,2}\s+\w{3}\s+\d{4}/);
  if (dateLine) {
    const after = text.slice(text.indexOf(dateLine[0]) + dateLine[0].length, text.indexOf(dateLine[0]) + dateLine[0].length + 80);
    const nameM = after.match(/([A-Za-zÀ-ÿ][A-Za-zÀ-ÿ\s'-]{1,40})/);
    if (nameM) patient.demographics.name = nameM[1].trim().split(/\s{2,}/)[0];
  }

  const ageM = text.match(/AGE[\s\S]{0,30}?(\d{2})\s*yrs/i) || text.match(/\b(\d{2})\s*yrs\b/);
  if (ageM) patient.demographics.age = ageM[1];

  if (/\bFemale\b/i.test(text)) patient.demographics.sex = "2";
  else if (/\bMale\b/i.test(text)) patient.demographics.sex = "1";

  if (/\bIschemic\b/i.test(text)) patient.demographics.strokeType = "1";
  else if (/\bHemorrhagic\b/i.test(text)) patient.demographics.strokeType = "2";

  if (/AFFECTED SIDE[\s\S]{0,20}?\bLeft\b/i.test(text)) patient.demographics.side = "1";
  else if (/AFFECTED SIDE[\s\S]{0,20}?\bRight\b/i.test(text)) patient.demographics.side = "2";

  const masM = text.match(/\bMAS\b[\s\n]+(0|1\+|1|2|3|4)\b/);
  if (masM) patient.demographics.mas = masM[1];

  const mrcM = text.match(/\bMRC\b[\s\n]+(2|3|4|5)\b/);
  if (mrcM) patient.demographics.mrc = mrcM[1];

  const ipaqRows = [
    { key: "light", re: /Light activity[^\d]*(\d+)\s+(\d+)/i },
    { key: "sitting", re: /Total daily sitting time[^\d]*(\d+)\s+(\d+)/i },
    { key: "extra", re: /Additional \(cycling[^\d]*(\d+)\s+(\d+)/i },
  ];
  ipaqRows.forEach(({ key, re }) => {
    const m = text.match(re);
    if (m) patient.ipaq[key] = { gun: m[1], sure: m[2] };
  });

  const vasRest = text.match(/Pain at Rest\s+([\d.]+|—)\s+([\d.]+|—)/i);
  if (vasRest) {
    patient.vas.rest = {};
    if (dash(vasRest[1]) != null) patient.vas.rest.pre = String(vasRest[1]);
    if (dash(vasRest[2]) != null) patient.vas.rest.post = String(vasRest[2]);
  }
  const vasAct = text.match(/Pain During Activity\s+([\d.]+|—)\s+([\d.]+|—)/i);
  if (vasAct) {
    patient.vas.activity = {};
    if (dash(vasAct[1]) != null) patient.vas.activity.pre = String(vasAct[1]);
    if (dash(vasAct[2]) != null) patient.vas.activity.post = String(vasAct[2]);
  }
  const vasNight = text.match(/Night Pain\s+([\d.]+|—)\s+([\d.]+|—)/i);
  if (vasNight) {
    patient.vas.night = {};
    if (dash(vasNight[1]) != null) patient.vas.night.pre = String(vasNight[1]);
    if (dash(vasNight[2]) != null) patient.vas.night.post = String(vasNight[2]);
  }

  const mcNarr = text.match(/muscle control changed from (\d+) to (\d+)/i);
  if (mcNarr) {
    patient.motorchange.control = mcNarr[1];
    patient.motorchange.difference = mcNarr[2];
  } else {
    const mcTbl = text.match(/Felt Difference\s+(\d+)\s+(\d+)/i);
    if (mcTbl) {
      patient.motorchange.control = mcTbl[1];
      patient.motorchange.difference = mcTbl[2];
    }
  }

  const kviqRe = /(Visual|Kinesthetic):\s*([^\n]+?)\s+([\d.]+|—)\s+([\d.]+|—)/gi;
  let km;
  while ((km = kviqRe.exec(text)) !== null) {
    const typeKey = km[1].toLowerCase() === "visual" ? "gorsel" : "kinestetik";
    const idx = findKviqIndex(km[2]);
    if (idx < 0) continue;
    const cellKey = `${idx}_${typeKey}`;
    patient.kgia[cellKey] = patient.kgia[cellKey] || {};
    if (dash(km[3]) != null) patient.kgia[cellKey].once = String(km[3]);
    if (dash(km[4]) != null) patient.kgia[cellKey].sonra = String(km[4]);
  }

  WMFT_PDF.forEach(({ re, id }) => {
    const m = text.match(new RegExp(re.source + "[\\s\\S]{0,40}?(\\d+|—)\\s+(\\d+|—)", "i"));
    if (!m) return;
    patient.wmft[id] = { pre: {}, post: {} };
    if (dash(m[1]) != null) patient.wmft[id].pre.rating = String(m[1]);
    if (dash(m[2]) != null) patient.wmft[id].post.rating = String(m[2]);
  });

  const kin = {};
  KIN_PDF_VARS.forEach(({ re, key }) => {
    const m = text.match(new RegExp(re.source + "[\\s↓↑]*\\s*\\S*\\s+([\\d.]+)\\s+([\\d.]+)\\s+([\\d.]+)", "i"));
    if (!m) return;
    if (!kin.result_pre) kin.result_pre = {};
    if (!kin.result_post) kin.result_post = {};
    if (!kin.result_baseline) kin.result_baseline = {};
    kin.result_pre[key] = num(m[1]);
    kin.result_post[key] = num(m[2]);
    kin.result_baseline[key] = num(m[3]);
    kin.status_pre = "completed";
    kin.status_post = "completed";
    kin.status_baseline = "completed";
  });
  patient.kinematics = kin;

  return normalizeImportedPatient(patient);
}

/** Import from File — JSON or PDF. */
export async function importPatientFile(file) {
  const name = (file.name || "").toLowerCase();
  if (name.endsWith(".json")) {
    return parsePatientJson(await file.text());
  }
  if (name.endsWith(".pdf")) {
    // Prefer server-side parsing (more robust than browser pdfjs).
    try {
      const fd = new FormData();
      fd.append("file", file);
      const res = await fetch("/api/parse-pdf", { method: "POST", body: fd });
      const data = await res.json();
      if (data.success && data.patient) {
        return normalizeImportedPatient(data.patient);
      }
    } catch (err) {
      console.warn("Server-side PDF parse failed, falling back to browser:", err);
    }
    const text = await extractPdfText(file);
    return parseClinicalReportPdf(text);
  }
  throw new Error("Supported formats: .json (NeuroLab export) or .pdf (Clinical Report)");
}

export function buildImportRecord(normalized) {
  const hasPre = !!(normalized.vas?.rest?.pre || normalized.motorchange?.control || normalized.vams?.happy?.pre);
  const hasPost = !!(normalized.vas?.rest?.post || normalized.motorchange?.difference || normalized.vams?.happy?.post);
  const pid = normalized.demographics?.participantId;
  const existing = pid
    ? (() => {
        try {
          const list = JSON.parse(localStorage.getItem("stroke_rehab_patients_v6") || "[]");
          return list.find((p) => p.demographics?.participantId === pid);
        } catch {
          return null;
        }
      })()
    : null;

  return {
    ...normalized,
    _id: existing?._id || `import_${Date.now()}`,
    _savedAt: new Date().toISOString(),
    _hasPre: existing?._hasPre || hasPre,
    _hasPost: existing?._hasPost || hasPost,
  };
}
