// Lógica do agLocalSite (visualizador/editor local de .md a partir da raiz do projeto).
// Não precisa mexer aqui para adicionar conteúdo novo: o sync.py gera site/js/content.js.
// Este arquivo só monta a navegação e decide se mostra o arquivo real (fetch) ou o texto embutido (fallback).

const treeEl = document.getElementById("tree");
const contentEl = document.getElementById("content");
const statusEl = document.getElementById("status-line");

// Tudo que aparece na tela vem do config.json (via content.js, ou da resposta do painel de configurações ao salvar): título, subtítulo,
// etiqueta, título da aba, rótulos dos botões e rodapé. Chave ausente ou vazia volta ao texto padrão do index.html, guardado aqui
// antes de qualquer configuração para "restaurar padrão" valer sem recarregar a página.
const PADRAO_UI = (() => {
  const mapa = { "graph-btn": "grafo", "kb-btn": "quadro", "ag-plus": "mais", "menu-btn": "menu" };
  const botoes = {};
  for (const id of Object.keys(mapa)) { const el = document.getElementById(id); if (el) botoes[id] = el.textContent; }
  const rodape = document.querySelector("footer.hint");
  const sub = document.getElementById("brand-sub");
  return { mapa, botoes, rodapeHtml: rodape ? rodape.innerHTML : "", subtitulo: sub ? sub.textContent : "" };
})();

// cfg tem o formato de AG_CONFIG. Tudo entra por textContent. O botão de tema não é repintado aqui (quem muda o modo chama paintThemeBtn()).
function aplicarConfig(cfg) {
  if (!cfg) return;
  agDefinirTextos(cfg.textos);
  document.title = cfg.titulo_aba;
  document.getElementById("brand-title").textContent = cfg.titulo;
  document.getElementById("brand-tag").textContent = cfg.etiqueta;
  document.getElementById("brand-sub").textContent = cfg.subtitulo || PADRAO_UI.subtitulo;
  for (const [id, chave] of Object.entries(PADRAO_UI.mapa)) {
    const el = document.getElementById(id);
    if (el) el.textContent = agTexto(chave, PADRAO_UI.botoes[id]);
  }
  const rodape = document.querySelector("footer.hint");
  if (rodape) {
    const r = cfg.textos && cfg.textos.rodape;
    if (typeof r === "string") {          // "" oculta o rodapé; texto o substitui (texto puro)
      rodape.hidden = r === "";
      if (r !== "") rodape.textContent = r;
    } else {                              // padrão: o HTML do index.html
      rodape.hidden = false;
      rodape.innerHTML = PADRAO_UI.rodapeHtml;
    }
  }
}
if (typeof AG_CONFIG !== "undefined") aplicarConfig(AG_CONFIG);

// Menu recolhível no celular (até 860 px, ver style.css): fechado, o documento aparece na primeira tela.
const menuBtn = document.getElementById("menu-btn");
function setMenu(aberto) {
  document.body.classList.toggle("menu-open", aberto);
  menuBtn.setAttribute("aria-expanded", String(aberto));
}
menuBtn.addEventListener("click", () => setMenu(!document.body.classList.contains("menu-open")));

let allButtons = [];
let currentId = null; // documento aberto

// Documento aberto, como está em AG_CONTENT agora (o objeto muda quando a lista é atualizada).
function currentDoc() {
  return docList().find((d) => d.id === currentId) || null;
}

// Palavras a marcar no próximo documento aberto ({ id, terms }). Vem do grafo; o menu lateral não marca nada.
let pendingHl = null;
function setHighlight(id, terms) {
  pendingHl = terms.length ? { id, terms } : null;
}

function markTerms(terms) {
  const walker = document.createTreeWalker(contentEl, NodeFilter.SHOW_TEXT);
  const nodes = [];
  while (walker.nextNode()) nodes.push(walker.currentNode);
  let first = null;
  nodes.forEach((node) => {
    const text = node.nodeValue;
    const ranges = AGSearch.findRanges(text, terms);
    if (!ranges.length) return;
    const frag = document.createDocumentFragment();
    let pos = 0;
    ranges.forEach(([s, e]) => {
      frag.append(text.slice(pos, s));
      const m = document.createElement("mark");
      m.textContent = text.slice(s, e);
      frag.append(m);
      first = first || m;
      pos = e;
    });
    frag.append(text.slice(pos));
    node.replaceWith(frag);
  });
  if (first) first.scrollIntoView({ block: "center" });
}

