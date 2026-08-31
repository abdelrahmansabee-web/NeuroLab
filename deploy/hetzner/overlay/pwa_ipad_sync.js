/* Home Screen app only: upload overlay validation videos into Drive patient folders. */
(function () {
  function standalone() {
    return (
      (window.matchMedia && window.matchMedia("(display-mode: standalone)").matches) ||
      window.navigator.standalone === true
    );
  }
  if (!standalone()) return;
  if ((location.pathname || "").indexOf("sync-ipad") !== -1) return;
  if ((location.pathname || "").indexOf("connect-drive") !== -1) return;

  var DB = "neurolab_validation_v1";
  var STORE = "artifacts";
  var FINGERPRINT_KEY = "nl_pwa_drive_ok_v1";
  var syncing = false;

  function token() {
    try {
      return localStorage.getItem("neurolab_token");
    } catch (e) {
      return null;
    }
  }

  function authHeaders() {
    var headers = {};
    var t = token();
    if (t) headers.Authorization = "Bearer " + t;
    return headers;
  }

  function blobSize(blob) {
    return blob instanceof Blob && blob.size ? blob.size : 0;
  }

  function loadFingerprints() {
    try {
      var raw = localStorage.getItem(FINGERPRINT_KEY);
      var parsed = raw ? JSON.parse(raw) : {};
      return parsed && typeof parsed === "object" ? parsed : {};
    } catch (e) {
      return {};
    }
  }

  function saveFingerprints(map) {
    try {
      localStorage.setItem(FINGERPRINT_KEY, JSON.stringify(map));
    } catch (e) {}
  }

  function fingerprint(rec) {
    return String(rec.patientKey || rec.id || "anon") + "|" + String(rec.phase || "") + "|" + String(blobSize(rec.unifiedVideoBlob));
  }

  function openDb() {
    return new Promise(function (resolve, reject) {
      var req = indexedDB.open(DB, 1);
      req.onerror = function () {
        reject(req.error || new Error("IndexedDB open failed"));
      };
      req.onsuccess = function () {
        resolve(req.result);
      };
      req.onupgradeneeded = function () {
        var db = req.result;
        if (!db.objectStoreNames.contains(STORE)) db.createObjectStore(STORE, { keyPath: "id" });
      };
    });
  }

  function getAll(db) {
    return new Promise(function (resolve, reject) {
      var tx = db.transaction(STORE, "readonly");
      var req = tx.objectStore(STORE).getAll();
      req.onsuccess = function () {
        resolve(req.result || []);
      };
      req.onerror = function () {
        reject(req.error);
      };
    });
  }

  function statusEl() {
    return document.getElementById("nl-pwa-sync-status");
  }

  function setStatus(text, kind) {
    var el = statusEl();
    if (!el) return;
    el.textContent = text;
    el.style.color = kind === "err" ? "#ffb4b4" : kind === "ok" ? "#8ee0b5" : "#fff";
  }

  function driveOk(body) {
    return !!(body && body.drive && body.drive.ok);
  }

  function uploadRecord(rec) {
    var blob = rec.unifiedVideoBlob;
    if (!blobSize(blob)) {
      return Promise.resolve({ skipped: true, reason: "no_validation_video" });
    }
    var fd = new FormData();
    fd.append("patientKey", rec.patientKey || rec.id || "anon");
    fd.append("phase", rec.phase || "unknown");
    if (rec.unifiedVideoFilename) fd.append("unifiedVideoFilename", rec.unifiedVideoFilename);
    fd.append("unifiedVideo", blob, "unified.mp4");
    return fetch("/api/validation-cache", {
      method: "POST",
      body: fd,
      credentials: "same-origin",
      headers: authHeaders(),
    }).then(function (res) {
      return res.json().catch(function () {
        return {};
      }).then(function (body) {
        if (!res.ok) throw new Error(body.detail || "HTTP " + res.status);
        return body;
      });
    });
  }

  function uploadPatients() {
    try {
      var dump = {};
      var keys = ["stroke_rehab_patients_v6", "neuro_kin_results", "neuro_fd_data", "neurolab_token"];
      for (var i = 0; i < keys.length; i++) dump[keys[i]] = localStorage.getItem(keys[i]);
      var fd = new FormData();
      fd.append("payload", new Blob([JSON.stringify(dump)], { type: "application/json" }), "localstorage.json");
      return fetch("/api/ipad-localstorage", {
        method: "POST",
        body: fd,
        credentials: "same-origin",
        headers: authHeaders(),
      });
    } catch (e) {
      return Promise.resolve(null);
    }
  }

  function sendReport(report) {
    try {
      return fetch("/api/ipad-sync-report", {
        method: "POST",
        credentials: "same-origin",
        headers: Object.assign({ "Content-Type": "application/json" }, authHeaders()),
        body: JSON.stringify(report),
      });
    } catch (e) {
      return Promise.resolve(null);
    }
  }

  function syncVideos(force) {
    if (syncing) return Promise.resolve();
    syncing = true;
    setStatus("جاري رفع فيديوهات الفاليديشن…", "");
    return openDb()
      .then(getAll)
      .then(function (rows) {
        var seen = loadFingerprints();
        var uploaded = 0;
        var overlay = 0;
        var cameraOnly = 0;
        var failed = 0;
        var driveFail = 0;
        var lastDrive = "";
        var inventory = [];
        var chain = Promise.resolve();
        rows.forEach(function (rec) {
          var unified = blobSize(rec.unifiedVideoBlob);
          var original = blobSize(rec.originalVideoBlob);
          inventory.push({
            patientKey: rec.patientKey || rec.id || "anon",
            phase: rec.phase || "",
            unifiedBytes: unified,
            originalBytes: original,
          });
          chain = chain.then(function () {
            if (!unified) {
              if (original) cameraOnly += 1;
              return;
            }
            overlay += 1;
            var key = fingerprint(rec);
            if (!force && seen[key]) {
              uploaded += 1;
              return;
            }
            return uploadRecord(rec)
              .then(function (body) {
                if (body && body.skipped) {
                  driveFail += 1;
                  lastDrive = body.reason || "skipped";
                  return;
                }
                if (!driveOk(body)) {
                  driveFail += 1;
                  lastDrive = ((body.drive && (body.drive.reason || body.drive.error)) || body.drive_error || "drive_failed");
                  return;
                }
                seen[key] = Date.now();
                saveFingerprints(seen);
                uploaded += 1;
              })
              .catch(function (err) {
                failed += 1;
                lastDrive = (err && err.message) || "upload_failed";
              });
          });
        });
        return chain.then(function () {
          return {
            uploaded: uploaded,
            overlay: overlay,
            cameraOnly: cameraOnly,
            failed: failed,
            driveFail: driveFail,
            lastDrive: lastDrive,
            total: rows.length,
            inventory: inventory,
          };
        });
      })
      .then(function (stats) {
        return uploadPatients()
          .then(function () {
            return sendReport(stats);
          })
          .then(function () {
            return stats;
          });
      })
      .then(function (stats) {
        if (stats.failed) {
          setStatus("فشل رفع " + stats.failed + " فيديو. اضغطي تاني. " + (stats.lastDrive || ""), "err");
        } else if (stats.driveFail) {
          setStatus("الأوفرلاي وصل السيرفر ومقدرش يكتب الدرايف: " + (stats.lastDrive || "خطأ"), "err");
        } else if (stats.uploaded) {
          setStatus("اترفع " + stats.uploaded + " فيديو أوفرلاي على ملفات المرضى في الدرايف", "ok");
        } else if (stats.cameraOnly && !stats.overlay) {
          setStatus("في التطبيق فيديو كاميرا بس. Generate Unified لكل مرحلة وبعدين ارفعي. الدرايف فاضي من غير أوفرلاي.", "err");
        } else if (stats.total) {
          setStatus("مفيش فيديو أوفرلاي في الكاش. اعملي Generate Unified بعدين ارفعي.", "err");
        } else {
          setStatus("مفيش فيديو فاليديشن في التطبيق", "");
        }
      })
      .catch(function (err) {
        setStatus("فشل الرفع: " + ((err && err.message) || "خطأ"), "err");
      })
      .then(function () {
        syncing = false;
      });
  }

  function link(href, text) {
    var a = document.createElement("a");
    a.href = href;
    a.textContent = text;
    a.setAttribute("dir", "rtl");
    a.style.cssText =
      "display:inline-block;padding:8px 12px;border-radius:10px;" +
      "background:rgba(0,0,0,.5);color:#fff;font:15px/1.3 system-ui,sans-serif;" +
      "text-decoration:none;";
    return a;
  }

  function mount() {
    if (document.getElementById("nl-pwa-sync")) return;
    var wrap = document.createElement("div");
    wrap.id = "nl-pwa-sync";
    wrap.setAttribute("dir", "rtl");
    wrap.style.cssText =
      "position:fixed;z-index:2147483000;bottom:12px;right:12px;display:flex;" +
      "flex-direction:column;gap:8px;align-items:flex-end;";
    wrap.appendChild(link("/connect-drive", "ربط الدرايف"));
    var btn = document.createElement("button");
    btn.type = "button";
    btn.id = "nl-pwa-sync-btn";
    btn.textContent = "رفع الفاليديشن للدرايف";
    btn.setAttribute("dir", "rtl");
    btn.style.cssText =
      "display:inline-block;padding:8px 12px;border-radius:10px;border:0;" +
      "background:rgba(0,0,0,.5);color:#fff;font:15px/1.3 system-ui,sans-serif;";
    btn.addEventListener("click", function () {
      syncVideos(true);
    });
    wrap.appendChild(btn);
    var status = document.createElement("div");
    status.id = "nl-pwa-sync-status";
    status.setAttribute("dir", "rtl");
    status.style.cssText = "max-width:260px;font:12px/1.35 system-ui,sans-serif;color:#fff;text-align:right;";
    wrap.appendChild(status);
    document.body.appendChild(wrap);
  }

  if (document.body) mount();
  else document.addEventListener("DOMContentLoaded", mount);

  function start() {
    setTimeout(function () {
      syncVideos(false);
    }, 2500);
  }
  if (document.readyState === "complete") start();
  else window.addEventListener("load", start);
  document.addEventListener("visibilitychange", function () {
    if (!document.hidden) syncVideos(false);
  });
  window.addEventListener("online", function () {
    syncVideos(false);
  });
})();
