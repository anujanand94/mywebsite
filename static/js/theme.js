/* theme.js — site-wide light/dark theme handler.
 *
 * Priority on first visit: localStorage 'site-theme' → OS prefers-color-scheme → dark default.
 * Persists user toggles to localStorage. Follows OS changes only if the user
 * has never picked one explicitly.
 *
 * Markup contract:
 *   <html data-theme="dark">  (or absent — defaults handled here)
 *   <button data-theme-toggle aria-label="Toggle theme">…</button>
 *
 * The toggle button's innerHTML is replaced with a moon or sun SVG to reflect
 * the currently-active theme.
 */
(function () {
  var html = document.documentElement;
  var KEY  = 'site-theme';

  var MOON = '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor"' +
             ' stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">' +
             '<path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg>';
  var SUN  = '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor"' +
             ' stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">' +
             '<circle cx="12" cy="12" r="4"/>' +
             '<path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41' +
             ' M2 12h2M20 12h2M4.93 19.07l1.41-1.41M17.66 6.34l1.41-1.41"/></svg>';

  function current() { return html.getAttribute('data-theme') || 'dark'; }
  function paint() {
    var t = current();
    document.querySelectorAll('[data-theme-toggle]').forEach(function (btn) {
      btn.innerHTML = (t === 'dark') ? MOON : SUN;
      btn.setAttribute('aria-pressed', t === 'light' ? 'true' : 'false');
      btn.setAttribute('title', t === 'dark' ? 'Switch to light mode' : 'Switch to dark mode');
    });
    window.dispatchEvent(new CustomEvent('site-theme-change', { detail: { theme: t } }));
  }

  // Resolve initial theme.
  var stored = (function () {
    try { return localStorage.getItem(KEY); } catch (e) { return null; }
  })();
  if (stored === 'light' || stored === 'dark') {
    html.setAttribute('data-theme', stored);
  } else if (window.matchMedia && window.matchMedia('(prefers-color-scheme: light)').matches) {
    html.setAttribute('data-theme', 'light');
  } else if (!html.hasAttribute('data-theme')) {
    html.setAttribute('data-theme', 'dark');
  }

  // Live-follow OS changes if the user hasn't picked one.
  if (window.matchMedia) {
    window.matchMedia('(prefers-color-scheme: light)').addEventListener('change', function (e) {
      var s = null;
      try { s = localStorage.getItem(KEY); } catch (_) {}
      if (s === 'light' || s === 'dark') return;
      html.setAttribute('data-theme', e.matches ? 'light' : 'dark');
      paint();
    });
  }

  // Wire toggles. Use event delegation so buttons added later still work.
  document.addEventListener('click', function (e) {
    var btn = e.target.closest && e.target.closest('[data-theme-toggle]');
    if (!btn) return;
    var next = current() === 'dark' ? 'light' : 'dark';
    html.setAttribute('data-theme', next);
    try { localStorage.setItem(KEY, next); } catch (_) {}
    paint();
  });

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', paint);
  } else {
    paint();
  }
})();
