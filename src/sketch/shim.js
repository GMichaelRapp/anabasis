/* Anabasis sketch frame, first script. The frame is sandboxed: scripts run, but it has no origin of its own, so it
   can't read the project, the page or this browser's storage. Excalidraw expects storage and a Node-style
   environment flag, so it gets harmless stand-ins, and a Trusted Types policy for the markup React writes. */
(function () {
  window.process = { env: { NODE_ENV: 'production' } };
  var mem = function () { var d = {}; return { getItem: function (k) { return Object.prototype.hasOwnProperty.call(d, k) ? d[k] : null; }, setItem: function (k, v) { d[k] = String(v); }, removeItem: function (k) { delete d[k]; }, clear: function () { d = {}; }, key: function (i) { return Object.keys(d)[i] || null; }, get length() { return Object.keys(d).length; } }; };
  ['localStorage', 'sessionStorage'].forEach(function (k) { var ok = false; try { ok = !!window[k]; } catch (e) {} if (!ok) Object.defineProperty(window, k, { value: mem(), configurable: true }); });
  try { if (window.trustedTypes && trustedTypes.createPolicy) trustedTypes.createPolicy('default', { createHTML: function (h) { return h; }, createScriptURL: function () { return null; }, createScript: function () { return null; } }); } catch (e) {}
})();
