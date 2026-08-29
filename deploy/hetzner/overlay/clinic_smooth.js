(function () {
  var doc = document.documentElement;
  doc.classList.add("nl-clinic-smooth");

  var STYLE_ID = "nl-clinic-perf";
  var CSS =
    "html.nl-clinic-smooth,html.nl-clinic-smooth *,html.nl-clinic-smooth *::before,html.nl-clinic-smooth *::after{" +
    "backdrop-filter:none!important;-webkit-backdrop-filter:none!important}" +
    "html.nl-clinic-smooth .fixed.inset-0.z-0>.absolute.inset-0:first-child," +
    'html.nl-clinic-smooth [style*="blur(24px)"]{' +
    'filter:none!important;-webkit-filter:none!important;transform:none!important;background-image:url("/bg_soft.jpg")!important}';

  var GLASS =
    '.sidebar-shell,.glass-float,.content-shell,.section-header,.gselect-trigger,.gselect-menu,.app-topbar-glass,[class*="backdrop-blur"]';

  function styleTag() {
    var s = document.getElementById(STYLE_ID);
    if (!s) {
      s = document.createElement("style");
      s.id = STYLE_ID;
      s.textContent = CSS;
    }
    (document.body || doc).appendChild(s);
  }

  function killBackdrop(el) {
    if (!el || el.nodeType !== 1) return;
    el.style.setProperty("backdrop-filter", "none", "important");
    el.style.setProperty("-webkit-backdrop-filter", "none", "important");
  }

  function killBgFilter(el) {
    if (!el || el.nodeType !== 1) return;
    el.style.setProperty("filter", "none", "important");
    el.style.setProperty("-webkit-filter", "none", "important");
    el.style.setProperty("transform", "none", "important");
    el.style.setProperty("background-image", 'url("/bg_soft.jpg")', "important");
  }

  function sweep() {
    styleTag();
    doc.querySelectorAll(GLASS).forEach(killBackdrop);
    doc.querySelectorAll('[style*="blur(24px)"]').forEach(killBgFilter);
    var layer = doc.querySelector(".fixed.inset-0.z-0 > .absolute.inset-0");
    if (layer) killBgFilter(layer);
  }

  sweep();
  [50, 200, 600, 1500, 4000].forEach(function (ms) {
    setTimeout(sweep, ms);
  });
  document.addEventListener("DOMContentLoaded", sweep);
  window.addEventListener("load", sweep);
})();