// Monta o menu. Pode ser chamada de novo (lista atualizada): pastas abertas e documento ativo são mantidos.
function buildTree() {
  const first = !treeEl.children.length;
  const abertos = new Set([...treeEl.querySelectorAll(".group.open, .subgroup.open")].map((e) => e.dataset.key));
  treeEl.innerHTML = "";
  allButtons = [];
  AG_CONTENT.forEach((group, gi) => {
    const groupDiv = document.createElement("div");
    groupDiv.dataset.key = "g:" + group.id;
    groupDiv.className = "group" + ((first ? gi === 0 : abertos.has(groupDiv.dataset.key)) ? " open" : "");

    const label = document.createElement("button");
    label.className = "group-label";
    label.innerHTML = `<span class="caret"></span><span>${escapeHtml(group.label)}</span>`;
    label.addEventListener("click", () => groupDiv.classList.toggle("open"));

    const itemsDiv = document.createElement("div");
    itemsDiv.className = "group-items";

    // Subpasta dentro da pasta numerada (ex.: 02-.../Alfa/Painel/README.md)
    // vira um grupo expansível. README direto na pasta-módulo (grupo/módulo/README.md) não conta.
    let lastSub = null;
    let container = itemsDiv;
    group.items.forEach((item) => {
      const parts = item.file.split("/");
      const sub = parts.length >= 4 || (parts.length === 3 && !/^readme\.md$/i.test(parts[2])) ? parts[1] : null;
      if (sub !== lastSub) {
        container = itemsDiv;
        if (sub) {
          const subDiv = document.createElement("div");
          subDiv.dataset.key = "s:" + group.id + "/" + sub;
          subDiv.className = "subgroup" + (abertos.has(subDiv.dataset.key) ? " open" : "");
          const h = document.createElement("button");
          h.className = "sub-label";
          h.innerHTML = `<span class="caret"></span><span>${escapeHtml(sub)}</span>`;
          h.addEventListener("click", () => subDiv.classList.toggle("open"));
          container = document.createElement("div");
          container.className = "sub-items";
          subDiv.appendChild(h);
          subDiv.appendChild(container);
          itemsDiv.appendChild(subDiv);
        }
        lastSub = sub;
      }
      const btn = document.createElement("button");
      btn.className = "item-btn";
      btn.textContent = item.title;
      btn.dataset.id = item.id;
      btn.addEventListener("click", () => { pendingHl = null; selectItem(item, btn); });
      container.appendChild(btn);
      allButtons.push(btn);
    });

    groupDiv.appendChild(label);
    groupDiv.appendChild(itemsDiv);
    treeEl.appendChild(groupDiv);
  });
  const ativo = allButtons.find((b) => b.dataset.id === currentId);
  if (ativo) ativo.classList.add("active");
}

// Opções do renderizador: a pasta do documento aberto resolve as imagens relativas.
function opcoesMd() {
  const item = currentDoc();
  return { pasta: item ? item.file.split("/").slice(0, -1).join("/") : null };
}

// Desenha o texto do documento aberto e avisa a interface de escrita (botão Editar, caixas do checklist).
function showDoc(text) {
  contentEl.innerHTML = markdownToHtml(text, opcoesMd());
  if (typeof AGEditor !== "undefined") AGEditor.aoAbrir();
  if (typeof AGPostit !== "undefined") AGPostit.aoAbrir();
}

// Redesenha o documento aberto com os dados atuais, sem sair do lugar na página.
function repaintCurrent() {
  const item = currentDoc();
  if (!item) return;
  const y = window.scrollY;
  showDoc(item.fallback);
  window.scrollTo(0, y);
}

