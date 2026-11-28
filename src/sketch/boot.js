/* Anabasis sketch frame, last script: start Excalidraw with the drawing the page sends, and answer the page. It
   talks only to the window that holds it, in plain data, and sends back the drawing and a picture of it. */
(function () {
  var api = null, ready = false;
  function send(m) { m.sk = 1; parent.postMessage(m, '*'); }
  window.addEventListener('message', function (e) {
    if (e.source !== parent) return;
    var m = e.data || {};
    if (m.skInit && !ready) {
      ready = true;
      var root = ReactDOM.createRoot(document.getElementById('root')), s = m.scene;
      root.render(React.createElement(ExcalidrawLib.Excalidraw, {
        theme: m.theme === 'dark' ? 'dark' : 'light',
        initialData: s ? { elements: s.elements, appState: Object.assign({}, s.appState || {}), files: s.files || {} } : { appState: { viewBackgroundColor: '#ffffff' } },
        excalidrawAPI: function (a) { api = a; setTimeout(function () { send({ skReady: 1 }); }, 50); },
        UIOptions: { canvasActions: { loadScene: false, saveToActiveFile: false, export: false, saveAsImage: false, toggleTheme: false } },
        onChange: function () { send({ skChange: 1 }); },
        onLinkOpen: function (el, ev) { ev.preventDefault(); }
      }));
    }
    if (m.skGet && api) {
      var els = api.getSceneElements(), st = api.getAppState(), files = api.getFiles();
      if (!els.length) { send({ skScene: { elements: [], files: {}, appState: {} }, png: '' }); return; }
      ExcalidrawLib.exportToBlob({
        elements: els, files: files, mimeType: 'image/png',
        appState: Object.assign({}, st, { exportBackground: true, exportWithDarkMode: false, viewBackgroundColor: st.viewBackgroundColor || '#ffffff' }),
        getDimensions: function (w, h) { var k = Math.min(2, 2400 / Math.max(w, h)); return { width: Math.round(w * k), height: Math.round(h * k), scale: k }; }
      }).then(function (b) { var r = new FileReader(); r.onload = function () { send({ skScene: { elements: els, files: files, appState: { viewBackgroundColor: st.viewBackgroundColor, gridSize: st.gridSize } }, png: r.result }); }; r.readAsDataURL(b); })
        .catch(function (err) { send({ skErr: String((err && err.message) || err) }); });
    }
  });
  send({ skBoot: 1 });
})();
