/* Show Drive + iPad sync links only inside the Home Screen app (Safari storage is separate). */
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
    wrap.appendChild(link("/sync-ipad", "رفع فيديوهات الآيباد"));
    document.body.appendChild(wrap);
  }
  if (document.body) mount();
  else document.addEventListener("DOMContentLoaded", mount);
})();
