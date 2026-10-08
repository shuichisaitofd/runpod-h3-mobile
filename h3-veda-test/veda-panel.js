/* H3 Veda test panel (I2V only). Adds a Veda on/off switch and a sparsity setting to the H3 Mobile page.
   It rewrites the I2V workflow in the browser right after it is fetched; no server file is changed. */
(function () {
  'use strict';
  var KEY = 'h3veda_state_v1';
  var NODE_ID = '105:200';
  var GUIDER_ID = '105:16';
  var st = { on: false, pct: 90 };
  var opts = null;      // allowed sparsity values from ComfyUI (array of strings like "90%"), or null for free numbers
  var predictor = null; // predictor file name from ComfyUI
  var nodeState = 'checking'; // checking | ok | missing

  try { var saved = JSON.parse(localStorage.getItem(KEY) || 'null'); if (saved) { st.on = !!saved.on; st.pct = Number(saved.pct) || 90; } } catch (e) {}
  function save() { try { localStorage.setItem(KEY, JSON.stringify(st)); } catch (e) {} }
  function api(path) { return typeof window.apiUrl === 'function' ? window.apiUrl(path) : path; }
  function label() { return st.on ? 'Veda ' + st.pct + '%' : 'Veda OFF'; }

  // Rewrites an I2V API workflow so that it has Veda at st.pct, or none. Same shape as i2v.json.vedaNN.
  window.h3VedaApply = function (wf, state) {
    var s = state || st;
    var guider = wf && wf[GUIDER_ID];
    if (!guider || !guider.inputs) return wf;
    var src = guider.inputs.model;
    Object.keys(wf).forEach(function (id) {
      var n = wf[id];
      if (n && n.class_type === 'VedaSparseAttention') {
        if (guider.inputs.model && guider.inputs.model[0] === id) src = n.inputs.model;
        delete wf[id];
      }
    });
    guider.inputs.model = src;
    if (!s.on) return wf;
    wf[NODE_ID] = {
      inputs: { model: src, predictor: s.predictor || predictor || 'minimax_h3_t2va_veda_8nfe_600step_preview_fp8.safetensors',
        generated_sparsity: s.pct + '%', reference_sparsity: s.pct + '%', full_attention_layers: '', full_attention_steps: '', verbose: false },
      class_type: 'VedaSparseAttention', _meta: { title: 'Veda Sparse Attention (MiniMax H3)' }
    };
    guider.inputs.model = [NODE_ID, 0];
    return wf;
  };

  var baseFetch = window.fetch.bind(window);
  window.fetch = async function (input, init) {
    var url = typeof input === 'string' ? input : (input && input.url) || '';
    if (/\/h3-mobile\/api\/workflow\/i2v(?:[?#]|$)/.test(url)) {
      var res = await baseFetch(input, init);
      if (!res.ok) return res;
      try {
        var wf = window.h3VedaApply(await res.clone().json());
        return new Response(JSON.stringify(wf), { status: res.status, statusText: res.statusText, headers: res.headers });
      } catch (e) { return res; }
    }
    return baseFetch(input, init);
  };

  function loadNodeInfo() {
    baseFetch(api('/object_info/VedaSparseAttention')).then(function (r) { return r.ok ? r.json() : null; }).then(function (j) {
      var req = j && j.VedaSparseAttention && j.VedaSparseAttention.input && j.VedaSparseAttention.input.required;
      if (!req) { nodeState = 'missing'; render(); return; }
      nodeState = 'ok';
      var p = req.predictor && req.predictor[0];
      if (Array.isArray(p) && p.length) predictor = p.indexOf('minimax_h3_t2va_veda_8nfe_600step_preview_fp8.safetensors') >= 0 ? 'minimax_h3_t2va_veda_8nfe_600step_preview_fp8.safetensors' : p[0];
      if (Array.isArray(p) && !p.length) nodeState = 'nopredictor';
      var g = req.generated_sparsity && req.generated_sparsity[0];
      if (Array.isArray(g) && g.length) { opts = g.slice(); }
      render();
    }).catch(function () { nodeState = 'missing'; render(); });
  }

  var pill, panel;
  function css() {
    var s = document.createElement('style');
    s.textContent = '#vedaPill{position:fixed;right:10px;bottom:76px;z-index:99999;padding:10px 14px;border-radius:22px;border:0;font:600 14px/1 system-ui,sans-serif;color:#fff;background:#555;box-shadow:0 2px 8px rgba(0,0,0,.4)}' +
      '#vedaPill.on{background:#0a7d3b}' +
      '#vedaPanel{position:fixed;right:10px;bottom:128px;z-index:99999;width:min(320px,calc(100vw - 20px));padding:14px;border-radius:14px;background:#1c1c1e;color:#fff;font:14px/1.5 system-ui,sans-serif;box-shadow:0 4px 18px rgba(0,0,0,.6);display:none}' +
      '#vedaPanel h3{margin:0 0 8px;font-size:15px}#vedaPanel .row{display:flex;gap:8px;align-items:center;margin:8px 0}' +
      '#vedaPanel button{padding:10px 12px;border-radius:10px;border:1px solid #666;background:#2c2c2e;color:#fff;font-size:14px}' +
      '#vedaPanel button.sel{background:#0a7d3b;border-color:#0a7d3b}#vedaPanel input[type=range]{flex:1;height:32px}' +
      '#vedaPanel .note{font-size:12px;color:#bbb}#vedaPanel .warn{font-size:13px;color:#ffb4a8}';
    document.head.appendChild(s);
  }
  function snap(v) {
    if (!opts) return Math.min(99, Math.max(1, Math.round(v)));
    var nums = opts.map(function (o) { return parseInt(o, 10); });
    var best = nums[0];
    nums.forEach(function (n) { if (Math.abs(n - v) < Math.abs(best - v)) best = n; });
    return best;
  }
  function render() {
    if (!pill) return;
    pill.textContent = label();
    pill.className = st.on ? 'on' : '';
    if (panel.style.display === 'none') return;
    var lo = 10, hi = 99, step = 1;
    if (opts) { var nums = opts.map(function (o) { return parseInt(o, 10); }).filter(function (n) { return !isNaN(n); }); lo = Math.min.apply(null, nums); hi = Math.max.apply(null, nums); step = 1; }
    var warn = nodeState === 'missing' ? '<div class="warn">この Pod には Veda ノードが入っていません。ONにすると生成が失敗します。</div>' :
      nodeState === 'nopredictor' ? '<div class="warn">Veda の予測モデルファイルが見つかりません。</div>' :
      nodeState === 'checking' ? '<div class="note">Vedaの確認中…</div>' : '';
    panel.innerHTML = '<h3>Veda テスト(画像から動画のみ)</h3>' + warn +
      '<div class="row"><button id="vOff" class="' + (st.on ? '' : 'sel') + '">OFF</button><button id="vOn" class="' + (st.on ? 'sel' : '') + '">ON</button></div>' +
      '<div class="row"><span>スパース率</span><b id="vVal">' + st.pct + '%</b></div>' +
      '<div class="row"><input id="vRange" type="range" min="' + lo + '" max="' + hi + '" step="' + step + '" value="' + st.pct + '"></div>' +
      '<div class="row">' + [40, 70, 80, 90].map(function (n) { return '<button data-p="' + n + '">' + n + '</button>'; }).join('') + '</div>' +
      '<div class="note">次の生成から反映されます(生成中のものは変わりません)。数値が大きいほど計算を多く省きます(速くなる代わりに、画質が落ちることがあります)。</div>';
    panel.querySelector('#vOff').onclick = function () { st.on = false; save(); render(); };
    panel.querySelector('#vOn').onclick = function () { st.on = true; save(); render(); };
    panel.querySelector('#vRange').oninput = function (e) { st.pct = snap(Number(e.target.value)); panel.querySelector('#vVal').textContent = st.pct + '%'; save(); pill.textContent = label(); };
    Array.prototype.forEach.call(panel.querySelectorAll('button[data-p]'), function (b) { b.onclick = function () { st.pct = snap(Number(b.getAttribute('data-p'))); st.on = true; save(); render(); }; });
  }
  function init() {
    css();
    pill = document.createElement('button'); pill.id = 'vedaPill'; pill.type = 'button';
    panel = document.createElement('div'); panel.id = 'vedaPanel'; panel.style.display = 'none';
    pill.onclick = function () { panel.style.display = panel.style.display === 'none' ? 'block' : 'none'; render(); };
    document.body.appendChild(panel); document.body.appendChild(pill);
    render(); loadNodeInfo();
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init); else init();
})();
