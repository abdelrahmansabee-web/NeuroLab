/**
 * Clinic Excel exports: one workbook per clinical task, task-core kinematic
 * columns only. Archived patients/sessions are never included.
 */
import * as XLSX from "xlsx";
import {
  CLINICAL_MOVEMENT_TASKS,
  clinicalTaskById,
  coreMetricKeysForTask,
} from "./clinicalTasks";
import {
  DEMO_SPSS_KEYS,
  exportDemographicsForSpss,
  getPatientKinPhase,
  KINEMATIC_VARS,
  pickKinField,
} from "./analysisPlan";

const DEFAULT_TASK_ID = "study_reach_grasp";
const PHASES = ["pre", "post", "baseline"];

function isArchivedPatient(p) {
  return !!(p && p._archived);
}

export function activePatientsOnly(list) {
  return (list || []).filter((p) => p && typeof p === "object" && !isArchivedPatient(p));
}

function resolveResultTaskId(result) {
  if (!result || typeof result !== "object") return "";
  const raw = result.clinical_task || result.clinicalTask || "";
  return String(raw || "").trim().toLowerCase();
}

/** Task ids present on this patient's kinematics (legacy blank → study_reach_grasp). */
export function patientClinicalTaskIds(patient) {
  const ids = new Set();
  let sawAnyPhase = false;
  PHASES.forEach((phase) => {
    const m = getPatientKinPhase(patient, phase);
    if (!m) return;
    sawAnyPhase = true;
    ids.add(resolveResultTaskId(m) || DEFAULT_TASK_ID);
  });
  if (!sawAnyPhase) return [];
  return [...ids];
}

export function kinematicKeysForTask(taskId) {
  const id = String(taskId || DEFAULT_TASK_ID).toLowerCase();
  const core = coreMetricKeysForTask(id) || [];
  const known = new Set(KINEMATIC_VARS.map((v) => v.key));
  return core.filter((k) => known.has(k) || k === "task_complete");
}

function kinCell(m, key) {
  if (!m) return "";
  const v = pickKinField(m, key);
  return v !== null && v !== undefined ? v : "";
}

function phaseMetricsForTask(patient, taskId) {
  const want = String(taskId || DEFAULT_TASK_ID).toLowerCase();
  const out = { pre: null, post: null, baseline: null };
  PHASES.forEach((phase) => {
    const m = getPatientKinPhase(patient, phase);
    if (!m) return;
    const resolved = resolveResultTaskId(m) || DEFAULT_TASK_ID;
    if (resolved === want) out[phase === "baseline" ? "baseline" : phase] = m;
  });
  return out;
}

export function patientHasTaskData(patient, taskId) {
  const phases = phaseMetricsForTask(patient, taskId);
  return !!(phases.pre || phases.post || phases.baseline);
}

/** One row: demographics + only this task's kinematic Pre/Post/Healthy columns. */
export function buildTaskRow(patient, taskId) {
  if (!patient || isArchivedPatient(patient)) return null;
  const d = patient.demographics || {};
  if (!d.participantId && !d.name) return null;
  if (!patientHasTaskData(patient, taskId)) return null;

  const keys = kinematicKeysForTask(taskId);
  const phases = phaseMetricsForTask(patient, taskId);
  const row = {
    ...exportDemographicsForSpss(d),
    ClinicalTask: String(taskId || DEFAULT_TASK_ID),
    ClinicalTaskLabel: clinicalTaskById(taskId).label || String(taskId || ""),
  };

  keys.forEach((key) => {
    row[`${key}_Pre`] = kinCell(phases.pre, key);
    row[`${key}_Post`] = kinCell(phases.post, key);
    row[`${key}_Healthy`] = kinCell(phases.baseline, key);
  });
  return row;
}

export function buildTaskDataset(patients, taskId) {
  return activePatientsOnly(patients)
    .map((p) => buildTaskRow(p, taskId))
    .filter(Boolean);
}

export function excelFileNameForTask(taskId) {
  const task = clinicalTaskById(taskId);
  const id = String(task?.id || taskId || DEFAULT_TASK_ID);
  const safe = id.replace(/[^\w.-]+/g, "_");
  return `${safe}.xlsx`;
}

function orderedColumns(sampleRow, taskId) {
  if (!sampleRow) return [];
  const keys = kinematicKeysForTask(taskId);
  const kinCols = [];
  keys.forEach((key) => {
    kinCols.push(`${key}_Pre`, `${key}_Post`, `${key}_Healthy`);
  });
  const head = [
    ...DEMO_SPSS_KEYS,
    "ClinicalTask",
    "ClinicalTaskLabel",
  ].filter((k) => Object.prototype.hasOwnProperty.call(sampleRow, k));
  const rest = Object.keys(sampleRow).filter(
    (k) => !head.includes(k) && !kinCols.includes(k)
  );
  return [...head, ...kinCols, ...rest];
}

export function workbookBlobForTask(patients, taskId) {
  const rows = buildTaskDataset(patients, taskId);
  if (!rows.length) return null;
  const cols = orderedColumns(rows[0], taskId);
  const sheetRows = rows.map((row) => {
    const ordered = {};
    cols.forEach((c) => {
      ordered[c] = row[c];
    });
    return ordered;
  });
  const wb = XLSX.utils.book_new();
  const ws = XLSX.utils.json_to_sheet(sheetRows, { header: cols });
  ws["!cols"] = cols.map((c) => ({ wch: Math.min(28, Math.max(10, String(c).length + 2)) }));
  const sheetName = String(taskId || "task").slice(0, 31);
  XLSX.utils.book_append_sheet(wb, ws, sheetName);
  const out = XLSX.write(wb, { bookType: "xlsx", type: "array" });
  return new Blob([out], {
    type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
  });
}

/**
 * Build one Excel blob per clinical task that has active (non-archived) data.
 * @returns {{ taskId: string, label: string, fileName: string, blob: Blob, rowCount: number }[]}
 */
export function buildAllTaskExcelFiles(patients) {
  const active = activePatientsOnly(patients);
  const files = [];
  CLINICAL_MOVEMENT_TASKS.forEach((task) => {
    const rows = buildTaskDataset(active, task.id);
    if (!rows.length) return;
    const blob = workbookBlobForTask(active, task.id);
    if (!blob) return;
    files.push({
      taskId: task.id,
      label: task.label,
      fileName: excelFileNameForTask(task.id),
      blob,
      rowCount: rows.length,
    });
  });
  return files;
}

/** Single-patient kinematics sheet rows for the patient's clinical task only. */
export function patientTaskKinSheetRows(patient) {
  if (!patient || isArchivedPatient(patient)) return [];
  const taskIds = patientClinicalTaskIds(patient);
  if (!taskIds.length) return [];
  const taskId = taskIds[0];
  const keys = kinematicKeysForTask(taskId);
  const byKey = Object.fromEntries(KINEMATIC_VARS.map((v) => [v.key, v]));
  const phases = phaseMetricsForTask(patient, taskId);
  return keys.map((key) => {
    const meta = byKey[key] || { key, label: key, unit: "" };
    return {
      taskId,
      name: meta.label || key,
      unit: meta.unit || "",
      pre: kinCell(phases.pre, key),
      post: kinCell(phases.post, key),
      healthy: kinCell(phases.baseline, key),
    };
  });
}
