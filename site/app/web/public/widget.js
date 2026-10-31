/* Bookly support widget: <script src=".../widget.js" data-tenant="lumen"></script> */
(function () {
  'use strict';
  var script = document.currentScript ||
    document.querySelector('script[data-tenant][src*="widget.js"]');
  if (!script) return;
  var tenant = script.getAttribute('data-tenant');
  if (!tenant) { if (window.console) console.warn('[bookly] data-tenant is required'); return; }
  var origin = new URL(script.src, window.location.href).origin;
  var color = script.getAttribute('data-color') || '#4f46e5';
  var label = script.getAttribute('data-label');
  var Z = 2147483000;

  var iframe = null, isOpen = false;

  function css(el, s) { el.style.cssText = s; return el; }

  var root = css(document.createElement('div'), 'position:fixed;right:20px;bottom:20px;z-index:' + Z + ';font-family:system-ui,-apple-system,Segoe UI,Roboto,sans-serif;');
  root.id = 'bookly-widget-root';

  var panel = css(document.createElement('div'), 'display:none;position:absolute;right:0;bottom:72px;width:380px;height:600px;max-height:calc(100vh - 140px);background:#fff;border-radius:16px;box-shadow:0 12px 40px rgba(0,0,0,.25);');
  panel.id = 'bookly-widget-panel';
  panel.setAttribute('role', 'dialog');
  panel.setAttribute('aria-label', 'Підтримка');

  var closeBtn = css(document.createElement('button'), 'position:absolute;top:-38px;right:0;z-index:2;width:30px;height:30px;border:0;border-radius:50%;background:rgba(0,0,0,.55);color:#fff;font-size:18px;line-height:30px;padding:0;cursor:pointer;');
  closeBtn.id = 'bookly-widget-close';
  closeBtn.type = 'button';
  closeBtn.setAttribute('aria-label', 'Закрити');
  closeBtn.innerHTML = '&times;';

  var btnWrap = css(document.createElement('div'), 'display:flex;align-items:center;justify-content:flex-end;gap:10px;');
  if (label) {
    var lab = css(document.createElement('span'), 'background:#fff;color:#111;padding:6px 12px;border-radius:999px;font-size:13px;box-shadow:0 2px 10px rgba(0,0,0,.2);');
    lab.id = 'bookly-widget-label';
    lab.textContent = label;
    btnWrap.appendChild(lab);
  }
  var btn = css(document.createElement('button'), 'width:56px;height:56px;border:0;border-radius:50%;background:' + color + ';color:#fff;cursor:pointer;padding:0;display:flex;align-items:center;justify-content:center;box-shadow:0 6px 20px rgba(0,0,0,.3);');
  btn.id = 'bookly-widget-button';
  btn.type = 'button';
  btn.setAttribute('aria-label', 'Підтримка');
  btn.setAttribute('aria-expanded', 'false');
  btn.innerHTML = '<svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>';
  btnWrap.appendChild(btn);

  panel.appendChild(closeBtn);
  root.appendChild(panel);
  root.appendChild(btnWrap);

  function layout() {
    var small = window.innerWidth < 480;
    if (small && isOpen) {
      css(root, 'position:fixed;left:0;top:0;right:0;bottom:0;z-index:' + Z + ';font-family:system-ui,sans-serif;');
      css(panel, 'display:block;position:absolute;left:0;top:0;width:100%;height:100%;background:#fff;border-radius:0;overflow:hidden;');
      btnWrap.style.display = 'none';
      closeBtn.style.top = '8px';
      closeBtn.style.right = '8px';
    } else {
      css(root, 'position:fixed;right:20px;bottom:20px;z-index:' + Z + ';font-family:system-ui,-apple-system,Segoe UI,Roboto,sans-serif;');
      css(panel, 'display:' + (isOpen ? 'block' : 'none') + ';position:absolute;right:0;bottom:72px;width:380px;height:600px;max-height:calc(100vh - 140px);background:#fff;border-radius:16px;box-shadow:0 12px 40px rgba(0,0,0,.25);');
      btnWrap.style.display = 'flex';
      closeBtn.style.top = '-38px';
      closeBtn.style.right = '0';
    }
  }

  function open() {
    if (!iframe) {
      iframe = css(document.createElement('iframe'), 'width:100%;height:100%;border:0;display:block;border-radius:16px;');
      iframe.id = 'bookly-widget-frame';
      iframe.title = 'Підтримка';
      iframe.src = origin + '/b/' + encodeURIComponent(tenant) + '/support?embed=1';
      panel.appendChild(iframe);
    }
    isOpen = true;
    btn.setAttribute('aria-expanded', 'true');
    layout();
  }
  function close() {
    isOpen = false;
    btn.setAttribute('aria-expanded', 'false');
    layout();
  }

  btn.addEventListener('click', function () { if (isOpen) { close(); } else { open(); } });
  closeBtn.addEventListener('click', close);
  window.addEventListener('resize', layout);

  function mount() { document.body.appendChild(root); }
  if (document.body) mount(); else document.addEventListener('DOMContentLoaded', mount);

  window.BooklyWidget = { open: open, close: close };
})();
