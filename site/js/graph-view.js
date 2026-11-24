// Visão do grafo: caixa de busca, botões, lista de resultados e o 3D (biblioteca 3d-force-graph).
// A busca fica em search.js e a derivação de nós/ligações em graph-model.js; aqui só há interface.
// O estado (busca, botões, câmera) fica em memória: fechar e reabrir o grafo não perde nada.

const AGView = (function () {
  const PALETTE = ["#d9791f", "#3f7d6e", "#2b6cb0", "#8e4ec6", "#c2415d", "#9a7b0a",
                   "#0e7490", "#b45309", "#4d7c0f", "#6b5b95", "#a3424b", "#457b9d",
                   "#5f6caf", "#2f855a", "#b7791f", "#9b2c7d"];
  const MODES = [["any", "Qualquer"], ["all", "Todas"], ["exact", "Exato"], ["text", "Texto"]];
  const LINKS = [["tags", "Tags como nós"], ["direct", "Ligações diretas"]];
  const MODE_HINT = {
    any: "Termos soltos são tags; entra o documento que tiver pelo menos uma.",
    all: "Termos soltos são tags; entra o documento que tiver todas.",
    exact: "Entra o documento cujas tags curadas são exatamente estas, nem mais nem menos.",
    text: "Termos soltos são trechos de texto (título, tags e corpo); todos precisam aparecer.",
  };

  const state = { mode: "any", link: "tags", auto: true, only: false, query: "" };
  let docs = [];
  let texts = new Map();
  let colors = new Map();
  let legend = [];
  let graph = null;
  let graphFailed = false;
  let graphKey = null;
  let result = { all: true, ids: [], matched: {}, terms: [] };
  let hi = null;      // Set de ids de documentos em destaque (null = sem busca)
  let hiTags = null;  // Set de tags em destaque
  const ui = {};

  const $ = (tag, cls, text) => {
    const e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text != null) e.textContent = text;
    return e;
  };

  function webglOk() {
    try {
      const c = document.createElement("canvas");
      return !!(c.getContext("webgl2") || c.getContext("webgl"));
    } catch (e) {
      return false;
    }
  }

  // ---------- montagem da interface ----------

  function segmented(options, key, onChange) {
    const wrap = $("div", "gv-seg");
    options.forEach(([value, label]) => {
      const b = $("button", "", label);
      b.type = "button";
      b.dataset.value = value;
      b.addEventListener("click", () => { state[key] = value; sync(); onChange(); });
      wrap.appendChild(b);
    });
    return wrap;
  }

  function check(label, key, onChange) {
    const l = $("label", "gv-check");
    const i = $("input");
    i.type = "checkbox";
    i.addEventListener("change", () => { state[key] = i.checked; onChange(); });
    l.append(i, document.createTextNode(" " + label));
    l.input = i;
    return l;
  }

  function build(root) {
    root.innerHTML = "";
    const bar = $("div", "gv-toolbar");
    const box = $("div", "gv-search");
    ui.input = $("input");
    ui.input.type = "text";
    ui.input.autocomplete = "off";
    ui.input.spellcheck = false;
    ui.input.placeholder = 'algoritmo 3d  ·  tag:gasflow -tag:x  ·  "trecho"';
    ui.suggest = $("div", "gv-suggest");
    ui.suggest.hidden = true;
    box.append(ui.input, ui.suggest);

    ui.modes = segmented(MODES, "mode", () => refresh());
    ui.links = segmented(LINKS, "link", () => refresh());
    ui.auto = check("Automáticas", "auto", () => refresh());
    ui.only = check("Só resultados", "only", () => refresh());
    ui.hint = $("div", "gv-hint");
    bar.append(box, ui.modes, ui.links, ui.auto, ui.only, ui.hint);

    // A biblioteca 3D limpa o elemento onde monta; por isso dica e legenda ficam ao lado dele, não dentro.
    const wrap = $("div", "gv-canvas");
    ui.canvas = $("div", "gv-mount");
    ui.legend = $("div", "gv-legend");
    wrap.append(ui.canvas, ui.legend, $("div", "gv-nav", "arraste: girar · roda: zoom · botão direito: mover"));

    const side = $("aside", "gv-results");
    ui.count = $("div", "gv-count");
    ui.error = $("div", "gv-error");
    ui.list = $("ul", "gv-list");
    side.append(ui.count, ui.error, ui.list);
    root.append(bar, wrap, side);

    drawLegend();

    ui.input.addEventListener("input", () => { state.query = ui.input.value; refresh(); showSuggestions(); });
    ui.input.addEventListener("click", showSuggestions);
    ui.input.addEventListener("keydown", onKey);
    ui.input.addEventListener("blur", () => setTimeout(() => { ui.suggest.hidden = true; }, 120));
    new ResizeObserver(resize).observe(wrap);
    sync();
  }

  function drawLegend() {
    ui.legend.innerHTML = "";
    legend.forEach(([label, color]) => {
      const row = $("div", "gv-legend-row");
      const dot = $("span", "gv-dot");
      dot.style.background = color;
      row.append(dot, document.createTextNode(label));
      ui.legend.appendChild(row);
    });
    const tagRow = $("div", "gv-legend-row");
    const tagDot = $("span", "gv-dot gv-dot-tag");
    tagRow.append(tagDot, document.createTextNode("tag"));
    ui.legend.appendChild(tagRow);
  }

  function sync() {
    ui.modes.querySelectorAll("button").forEach((b) => b.classList.toggle("on", b.dataset.value === state.mode));
    ui.links.querySelectorAll("button").forEach((b) => b.classList.toggle("on", b.dataset.value === state.link));
    ui.auto.input.checked = state.auto;
    ui.only.input.checked = state.only;
    ui.hint.textContent = MODE_HINT[state.mode];
  }

  // ---------- sugestões de tags ----------

  let sugIndex = -1;

  function currentToken() {
    const caret = ui.input.selectionStart == null ? ui.input.value.length : ui.input.selectionStart;
    const before = ui.input.value.slice(0, caret);
    const m = /[^\s()"]*$/.exec(before);
    return { start: m.index, end: caret, text: m[0] };
  }

  function showSuggestions() {
    const tok = currentToken();
    let text = tok.text.replace(/^-/, "");
    let asTag = state.mode !== "text";
    const op = /^([a-z]+):/.exec(text);
    if (op) { asTag = op[1] === "tag"; text = text.slice(op[0].length); }
    ui.suggest.innerHTML = "";
    sugIndex = -1;
    if (!asTag || !text) { ui.suggest.hidden = true; return; }
    const list = AGSearch.suggest(text, docs, state.auto, 8);
    if (!list.length || (list.length === 1 && list[0].tag === AGSearch.normTag(text))) { ui.suggest.hidden = true; return; }
    list.forEach(({ tag, count }) => {
      const b = $("button", "", tag);
      b.type = "button";
      b.append($("span", "gv-sug-n", String(count)));
      b.addEventListener("mousedown", (e) => { e.preventDefault(); pick(tag); });
      ui.suggest.appendChild(b);
    });
    ui.suggest.hidden = false;
  }

  function pick(tag) {
    const tok = currentToken();
    const raw = tok.text;
    const neg = raw.startsWith("-") ? "-" : "";
    const rest = raw.replace(/^-/, "");
    const op = /^([a-z]+):/.exec(rest);
    const prefix = neg + (op ? op[0] : "");
    const v = ui.input.value;
    ui.input.value = v.slice(0, tok.start) + prefix + tag + " " + v.slice(tok.end);
    state.query = ui.input.value;
    ui.suggest.hidden = true;
    ui.input.focus();
    refresh();
  }

  function onKey(e) {
    const items = [...ui.suggest.querySelectorAll("button")];
    if (ui.suggest.hidden || !items.length) return;
    if (e.key === "ArrowDown" || e.key === "ArrowUp") {
      e.preventDefault();
      sugIndex = (sugIndex + (e.key === "ArrowDown" ? 1 : -1) + items.length) % items.length;
      items.forEach((b, i) => b.classList.toggle("on", i === sugIndex));
    } else if ((e.key === "Enter" || e.key === "Tab") && sugIndex >= 0) {
      e.preventDefault();
      pick(items[sugIndex].firstChild.textContent);
    } else if (e.key === "Escape") {
      ui.suggest.hidden = true;
    }
  }

  // ---------- busca e lista ----------

  function refresh() {
    const res = AGSearch.search(state.query, docs, {
      mode: state.mode,
      auto: state.auto,
      getText: (id) => texts.get(id) || "",
    });
    if (res.error) {
      ui.error.textContent = "Consulta incompleta: " + res.error + ".";
      return; // mantém o último resultado
    }
    ui.error.textContent = "";
    result = res;
    if (res.all) {
      hi = null;
      hiTags = null;
    } else {
      hi = new Set(res.ids);
      hiTags = new Set();
      Object.values(res.matched).forEach((tags) => tags.forEach((t) => {
        const p = t.split("/");
        for (let i = 1; i <= p.length; i++) hiTags.add(p.slice(0, i).join("/"));
      }));
    }
    renderList();
    updateGraph();
  }

  function renderList() {
    ui.count.textContent = result.all
      ? `${docs.length} documentos`
      : `${result.ids.length} de ${docs.length} documentos`;
    ui.list.innerHTML = "";
    if (!result.ids.length) {
      ui.list.appendChild($("li", "gv-empty", "Nenhum documento."));
      return;
    }
    const byId = new Map(docs.map((d) => [d.id, d]));
    result.ids.forEach((id) => {
      const d = byId.get(id);
      const li = $("li");
      const b = $("button", "gv-item", d.title);
      b.type = "button";
      b.addEventListener("click", () => openDoc(id));
      const path = $("div", "gv-path", d.file);
      li.append(b, path);
      const tags = result.all ? d.tags.curated.slice(0, 3) : (result.matched[id] || []).slice(0, 6);
      if (tags.length) {
        const chips = $("div", "gv-chips");
        tags.forEach((t) => {
          const c = $("button", "gv-chip", "#" + t);
          c.type = "button";
          c.addEventListener("click", () => setQuery("tag:" + t));
          chips.appendChild(c);
        });
        li.appendChild(chips);
      }
      ui.list.appendChild(li);
    });
  }

  function setQuery(q) {
    ui.input.value = q;
    state.query = q;
    refresh();
  }

  // ---------- 3D ----------

  const isHi = (n) => (n.type === "doc" ? hi.has(n.id) : hiTags.has(n.tag));

  // Cores do grafo vêm das variáveis do CSS, então seguem o tema claro/escuro.
  let gc = null;
  function readColors() {
    const cs = getComputedStyle(document.documentElement);
    const v = (name, fallback) => cs.getPropertyValue(name).trim() || fallback;
    return {
      bg: v("--bg", "#eef2f1"), tag: v("--g-tag", "#7f8f94"), tagDim: v("--g-tag-dim", "#dde3e2"),
      docDim: v("--g-doc-dim", "#cfd6d5"), link: v("--g-link", "#93a4a9"), linkDim: v("--g-link-dim", "#e3e8e7"),
    };
  }

  function ensureGraph() {
    if (graph || graphFailed) return !!graph;
    const fail = (msg) => {
      graphFailed = true;
      ui.canvas.innerHTML = "";
      ui.canvas.appendChild($("p", "gv-msg", msg));
    };
    if (typeof ForceGraph3D === "undefined") { fail("Biblioteca 3D não encontrada em site/js/vendor/. A busca e a lista continuam funcionando."); return false; }
    if (!webglOk()) { fail("Este navegador não iniciou o WebGL, então o 3D não aparece. A busca e a lista continuam funcionando."); return false; }
    try {
      gc = readColors();
      graph = ForceGraph3D()(ui.canvas)
        .backgroundColor(gc.bg)
        .showNavInfo(false)
        .nodeRelSize(3.2)
        .nodeResolution(14)
        .nodeVal((n) => (n.type === "doc" ? 2 + Math.sqrt(n.deg) * 1.5 : 1 + Math.sqrt(n.n) * 1.2))
        .nodeColor((n) => {
          const dim = hi !== null && !isHi(n);
          if (n.type === "tag") return dim ? gc.tagDim : gc.tag;
          return dim ? gc.docDim : colors.get(n.group) || "#8a9aa0";
        })
        .nodeLabel((n) => n.type === "doc"
          ? `<div class="gv-tip"><b>${escapeHtml(n.label)}</b><br><small>${escapeHtml(n.file)}</small><br>${n.tags.slice(0, 8).map(escapeHtml).join(" · ")}</div>`
          : `<div class="gv-tip"><b>#${escapeHtml(n.tag)}</b><br><small>${n.n} documento(s)</small></div>`)
        .linkOpacity(0.55)
        .linkWidth((l) => (state.link === "direct" ? Math.min(0.3 + l.w * 0.35, 2.5) : 0.5))
        .linkColor((l) => (hi !== null && !(isHi(l.source) && isHi(l.target)) ? gc.linkDim : gc.link))
        .warmupTicks(40)
        .cooldownTime(8000)
        .onEngineStop(() => fit())
        .onNodeClick((n) => (n.type === "doc" ? openDoc(n.id) : setQuery("tag:" + n.tag)));
      graph.controls().addEventListener("start", () => { userMoved = true; });
      resize();
      return true;
    } catch (e) {
      fail("O 3D não pôde ser iniciado neste navegador (" + e.message + "). A busca e a lista continuam funcionando.");
      return false;
    }
  }

  function updateGraph() {
    if (!isOpen()) return; // o 3D só nasce com o grafo aberto; reabrir com o mesmo estado não reconstrói nada
    if (!ensureGraph()) return;
    const only = state.only && !result.all ? new Set(result.ids) : null;
    const key = [state.link, state.auto, only ? result.ids.join(",") : ""].join("|");
    if (key !== graphKey) {
      graphKey = key;
      // Modo direto liga cada documento a muitos outros: afasta os nós para o desenho respirar.
      const direct = state.link === "direct";
      graph.d3Force("link").distance(direct ? 90 : 30);
      graph.d3Force("charge").strength(direct ? -140 : -30);
      graph.graphData(AGModel.build(docs, { mode: state.link, auto: state.auto, only }));
      scheduleFit();
    }
    graph.nodeColor(graph.nodeColor()).linkColor(graph.linkColor()).linkWidth(graph.linkWidth()); // reaplica cores e larguras
  }

  // Chamado pelo botão de tema (app.js): relê as cores e repinta o grafo, se ele já existir.
  function applyTheme() {
    if (!graph) return; // ainda não nasceu: ensureGraph lê as cores do tema atual
    gc = readColors();
    graph.backgroundColor(gc.bg).nodeColor(graph.nodeColor()).linkColor(graph.linkColor());
  }

  // Enquadra o grafo depois de cada reconstrução: uma vez cedo (2,5 s) e outra quando a simulação
  // termina de acomodar. Nunca depois que a pessoa mexeu na câmera, e um timer de uma reconstrução
  // antiga não enquadra o grafo da reconstrução seguinte.
  let fitToken = 0;
  let userMoved = false;
  function scheduleFit() {
    const token = ++fitToken;
    userMoved = false;
    setTimeout(() => fit(token), 2500);
  }
  function fit(token) {
    if ((token !== undefined && token !== fitToken) || userMoved || !graph || !isOpen()) return;
    graph.zoomToFit(500, 24);
  }

  function resize() {
    if (!graph) return;
    const w = ui.canvas.clientWidth;
    const h = ui.canvas.clientHeight;
    if (w > 0 && h > 0) graph.width(w).height(h);
  }

  // ---------- abrir, fechar, integrar ao site ----------

  const isOpen = () => document.body.classList.contains("graph-open");

  function open() {
    document.body.classList.add("graph-open");
    if (ui.btn) ui.btn.classList.add("on");
    if (ui.root && ui.input) {
      if (ensureGraph()) { graph.resumeAnimation(); resize(); }
      updateGraph();
    }
  }

  function close() {
    if (!isOpen()) return;
    document.body.classList.remove("graph-open");
    if (ui.btn) ui.btn.classList.remove("on");
    if (graph) graph.pauseAnimation();
  }

  function openDoc(id) {
    close();
    // as palavras da busca vão junto: o app.js as marca no texto do documento
    if (typeof setHighlight === "function") setHighlight(id, AGSearch.highlightTerms(state.query, state.mode));
    if (window.location.hash.slice(1) !== id) window.location.hash = id;
    else if (typeof selectByHash === "function") selectByHash(); // já era o documento aberto: não há hashchange
  }

  function init() {
    ui.root = document.getElementById("graph-view");
    ui.btn = document.getElementById("graph-btn");
    if (!ui.root || !ui.btn) return;
    ui.btn.addEventListener("click", () => (isOpen() ? close() : open()));

    if (typeof AG_GRAPH === "undefined") {
      ui.root.innerHTML = "";
      ui.root.appendChild($("p", "gv-msg", "Não encontrei site/js/graph-data.js. Rode o sync (sync.py, start.bat ou start.sh) e recarregue a página."));
      return;
    }
    loadData();
    build(ui.root);
    refresh();
  }

  // Lê AG_GRAPH e AG_CONTENT: textos para a busca, cor e legenda de cada pasta.
  function loadData() {
    docs = AG_GRAPH.docs;
    texts.clear();
    colors.clear();
    legend.length = 0;
    AG_CONTENT.forEach((g) => g.items.forEach((it) => texts.set(it.id, stripFrontmatter(it.fallback))));
    AG_CONTENT.forEach((g, i) => {
      const color = PALETTE[i % PALETTE.length];
      colors.set(g.id === "home" ? "home" : g.folder, color);
      legend.push([g.label, color]);
    });
  }

  // Relê os dados depois que a lista de documentos mudou (edição ou nota nova). Busca e câmera ficam como estavam.
  function reload() {
    if (!ui.input) return; // o grafo não iniciou (sem graph-data.js)
    loadData();
    drawLegend();
    graphKey = null; // o 3D se refaz na próxima vez que o grafo estiver aberto
    refresh();
  }

  return { init, open, close, applyTheme, reload };
})();
