/* Show a sync-ipad link only inside the Home Screen app (Safari storage is separate). */
(function () {
  function standalone() {
    return (
      (window.matchMedia && window.matchMedia("(display-mode: standalone)").matches) ||
      window.navigator.standalone === true
    );
  }
  if (!standalone()) return;
  if ((location.pathname || "").indexOf("sync-ipad") !== -1) return;
  function mount() {
    if (document.getElementById("nl-pwa-sync")) return;
    var a = document.createElement("a");
    a.id = "nl-pwa-sync";
    a.href = "/sync-ipad";
    a.textContent = "رفع فيديوهات الآيباد";
    a.setAttribute("dir", "rtl");
    a.style.cssText =
      "position:fixed;z-index:2147483000;bottom:12px;right:12px;padding:8px 12px;" +
      "border-radius:10px;background:rgba(0,0,0,.5);color:#fff;font:15px/1.3 system-ui,sans-serif;" +
      "text-decoration:none;";
    document.body.appendChild(a);
  }
  if (document.body) mount();
  else document.addEventListener("DOMContentLoaded", mount);
})();