async function selectItem(item, btn) {
  if (typeof AGEditor !== "undefined" && !AGEditor.podeSair()) {
    // recusou descartar a edição: se a troca veio do endereço (link, voltar), devolve o endereço do documento em edição
    if (currentId && window.location.hash.slice(1) !== currentId) history.replaceState(null, "", "#" + currentId);
    return;
  }
  if (typeof AGView !== "undefined") AGView.close();
  if (typeof AGBoard !== "undefined") AGBoard.close();
  setMenu(false);
  allButtons.forEach((b) => b.classList.remove("active"));
  btn.classList.add("active");
  currentId = item.id;

  contentEl.innerHTML = "<p>Carregando…</p>";

  let text = item.fallback;
  let source = "embutido";

  try {
    const res = await fetch("../" + item.file.split("/").map(encodeURIComponent).join("/"), { cache: "no-store" });
    if (res.ok) {
      const fetched = await res.text();
      if (fetched && fetched.trim().length > 0) {
        text = fetched;
        source = "arquivo local";
      }
    }
  } catch (e) {
    // fetch bloqueado (comum ao abrir via file://) — usa o fallback embutido
  }

  if (currentId !== item.id) return; // outro documento foi aberto enquanto este carregava

  statusEl.innerHTML = `
    <span class="status-dot ${source === "arquivo local" ? "" : "fallback"}"></span>
    <span>${escapeHtml(item.file)} — carregado de: ${source}${source !== "arquivo local" ? " (abra via servidor local para carregar o arquivo ao vivo)" : ""}</span>
  `;

  showDoc(text);
  window.scrollTo(0, 0); // link de citação clicado no fim de um documento longo abre o novo no topo
  if (pendingHl && pendingHl.id !== item.id) pendingHl = null;
  if (pendingHl) {
    try { markTerms(pendingHl.terms); } catch (e) { /* navegador sem suporte à busca do destaque: o documento abre sem marcas */ }
  }
  window.location.hash = item.id;
}

function selectByHash() {
  const id = window.location.hash.replace("#", "");
  if (!id) return false;
  for (const group of AG_CONTENT) {
    const item = group.id === id ? group.items[0] : group.items.find((it) => it.id === id);
    if (item) {
      // selectItem grava o hash ao terminar; esse hashchange não pode abrir o mesmo documento de novo (era um fetch a mais por clique)
      if (item.id === currentId) return true;
      const btn = allButtons.find((b) => b.dataset.id === item.id);
      const groupDiv = btn.closest(".group");
      groupDiv.classList.add("open");
      const subDiv = btn.closest(".subgroup");
      if (subDiv) subDiv.classList.add("open");
      selectItem(item, btn);
      return true;
    }
  }
  return false;
}

buildTree();

// Tema claro/escuro: o <head> já aplicou o tema salvo; aqui fica só o botão. Começa no claro.
const themeBtn = document.getElementById("theme-btn");
function paintThemeBtn() {
  const dark = document.documentElement.dataset.theme === "dark";
  themeBtn.textContent = dark ? agTexto("tema_claro", "☀ Claro") : agTexto("tema_escuro", "☾ Escuro");
  themeBtn.setAttribute("aria-pressed", String(dark));
}
if (themeBtn) {
  paintThemeBtn();
  themeBtn.addEventListener("click", () => {
    const dark = document.documentElement.dataset.theme !== "dark";
    document.documentElement.dataset.theme = dark ? "dark" : "light";
    try { localStorage.setItem("ag-theme", dark ? "dark" : "light"); } catch (e) { /* armazenamento bloqueado: vale só nesta visita */ }
    paintThemeBtn();
    if (typeof AGView !== "undefined") AGView.applyTheme();
  });
}
if (typeof AGView !== "undefined") AGView.init();
if (typeof AGBoard !== "undefined") AGBoard.init();
if (typeof AGPostit !== "undefined") AGPostit.init();

window.addEventListener("hashchange", selectByHash);

// Link interno [texto](#secao) para um título do documento aberto: rola até ele e mantém o endereço do documento
// (trocar o hash faria o F5 abrir outro documento). Citação de documento (a.doc-link) segue o caminho normal.
contentEl.addEventListener("click", (e) => {
  const a = e.target.closest && e.target.closest('a[href^="#"]');
  if (!a || a.classList.contains("doc-link")) return;
  let id = a.getAttribute("href").slice(1);
  try { id = decodeURIComponent(id); } catch (err) { /* % solto no endereço: usa como está */ }
  const alvo = document.getElementById(id);
  if (alvo && contentEl.contains(alvo)) { e.preventDefault(); alvo.scrollIntoView(); }
});

if (!AG_CONTENT.length) {
  contentEl.innerHTML = "<h1>Nenhum .md encontrado</h1><p>Crie um <code>.md</code> na raiz do projeto (a pasta que contém <code>agLocalSite/</code>) ou dentro de uma pasta dela e rode o <code>sync</code>.</p>";
} else if (!selectByHash()) {
  // abre o primeiro documento por padrão
  const first = AG_CONTENT[0].items[0];
  const firstBtn = allButtons[0];
  selectItem(first, firstBtn);
}

// Escrita pelo site: só liga se o servidor (start.bat / start.sh) responder; sem ele, tudo acima segue só de leitura.
if (typeof AGEditor !== "undefined") AGEditor.init();
