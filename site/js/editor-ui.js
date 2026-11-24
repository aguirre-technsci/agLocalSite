// Interface de escrita: barra Ctrl+K, painel "Nova nota", modo Editar, checklists que gravam
// e a consulta periódica que mantém menu, tags e grafo em dia.
//
// Só liga quando o serve.py responde em /api/ping (start.bat / start.sh). Sem servidor, nada daqui aparece
// e o site é só de leitura. As regras (o que grava, onde, com que cuidado) ficam no agwrite.py.

const AGEditor = (function () {
  const $ = (tag, cls, text) => {
    const e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text != null) e.textContent = text;
    return e;
  };

  const barEl = document.getElementById("ag-bar");
  const linhaEl = $("div", "ag-linha");
  const faixaEl = $("div", "ag-faixa-area");
  barEl.append(linhaEl, faixaEl);

  let escrita = false;   // o servidor está respondendo
  let carimbo = null;    // versão dos .md que a página conhece
  let mtimes = {};       // arquivo -> mtime_ns (texto), base para detectar conflito
  let carimboPostits = null; // versão dos .postits/*.json que a página conhece
  let postits = {};      // arquivo .md -> post-its (só os documentos que têm algum)
  let edicao = null;     // { file, base, original, ta, prev } enquanto edita
  let salvando = false;
  let faixaSaida = null; // faixa de "servidor parado", para sumir quando ele voltar
  const MSG_SAIDA = "O servidor não responde. O site voltou ao modo leitura e tenta de novo sozinho.";

  const sujo = () => !!edicao && edicao.ta.value !== edicao.original;

  // ---------- dados: buscar do servidor e alterar os objetos no lugar ----------
  // content.js e graph-data.js declaram const: a página muda o conteúdo dos objetos, não reatribui.

  async function atualizar() {
    const e = await AGWrite.estado();
    if (e.status !== 200) throw new Error(e.erro);
    const antes = currentDoc() && mtimes[currentDoc().file];
    carimbo = e.carimbo;
    mtimes = e.mtimes;
    carimboPostits = e.carimbo_postits;
    postits = e.postits || {};
    AG_CONTENT.splice(0, AG_CONTENT.length, ...e.content);
    AG_GRAPH.docs.splice(0, AG_GRAPH.docs.length, ...e.graph.docs);
    buildTree();
    if (typeof AGView !== "undefined") AGView.reload();
    if (typeof AGBoard !== "undefined") AGBoard.reload();
    if (typeof AGPostit !== "undefined") AGPostit.reload();
    const doc = currentDoc();
    if (!doc) return;
    if (edicao) {
      if (mtimes[edicao.file] !== edicao.base) faixaConflito(mtimes[edicao.file]);
    } else if (antes !== undefined && mtimes[doc.file] !== antes) {
      repaintCurrent(); // o arquivo mudou por fora
    }
  }

  async function ciclo() {
    if (document.visibilityState === "visible") {
      try {
        const v = await AGWrite.versao();
        if (v.status !== 200) throw new Error(v.erro);
        if (!escrita) voltouEscrita();
        if (v.carimbo !== carimbo || v.carimbo_postits !== carimboPostits) await atualizar();
      } catch (e) {
        if (escrita) emLeitura();
      }
    }
    setTimeout(ciclo, 2000);
  }

  function emLeitura() {
    escrita = false;
    document.getElementById("ag-plus").hidden = true;
    if (typeof AGPainel !== "undefined") AGPainel.setEscrita(false);
    barra();
    ativarCaixas();
    if (typeof AGBoard !== "undefined") { AGBoard.reload(); AGBoard.aviso(MSG_SAIDA); }
    if (typeof AGPostit !== "undefined") AGPostit.reload();
    faixaSaida = faixa(MSG_SAIDA);
  }

  function voltouEscrita() {
    escrita = true;
    document.getElementById("ag-plus").hidden = false;
    if (typeof AGPainel !== "undefined") AGPainel.setEscrita(true);
    if (faixaSaida && faixaSaida.isConnected) limparFaixa();
    faixaSaida = null;
    barra();
    ativarCaixas();
    if (typeof AGBoard !== "undefined") { AGBoard.reload(); AGBoard.aviso(""); }
    if (typeof AGPostit !== "undefined") AGPostit.reload();
  }

  // ---------- painel modal: foco preso, Esc fecha, foco volta a quem abriu ----------

  function abrirDialogo(painel, aoFechar) {
    const origem = document.activeElement;
    const fundo = $("div", "ag-fundo");
    const shell = document.querySelector(".shell");
    fundo.append(painel);
    document.body.append(fundo);
    shell.inert = true;
    const fechar = () => {
      document.removeEventListener("keydown", tecla, true);
      fundo.remove();
      shell.inert = false;
      if (origem && origem.isConnected) origem.focus();
      if (aoFechar) aoFechar();
    };
    const tecla = (e) => {
      if (e.key === "Escape") {
        e.preventDefault();
        fechar();
      } else if (e.key === "Tab") {
        const f = [...painel.querySelectorAll("button, input, select, textarea")].filter((x) => !x.disabled && x.offsetParent !== null);
        if (!f.length) return;
        const ativo = document.activeElement;
        if (!painel.contains(ativo) || (e.shiftKey && ativo === f[0]) || (!e.shiftKey && ativo === f[f.length - 1])) {
          e.preventDefault();
          (e.shiftKey ? f[f.length - 1] : f[0]).focus();
        }
      }
    };
    document.addEventListener("keydown", tecla, true);
    fundo.addEventListener("mousedown", (e) => { if (e.target === fundo) fechar(); });
    return fechar;
  }

  function dialogo(classe, titulo) {
    const painel = $("div", "ag-dialogo " + classe);
    painel.setAttribute("role", "dialog");
    painel.setAttribute("aria-modal", "true");
    painel.setAttribute("aria-label", titulo);
    return painel;
  }

  // ---------- barra Ctrl+K ----------

  function abrirPaleta() {
    if (!escrita || document.querySelector(".ag-fundo")) return;
    const doc = currentDoc();
    const pasta = doc ? doc.file.split("/").slice(0, -1).join("/") : "";
    const acoes = [{ titulo: "Nova nota", caminho: "", acao: "nova", dica: "em " + (pasta || agTexto("home", "Home")) }];
    acoes.push({ titulo: "Abrir o quadro", caminho: "", acao: "quadro", dica: "notas e checklists" });
    if (doc && !edicao) acoes.push({ titulo: "Editar este documento", caminho: "", acao: "editar", dica: doc.title });
    if (doc && !edicao && typeof AGPostit !== "undefined") acoes.push({ titulo: "Novo post-it", caminho: "", acao: "postit", dica: "nesta página" });
    const todos = [...acoes, ...docList().map((d) => ({ titulo: d.title, caminho: d.file, id: d.id }))];

    const painel = dialogo("ag-paleta", "Barra de comandos");
    const entrada = $("input");
    entrada.type = "text";
    entrada.autocomplete = "off";
    entrada.spellcheck = false;
    entrada.placeholder = "Ir para um documento, ou criar uma nota";
    entrada.setAttribute("aria-label", "Buscar documento ou ação");
    entrada.setAttribute("role", "combobox");
    entrada.setAttribute("aria-expanded", "true");
    entrada.setAttribute("aria-controls", "ag-lista");
    entrada.setAttribute("aria-autocomplete", "list");
    const lista = $("ul", "ag-lista");
    lista.id = "ag-lista";
    lista.setAttribute("role", "listbox");
    lista.setAttribute("aria-label", "Resultados");
    painel.append(entrada, lista, $("p", "ag-dica", "↑ ↓ escolhem · Enter abre · Esc fecha"));
    const fechar = abrirDialogo(painel);

    let itens = [];
    let ativo = 0;

    function marcar() {
      [...lista.children].forEach((li, i) => li.setAttribute("aria-selected", String(i === ativo)));
      const li = lista.children[ativo];
      entrada.setAttribute("aria-activedescendant", li ? li.id : "");
      if (li) li.scrollIntoView({ block: "nearest" });
    }

    function desenhar() {
      itens = AGWrite.filtrarPaleta(todos, entrada.value).slice(0, 60);
      ativo = 0;
      lista.replaceChildren();
      if (!itens.length) {
        const vazio = $("li", "ag-vazio", "Nenhum documento com esse texto.");
        vazio.setAttribute("role", "presentation");
        lista.append(vazio);
      }
      itens.forEach((it, i) => {
        const li = $("li", "ag-op" + (it.acao ? " acao" : ""));
        li.id = "ag-op-" + i;
        li.setAttribute("role", "option");
        li.append($("span", "t", it.titulo), $("span", "c", it.acao ? it.dica : it.caminho));
        li.addEventListener("click", () => executar(it));
        lista.append(li);
      });
      marcar();
    }

    function executar(it) {
      fechar();
      if (it.acao === "nova") abrirNova();
      else if (it.acao === "quadro") AGBoard.open();
      else if (it.acao === "editar") { AGBoard.close(); entrarEdicao(); }
      else if (it.acao === "postit") AGPostit.criarNaTela();
      else window.location.hash = it.id;
    }

    entrada.addEventListener("input", desenhar);
    entrada.addEventListener("keydown", (e) => {
      if (e.key === "ArrowDown" || e.key === "ArrowUp") {
        e.preventDefault();
        if (itens.length) ativo = (ativo + (e.key === "ArrowDown" ? 1 : -1) + itens.length) % itens.length;
        marcar();
      } else if (e.key === "Enter" && itens[ativo]) {
        e.preventDefault();
        executar(itens[ativo]);
      }
    });
    desenhar();
    entrada.focus();
  }

  // ---------- Nova nota ----------

  // Toda pasta com documento, mais as pastas-mãe delas e a raiz ("" = Home).
  function pastas() {
    const todas = new Set([""]);
    docList().forEach((d) => {
      const partes = d.file.split("/").slice(0, -1);
      for (let i = 1; i <= partes.length; i++) todas.add(partes.slice(0, i).join("/"));
    });
    return [...todas].sort();
  }

  function abrirNova() {
    if (!escrita || document.querySelector(".ag-fundo")) return;
    const doc = currentDoc();
    const painel = dialogo("ag-nova", "Nova nota");
    const titulo = $("h2", null, "Nova nota");
    titulo.id = "ag-nova-titulo";
    painel.setAttribute("aria-labelledby", titulo.id);
    painel.removeAttribute("aria-label");

    const campo = (rotulo, controle, extra) => {
      const l = $("label", "ag-campo");
      l.append($("span", null, rotulo), controle);
      if (extra) l.append(extra);
      return l;
    };

    const selPasta = $("select");
    pastas().forEach((p) => selPasta.append(new Option(p || "Home (raiz do projeto)", p)));
    selPasta.value = doc ? doc.file.split("/").slice(0, -1).join("/") : "";

    const campoTitulo = $("input");
    campoTitulo.type = "text";
    campoTitulo.autocomplete = "off";
    const erroTitulo = $("div", "ag-erro");
    erroTitulo.id = "ag-erro-titulo";
    erroTitulo.setAttribute("role", "alert");
    campoTitulo.setAttribute("aria-describedby", erroTitulo.id);

    // tags: chips + campo de digitação com sugestões das tags que já existem
    const tags = [];
    const chips = $("span", "ag-chips");
    const campoTag = $("input");
    campoTag.type = "text";
    campoTag.autocomplete = "off";
    campoTag.spellcheck = false;
    campoTag.setAttribute("aria-label", "Tags. Enter cria a tag");
    const sugestoes = $("div", "gv-suggest");
    sugestoes.hidden = true;
    const caixaTags = $("div", "ag-tags gv-search");
    caixaTags.append(chips, campoTag, sugestoes);
    const rotuloTags = $("div", "ag-campo");
    rotuloTags.append($("span", null, "Tags"), caixaTags);

    // status (opcional): a nota entra no quadro na coluna com esse nome; as colunas que já existem vêm como sugestão
    const campoStatus = $("input");
    campoStatus.type = "text";
    campoStatus.autocomplete = "off";
    campoStatus.maxLength = 40;
    campoStatus.setAttribute("list", "ag-status-lista");
    const listaStatus = $("datalist");
    listaStatus.id = "ag-status-lista";
    AGKanban.montarQuadro(docList()).colunas.forEach((c) => listaStatus.append(new Option(c.rotulo)));
    const erroStatus = $("div", "ag-erro");
    erroStatus.id = "ag-erro-status";
    erroStatus.setAttribute("role", "alert");
    campoStatus.setAttribute("aria-describedby", erroStatus.id);

    const corpo = $("textarea");
    corpo.rows = 6;
    const previa = $("pre", "ag-previa");
    const erroGeral = $("div", "ag-erro");
    erroGeral.setAttribute("role", "alert");
    const cancelar = $("button", "ag-btn", "Cancelar");
    cancelar.type = "button";
    const criarBtn = $("button", "ag-btn pri", "Criar nota");
    criarBtn.type = "button";
    const acoes = $("div", "ag-acoes");
    acoes.append(cancelar, criarBtn);
    painel.append(titulo, campo("Pasta", selPasta), campo("Título", campoTitulo, erroTitulo), rotuloTags,
      campo("Status (opcional)", campoStatus, erroStatus), listaStatus, campo("Texto", corpo), previa, erroGeral, acoes, $("p", "ag-dica", "Ctrl+Enter cria · Esc fecha"));
    const fechar = abrirDialogo(painel);

    // o que já foi digitado no campo de tag e ainda não virou chip também vai na nota
    const tagsAtuais = () => (campoTag.value.trim() ? [...tags, campoTag.value] : tags);

    function pintarPrevia() {
      const nome = AGWrite.slugTitulo(campoTitulo.value);
      const arquivo = nome ? (selPasta.value ? selPasta.value + "/" : "") + nome + ".md" : "(digite um título)";
      previa.textContent = "arquivo: " + arquivo + "\n" + AGWrite.frontmatter(tagsAtuais(), campoStatus.value);
    }

    function pintarChips() {
      chips.replaceChildren();
      tags.forEach((t, i) => {
        const b = $("button", "ag-chip", "#" + t + " ×");
        b.type = "button";
        b.setAttribute("aria-label", "Remover a tag " + t);
        b.addEventListener("click", () => { tags.splice(i, 1); pintarChips(); campoTag.focus(); });
        chips.append(b);
      });
      pintarPrevia();
    }

    function addTag(texto) {
      const t = AGSearch.normTag(texto);
      if (t && !tags.includes(t)) tags.push(t);
      campoTag.value = "";
      sugestoes.hidden = true;
      pintarChips();
    }

    let sug = -1;
    function mostrarSugestoes() {
      sugestoes.replaceChildren();
      sug = -1;
      const q = campoTag.value.trim();
      const lista = q ? AGSearch.suggest(q, AG_GRAPH.docs, false, 6).filter((s) => !tags.includes(s.tag)) : [];
      lista.forEach(({ tag, count }) => {
        const b = $("button", "", tag);
        b.type = "button";
        b.tabIndex = -1;
        b.append($("span", "gv-sug-n", String(count)));
        b.addEventListener("mousedown", (e) => { e.preventDefault(); addTag(tag); });
        sugestoes.append(b);
      });
      sugestoes.hidden = !lista.length;
    }

    campoTag.addEventListener("input", () => { mostrarSugestoes(); pintarPrevia(); });
    campoTag.addEventListener("keydown", (e) => {
      const itensSug = [...sugestoes.querySelectorAll("button")];
      if ((e.key === "ArrowDown" || e.key === "ArrowUp") && !sugestoes.hidden) {
        e.preventDefault();
        sug = (sug + (e.key === "ArrowDown" ? 1 : -1) + itensSug.length) % itensSug.length;
        itensSug.forEach((b, i) => b.classList.toggle("on", i === sug));
      } else if ((e.key === "Enter" || e.key === ",") && !e.ctrlKey && !e.metaKey) {
        e.preventDefault();
        if (sug >= 0 && itensSug[sug]) addTag(itensSug[sug].firstChild.textContent);
        else if (campoTag.value.trim()) addTag(campoTag.value);
      } else if (e.key === "Backspace" && !campoTag.value && tags.length) {
        tags.pop();
        pintarChips();
      } else if (e.key === "Escape" && !sugestoes.hidden) {
        e.stopPropagation(); // fecha só as sugestões
        sugestoes.hidden = true;
      }
    });
    campoTag.addEventListener("blur", () => { sugestoes.hidden = true; if (campoTag.value.trim()) addTag(campoTag.value); });

    campoTitulo.addEventListener("input", () => { erroTitulo.textContent = ""; pintarPrevia(); });
    campoStatus.addEventListener("input", () => { erroStatus.textContent = ""; pintarPrevia(); });
    selPasta.addEventListener("change", pintarPrevia);
    // texto colado que já começa com "# Título": o campo título se preenche sozinho
    corpo.addEventListener("input", () => {
      const m = !campoTitulo.value.trim() && /^\s*#[ \t]+(.+)/.exec(corpo.value);
      if (m) { campoTitulo.value = m[1].trim(); pintarPrevia(); }
    });

    let criando = false;
    async function criar() {
      if (criando) return;
      erroGeral.textContent = "";
      if (!AGWrite.slugTitulo(campoTitulo.value)) {
        erroTitulo.textContent = campoTitulo.value.trim() ? "Use pelo menos uma letra ou número no título." : "Digite um título.";
        campoTitulo.focus();
        return;
      }
      criando = true;
      criarBtn.disabled = true;
      try {
        const r = await AGWrite.nova(selPasta.value, campoTitulo.value, tagsAtuais(), corpo.value, campoStatus.value);
        if (r.status === 200) {
          await atualizar();
          fechar();
          window.location.hash = r.id;
          return;
        }
        if (r.codigo === "existe" || r.codigo === "titulo") {
          erroTitulo.textContent = r.codigo === "existe" ? r.erro + " Mude o título." : r.erro;
          campoTitulo.focus();
        } else if (r.codigo === "status") {
          erroStatus.textContent = r.erro;
          campoStatus.focus();
        } else {
          erroGeral.textContent = r.erro;
        }
      } catch (e) {
        erroGeral.textContent = "Sem conexão com o servidor. O que você digitou continua aqui.";
      }
      criando = false;
      criarBtn.disabled = false;
    }

    criarBtn.addEventListener("click", criar);
    cancelar.addEventListener("click", fechar);
    painel.addEventListener("keydown", (e) => {
      if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) { e.preventDefault(); criar(); }
    });
    pintarChips();
    campoTitulo.focus();
  }

  // ---------- Editar ----------

  function entrarEdicao() {
    const doc = currentDoc();
    if (!escrita || !doc || edicao) return;
    const ta = $("textarea", "ag-texto");
    ta.value = doc.fallback;
    ta.spellcheck = false;
    ta.setAttribute("aria-label", "Texto do arquivo, em markdown");
    const prev = $("div", "content ag-prev");
    prev.setAttribute("role", "region");
    prev.setAttribute("aria-label", "Prévia");
    contentEl.replaceChildren($("div", "ag-edicao"));
    contentEl.firstChild.append(ta, prev);
    edicao = { file: doc.file, base: mtimes[doc.file], original: doc.fallback, ta, prev };
    document.body.classList.add("ag-editando");

    let espera;
    const pintar = () => {
      prev.innerHTML = markdownToHtml(ta.value, typeof opcoesMd === "function" ? opcoesMd() : undefined);
      prev.querySelectorAll("input").forEach((cb) => cb.setAttribute("aria-label", cb.parentElement.textContent.trim()));
    };
    ta.addEventListener("input", () => { clearTimeout(espera); espera = setTimeout(pintar, 150); barra(); });
    ta.addEventListener("keydown", (e) => { if (e.key === "Escape") { e.preventDefault(); cancelarEdicao(); } });
    pintar();
    limparFaixa();
    barra();
    ta.focus();
  }

  function sairEdicao() {
    edicao = null;
    document.body.classList.remove("ag-editando");
    barra();
  }

  function cancelarEdicao() {
    if (sujo() && !confirm("Descartar as alterações deste documento?")) return;
    sairEdicao();
    limparFaixa();
    repaintCurrent();
  }

  async function salvarEdicao(base) {
    if (!edicao || salvando) return;
    salvando = true;
    barra();
    try {
      const r = await AGWrite.salvar(edicao.file, edicao.ta.value, base === undefined ? edicao.base : base);
      if (r.status === 200) {
        mtimes[edicao.file] = edicao.base = r.mtime;
        await atualizar();
        sairEdicao();
        limparFaixa();
        repaintCurrent();
      } else if (r.codigo === "conflito") {
        faixaConflito(r.mtime);
      } else {
        faixa("Não foi possível salvar: " + r.erro + " O texto continua aqui.");
      }
    } catch (e) {
      faixa("Sem conexão com o servidor. O texto continua aqui.");
    }
    salvando = false;
    barra();
  }

  // O arquivo mudou por fora: ficar com a nova versão ou sobrescrever com o que foi digitado.
  function faixaConflito(mtimeAtual) {
    faixa("O arquivo mudou por fora.", [
      ["Ver a nova versão", async () => {
        if (sujo() && !confirm("Descartar o que você digitou e abrir a nova versão?")) return;
        try { await atualizar(); } catch (e) { return faixa("Sem conexão com o servidor."); }
        sairEdicao();
        limparFaixa();
        repaintCurrent();
      }],
      ["Sobrescrever com a minha", () => salvarEdicao(mtimeAtual)],
    ]);
  }

  // ---------- barra acima do documento ----------

  function botao(rotulo, classe, aoClicar) {
    const b = $("button", "ag-btn " + classe, rotulo);
    b.type = "button";
    if (aoClicar) b.addEventListener("click", aoClicar);
    return b;
  }

  function barra() {
    linhaEl.replaceChildren();
    barEl.hidden = !(edicao || (escrita && currentDoc()));
    if (barEl.hidden) return;
    if (edicao) {
      const estado = $("span", "ag-estado" + (sujo() ? " sujo" : ""), salvando ? "Salvando…" : sujo() ? "Alterações não salvas" : "Sem alterações");
      estado.setAttribute("role", "status");
      const salvar = botao("Salvar", "pri", () => salvarEdicao());
      salvar.disabled = salvando;
      linhaEl.append(salvar, botao("Cancelar", "", cancelarEdicao), estado, $("span", "ag-estado", "Ctrl+S salva · Esc cancela"));
    } else {
      linhaEl.append(botao("Editar", "", entrarEdicao));
      if (typeof AGPostit !== "undefined") {
        const add = botao("＋ Post-it", "", null);
        AGPostit.ligarBotaoCriar(add);
        linhaEl.append(add);
        const n = AGPostit.contagem();
        if (n > 0) {
          const alternar = botao(`Post-its (${n})`, "", () => { AGPostit.alternarOcultar(); barra(); });
          alternar.setAttribute("aria-pressed", String(!AGPostit.estaOculto()));
          linhaEl.append(alternar);
        }
      }
    }
  }

  // Faixa de aviso acima do documento. Devolve o elemento.
  function faixa(mensagem, botoes) {
    const f = $("div", "ag-faixa");
    f.setAttribute("role", "alert");
    f.append($("span", null, mensagem));
    (botoes || []).forEach(([rotulo, aoClicar]) => f.append(botao(rotulo, "", aoClicar)));
    faixaEl.replaceChildren(f);
    barEl.hidden = false;
    return f;
  }

  function limparFaixa() {
    faixaEl.replaceChildren();
    barra();
  }

  // ---------- checklists que gravam ----------

  function ativarCaixas() {
    contentEl.querySelectorAll('input[type="checkbox"][data-linha]').forEach((cb) => {
      cb.disabled = !escrita;
      cb.setAttribute("aria-label", cb.parentElement.textContent.trim());
      cb.onchange = () => marcarCaixa(cb);
    });
  }

  // Uma gravação por vez: chamadas seguidas esperam a anterior e partem do texto já atualizado.
  // fn(texto) devolve o texto novo do arquivo, ou null se ele mudou e a alteração deve ser cancelada.
  // Devolve { ok: true } ou { ok: false, motivo: "mudou" | "conflito" | "erro", mensagem }. Nunca lança.
  let fila = Promise.resolve();
  function alterar(file, fn) {
    const r = fila.then(() => gravar(file, fn));
    fila = r.catch(() => {}); // um erro inesperado não trava as gravações seguintes
    return r;
  }

  async function gravar(file, fn) {
    const doc = docList().find((d) => d.file === file);
    const novo = doc && fn(doc.fallback);
    if (!novo) return { ok: false, motivo: "mudou", mensagem: "O arquivo mudou por fora." };
    try {
      const r = await AGWrite.salvar(file, novo, mtimes[file]);
      if (r.status !== 200) {
        return r.codigo === "conflito"
          ? { ok: false, motivo: "conflito", mensagem: "O arquivo mudou por fora." }
          : { ok: false, motivo: "erro", mensagem: r.erro };
      }
      mtimes[file] = r.mtime;
    } catch (e) {
      return { ok: false, motivo: "erro", mensagem: "Sem conexão com o servidor." };
    }
    try { await atualizar(); } catch (e) { /* gravou; a consulta periódica traz o resto */ }
    return { ok: true };
  }

  async function marcarCaixa(cb) {
    const doc = currentDoc();
    const linha = Number(cb.dataset.linha);
    const marcada = cb.checked;
    // a linha tem que ser ainda um item de checklist e ficar no estado que o clique pediu; senão o arquivo mudou
    const r = doc && await alterar(doc.file, (texto) => {
      const novo = AGWrite.alternarCaixa(texto, linha);
      return novo && /^\s*-\s+\[[xX]\]/.test(novo.split("\n")[linha]) === marcada ? novo : null;
    });
    if (r && r.ok) return;
    cb.checked = !marcada;
    if (r && r.motivo === "erro") return faixa(r.mensagem + " A caixa não foi alterada.");
    faixa("O arquivo mudou por fora. A caixa não foi alterada.", [
      ["Ver a nova versão", async () => { try { await atualizar(); repaintCurrent(); limparFaixa(); } catch (e) { /* a faixa segue */ } }],
    ]);
  }

  // ---------- integração com o app.js ----------

  // Chamado depois que um documento é desenhado.
  function aoAbrir() {
    limparFaixa();
    ativarCaixas();
  }

  // Chamado antes de abrir outro documento: com edição pendente, pergunta antes de descartar.
  function podeSair() {
    if (!edicao) return true;
    if (sujo() && !confirm("Descartar as alterações deste documento?")) return false;
    sairEdicao();
    return true;
  }

  async function init() {
    try {
      const p = await AGWrite.ping();
      if (p.status !== 200 || !p.escrita) return;
      await atualizar(); // mtimes e dados em dia (a página pode ter nascido de um content.js antigo)
    } catch (e) {
      return; // sem servidor com escrita: o site fica como sempre foi
    }
    escrita = true;
    const mais = document.getElementById("ag-plus");
    mais.hidden = false;
    if (typeof AGPainel !== "undefined") AGPainel.setEscrita(true);
    mais.addEventListener("click", abrirPaleta);
    document.addEventListener("keydown", (e) => {
      const tecla = e.key.toLowerCase();
      if ((e.ctrlKey || e.metaKey) && tecla === "k") {
        e.preventDefault();
        abrirPaleta();
      } else if ((e.ctrlKey || e.metaKey) && tecla === "s" && edicao) {
        e.preventDefault();
        salvarEdicao();
      }
    });
    window.addEventListener("beforeunload", (e) => { if (sujo()) { e.preventDefault(); e.returnValue = ""; } });
    barra();
    ativarCaixas();
    setTimeout(ciclo, 2000);
  }

  return {
    init, aoAbrir, podeSair, alterar, atualizar, faixa, abrirDialogo, dialogo,
    temEscrita: () => escrita,
    postitsDoDoc: (file) => postits[file] || [],
  };
})();
