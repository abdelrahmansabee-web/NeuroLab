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
  var busy = 0;
  var pendingAfterBusy = false;
  var lastForce = false;

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

  function requestUrl(arg) {
    if (typeof arg === "string") return arg;
    if (arg && arg.url) return String(arg.url);
    return "";
  }

  function isClinicJob(url) {
    var u = String(url || "");
    return u.indexOf("/analyze") !== -1 || u.indexOf("/unified-validation") !== -1;
  }

  if (!window.__nlDriveSyncFetchHook) {
    window.__nlDriveSyncFetchHook = true;
    var origFetch = window.fetch;
    window.fetch = function () {
      var job = isClinicJob(requestUrl(arguments[0]));
      if (job) busy += 1;
      var p = origFetch.apply(this, arguments);
      if (!job) return p;
      return Promise.resolve(p).then(
        function (res) {
          busy = Math.max(0, busy - 1);
          if (busy === 0 && pendingAfterBusy) {
            pendingAfterBusy = false;
            setTimeout(function () {
              syncVideos(lastForce);
            }, 2000);
          }
          return res;
        },
        function (err) {
          busy = Math.max(0, busy - 1);
          throw err;
        }
      );
    };
  }

  function quietFetch(url, opts) {
    return fetch(url, opts).then(
      function (res) {
        return res;
      },
      function () {
        return null;
      }
    );
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
    var el = document.getElementById("nl-pwa-sync-status");
    if (el) return el;
    el = document.createElement("div");
    el.id = "nl-pwa-sync-status";
    el.setAttribute("role", "status");
    el.style.cssText =
      "position:fixed;z-index:80;left:50%;bottom:24px;transform:translateX(-50%);" +
      "max-width:min(92vw,22rem);padding:8px 12px;border-radius:12px;" +
      "background:rgba(12,16,22,.88);color:#fff;font:13px/1.35 system-ui,sans-serif;" +
      "text-align:center;pointer-events:none;display:none;";
    document.body.appendChild(el);
    return el;
  }

  function setStatus(text, kind) {
    if (!document.body) return;
    var el = statusEl();
    if (!text) {
      el.style.display = "none";
      el.textContent = "";
      return;
    }
    el.textContent = text;
    el.style.color = kind === "err" ? "#ffb4b4" : kind === "ok" ? "#8ee0b5" : "#fff";
    el.style.display = "block";
    clearTimeout(el._hide);
    el._hide = setTimeout(function () {
      el.style.display = "none";
    }, 4000);
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
      return quietFetch("/api/ipad-localstorage", {
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
      return quietFetch("/api/ipad-sync-report", {
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
    lastForce = !!force;
    if (!force && busy > 0) {
      pendingAfterBusy = true;
      return Promise.resolve();
    }
    if (force && busy > 0) {
      pendingAfterBusy = true;
      return Promise.resolve();
    }
    if (syncing) return Promise.resolve();
    syncing = true;
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
            if (busy > 0) {
              pendingAfterBusy = true;
              return;
            }
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
            deferred: pendingAfterBusy,
          };
        });
      })
      .then(function (stats) {
        if (stats.deferred && busy > 0) return stats;
        return uploadPatients()
          .then(function () {
            return sendReport(stats);
          })
          .then(function () {
            return stats;
          });
      })
      .then(function (stats) {
        if (stats.deferred && busy > 0) {
          return;
        }
        if (stats.failed && force) {
          setStatus("Server is busy. Upload after analysis finishes.", "err");
        } else if (stats.driveFail && force) {
          setStatus("Overlay reached the server, but Drive did not save: " + (stats.lastDrive || "error"), "err");
        } else if (stats.uploaded && force) {
          setStatus(
            "Uploaded " + stats.uploaded + " validation video" + (stats.uploaded === 1 ? "" : "s") + " to Drive",
            "ok"
          );
        }
      })
      .catch(function () {
        if (busy > 0) {
          pendingAfterBusy = true;
          return;
        }
        if (force) {
          setStatus("Server is busy or the network dropped.", "err");
        }
      })
      .then(function () {
        syncing = false;
      });
  }

  function bindMenu() {
    window.__nlSyncVideos = function (force) {
      return syncVideos(!!force);
    };
    window.addEventListener("nl-upload-validation", function () {
      syncVideos(true);
    });
  }

  bindMenu();

  function start() {
    setTimeout(function () {
      syncVideos(false);
    }, 8000);
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
