/*
 * Judge plugin — Run-page mirror of manually-added judge laps.
 * Fills a <div class="judge-laps-panel" data-node="i"> under each node block
 * on the Run page with the laps a judge entered from the /judge pages for the
 * current race session. REST-only (polls /judge/api/laps/<i>); no socket use.
 */
(function () {
  'use strict';

  var POLL_MS = 2000;

  function p2(n) { return String(Math.floor(n)).padStart(2, '0'); }
  function p3(n) { return String(Math.floor(n)).padStart(3, '0'); }

  function fmt(ms) {
    ms = Math.max(0, ms);
    var m = Math.floor(ms / 60000);
    var s = Math.floor((ms % 60000) / 1000);
    var mil = ms % 1000;
    return (m > 0 ? m + ':' + p2(s) : s) + '.' + p3(mil);
  }

  function panels() {
    return Array.prototype.slice.call(document.querySelectorAll('.judge-laps-panel'));
  }

  function render(panel, laps) {
    if (!laps || !laps.length) {
      panel.innerHTML = '';
      panel.classList.remove('has-laps');
      return;
    }
    panel.classList.add('has-laps');

    var rows = '';
    for (var i = 0; i < laps.length; i++) {
      var lap = laps[i];
      rows += '<tr>' +
        '<td class="jl-n">' + i + '</td>' +
        '<td class="jl-ts">' + fmt(lap.lap_time_stamp) + '</td>' +
        '<td class="jl-lt">' + (i === 0 ? '—' : fmt(lap.lap_time)) + '</td>' +
        '</tr>';
    }
    panel.innerHTML =
      '<div class="jl-head"><span class="jl-dot"></span>Judge laps' +
      '<span class="jl-count">' + laps.length + '</span></div>' +
      '<table class="jl-table"><tbody>' + rows + '</tbody></table>';
  }

  function refresh() {
    panels().forEach(function (panel) {
      var node = panel.getAttribute('data-node');
      fetch('/judge/api/laps/' + node)
        .then(function (r) { return r.json(); })
        .then(function (laps) { render(panel, laps); })
        .catch(function () {});
    });
  }

  function injectStyles() {
    var css =
      '.judge-laps-panel{display:none}' +
      '.judge-laps-panel.has-laps{display:block;margin-top:.4rem;border:1px solid rgba(238,122,40,.45);' +
        'border-radius:6px;background:rgba(238,122,40,.07);overflow:hidden}' +
      '.judge-laps-panel .jl-head{display:flex;align-items:center;gap:.4rem;padding:.3rem .55rem;' +
        'font-size:.66rem;font-weight:700;letter-spacing:.08em;text-transform:uppercase;color:#ee7a28;' +
        'border-bottom:1px solid rgba(238,122,40,.3)}' +
      '.judge-laps-panel .jl-dot{width:7px;height:7px;border-radius:50%;background:#ee7a28;display:inline-block}' +
      '.judge-laps-panel .jl-count{margin-left:auto;font-weight:600;opacity:.8}' +
      '.judge-laps-panel .jl-table{width:100%;border-collapse:collapse;font-size:.8rem}' +
      '.judge-laps-panel .jl-table td{padding:.25rem .55rem;border-top:1px solid rgba(238,122,40,.15)}' +
      '.judge-laps-panel .jl-table tr:first-child td{border-top:none}' +
      '.judge-laps-panel .jl-n{width:1.6rem;font-weight:700;opacity:.6}' +
      '.judge-laps-panel .jl-ts{font-family:"SF Mono","Fira Code",Consolas,monospace}' +
      '.judge-laps-panel .jl-lt{text-align:right;font-family:"SF Mono","Fira Code",Consolas,monospace;opacity:.85}';
    var st = document.createElement('style');
    st.textContent = css;
    document.head.appendChild(st);
  }

  function init() {
    if (!panels().length) return;
    injectStyles();
    refresh();
    setInterval(refresh, POLL_MS);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
}());
