// Tela do quadro Kanban. As regras (colunas, cartões, movimentos) estão em kanban-model.js.
//
// Lê os textos dos documentos que a página já tem (AG_CONTENT), então também aparece sem servidor,
// só para leitura. Com o servidor (AGEditor.temEscrita()), os cartões se movem por arrastar ou pelo
// seletor "Mover para…" (teclado e toque) e cada movimento grava no .md por AGEditor.alterar.

const AGBoard = (function () {
  const $ = (tag, cls, text) => {
    const e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text != null) e.textContent = text;
    return e;
  };

  const AVISO_ITEM = "Itens de checklist só ficam em A fazer ou Feito.";

  let raiz = null;       // <section> do quadro
  let btn = null;
  let colunasEl, contagemEl, leituraEl, statusEl, alertaEl, buscaEl, dicaEl;
  let aberto = false;
  let arrastando = null; // cartão em arraste
  let gravando = null;   // chave do cartão que está sendo gravado
  let foco = null;       // chave do cartão cujo seletor deve receber o foco depois de desenhar
  let consulta = "";     // texto da busca: sem ele a coluna Feito fica escondida
  const vistas = new Map(); // colunas personalizadas já vistas nesta sessão: chave -> rótulo (ficam mesmo vazias)

  const escrita = () => typeof AGEditor !== "undefined" && AGEditor.temEscrita();

  function quadro() {
    const tags = {};
    if (typeof AG_GRAPH !== "undefined") AG_GRAPH.docs.forEach((d) => { tags[d.id] = d.tags.curated; });
    const q = AGKanban.montarQuadro(docList(), tags, [...vistas.values()]);
    q.colunas.forEach((c) => { if (!c.fixa) vistas.set(c.chave, c.rotulo); });
    return q;
  }

  function avisar(msg) { alertaEl.textContent = ""; statusEl.textContent = msg; }
  function alertar(msg) { statusEl.textContent = ""; alertaEl.textContent = msg; }

  // ---------- mover ----------

  async function mover(cartao, coluna, viaSeletor) {
    if (!AGKanban.destinoPermitido(cartao, coluna.chave)) {
      if (cartao.coluna !== coluna.chave) avisar(AVISO_ITEM);
      return;
    }
    gravando = cartao.chave;
    desenhar();
    const r = await AGEditor.alterar(cartao.arquivo, (texto) => AGKanban.moverCartao(cartao, coluna, texto));
    gravando = null;
    foco = viaSeletor ? cartao.chave : null;
    if (r.ok) {
      avisar("Movido para " + coluna.rotulo + ".");
    } else {
      alertar((r.motivo === "erro" ? r.mensagem : "O arquivo mudou por fora.") + " O cartão não foi movido.");
      if (r.motivo !== "erro") AGEditor.atualizar().catch(() => {}); // a página pode estar atrás do arquivo
    }
    desenhar();
  }

  // ---------- desenho ----------

  function cartaoEl(c, q) {
    const li = $("li", "kb-cartao " + (c.tipo === "nota" ? "kb-nota" : "kb-item") + (gravando === c.chave ? " kb-gravando" : ""));
    li.dataset.chave = c.chave;
    if (gravando === c.chave) li.setAttribute("aria-busy", "true");

    let nome; // como o cartão se chama para o leitor de tela
    if (c.tipo === "nota") {
      nome = c.titulo;
      const a = $("a", "kb-titulo", c.titulo);
      a.href = "#" + c.id;
      li.append(a);
      if (c.tags.length) {
        const tags = $("div", "kb-tags");
        c.tags.slice(0, 3).forEach((t) => tags.append($("span", "kb-tag", t)));
        if (c.tags.length > 3) tags.append($("span", "kb-tag", "+" + (c.tags.length - 3)));
        li.append(tags);
      }
    } else {
      nome = c.texto.length > 60 ? c.texto.slice(0, 60) + "…" : c.texto;
      const caixa = $("span", "kb-caixa", c.feito ? "☑" : "☐");
      caixa.setAttribute("role", "img");
      caixa.setAttribute("aria-label", c.feito ? "Feito" : "A fazer");
      const texto = $("span", "kb-texto");
      texto.innerHTML = inlineMd(c.texto);
      const linha = $("div", "kb-linha");
      linha.append(caixa, texto);
      li.append(linha);
    }

    const rodape = $("div", "kb-rodape");
    if (c.tipo === "nota") {
      rodape.append($("span", "kb-origem", c.pasta || agTexto("home", "Home")));
    } else {
      const a = $("a", "kb-origem", c.docTitulo);
      a.href = "#" + c.docId;
      rodape.append(a);
    }

    if (escrita()) {
      li.draggable = true;
      li.addEventListener("dragstart", (e) => {
        arrastando = c;
        e.dataTransfer.effectAllowed = "move";
        e.dataTransfer.setData("text/plain", c.chave);
        li.classList.add("kb-arrastando");
        // Feito está escondida: durante o arraste ela aparece como zona de soltura, para dar para concluir o cartão
        if (!colunasEl.querySelector('.kb-col[data-chave="feito"]') && AGKanban.destinoPermitido(c, "feito")) {
          colunasEl.append(colunaEl({ ...q.colunas.find((x) => x.chave === "feito"), cartoes: [] }, "zona", q, true));
        }
      });
      li.addEventListener("dragend", () => {
        arrastando = null;
        li.classList.remove("kb-arrastando");
        colunasEl.querySelectorAll(".kb-zona").forEach((e) => e.remove());
        colunasEl.querySelectorAll(".kb-alvo").forEach((e) => e.classList.remove("kb-alvo"));
      });
      const sel = $("select", "kb-mover");
      sel.setAttribute("aria-label", "Mover «" + nome + "» para");
      sel.append(new Option("Mover para…", ""));
      q.colunas.forEach((col) => {
        const o = new Option(col.chave === c.coluna ? col.rotulo + " (atual)" : col.rotulo, col.chave);
        o.disabled = !AGKanban.destinoPermitido(c, col.chave);
        sel.append(o);
      });
      sel.addEventListener("change", () => {
        const col = q.colunas.find((x) => x.chave === sel.value);
        sel.value = "";
        if (col) mover(c, col, true);
      });
      rodape.append(sel);
    }
    li.append(rodape);
    return li;
  }

  // zona = coluna Feito escondida, mostrada só durante o arraste (sem os cartões dela)
  function colunaEl(col, i, q, zona) {
    const sec = $("section", "kb-col" + (zona ? " kb-zona" : ""));
    sec.setAttribute("role", "group");
    sec.dataset.chave = col.chave;
    const cab = $("div", "kb-col-cab");
    const titulo = $("h3", null, col.rotulo);
    titulo.id = "kb-col-" + i;
    sec.setAttribute("aria-labelledby", titulo.id);
    cab.append(titulo, $("span", "kb-n", String(col.cartoes.length)));
    const corpo = $("ul", "kb-corpo");
    if (col.cartoes.length) col.cartoes.forEach((c) => corpo.append(cartaoEl(c, q)));
    else corpo.append($("li", "kb-vazio", zona ? "Solte aqui para concluir" : "Nenhum cartão"));
    sec.append(cab, corpo);

    if (escrita()) {
      // a coluna aceita o cartão em arraste? (item de checklist só vai para A fazer ou Feito)
      const aceita = () => arrastando && AGKanban.destinoPermitido(arrastando, col.chave);
      sec.addEventListener("dragover", (e) => {
        if (!aceita()) return;
        e.preventDefault();
        e.dataTransfer.dropEffect = "move";
        sec.classList.add("kb-alvo");
      });
      sec.addEventListener("dragenter", () => {
        if (arrastando && !aceita() && arrastando.coluna !== col.chave) avisar(AVISO_ITEM);
      });
      sec.addEventListener("dragleave", (e) => { if (!sec.contains(e.relatedTarget)) sec.classList.remove("kb-alvo"); });
      sec.addEventListener("drop", (e) => {
        e.preventDefault();
        sec.classList.remove("kb-alvo");
        // o cartão vem no próprio arraste: solturas de fora (texto, arquivo) ou de um arraste antigo não movem nada
        const c = arrastando && e.dataTransfer.getData("text/plain") === arrastando.chave ? arrastando : null;
        arrastando = null; // o quadro se redesenha e o cartão sai da página antes do dragend
        if (c && AGKanban.destinoPermitido(c, col.chave)) mover(c, col, false);
      });
    }
    return sec;
  }

  function desenhar() {
    if (!aberto) return;
    const q = quadro();
    const v = AGKanban.filtrarQuadro(q, consulta);
    // guarda a rolagem: horizontal do quadro e vertical de cada coluna
    const x = colunasEl.scrollLeft;
    const y = {};
    colunasEl.querySelectorAll(".kb-col").forEach((s) => { y[s.dataset.chave] = s.querySelector(".kb-corpo").scrollTop; });

    colunasEl.replaceChildren(...v.colunas.map((col, i) => colunaEl(col, i, q)));
    colunasEl.scrollLeft = x;
    colunasEl.querySelectorAll(".kb-col").forEach((s) => { s.querySelector(".kb-corpo").scrollTop = y[s.dataset.chave] || 0; });

    const total = v.colunas.reduce((n, c) => n + c.cartoes.length, 0);
    contagemEl.textContent = total + (v.busca ? (total === 1 ? " encontrado" : " encontrados") : (total === 1 ? " cartão" : " cartões"));
    const n = v.feitosOcultos;
    dicaEl.textContent = n ? `${n} ${n === 1 ? "cartão feito oculto" : "cartões feitos ocultos"}. Busque para ver.` : "";
    dicaEl.hidden = !n;
    leituraEl.hidden = escrita();

    if (foco) {
      const li = [...colunasEl.querySelectorAll(".kb-cartao")].find((e) => e.dataset.chave === foco);
      if (li) li.querySelector("select").focus();
      else raiz.focus({ preventScroll: true }); // o cartão foi para a coluna escondida: o foco fica no quadro
      foco = null;
    }
  }

  // ---------- abrir e fechar ----------

  function montar() {
    raiz = document.getElementById("kb-view");
    raiz.setAttribute("role", "region");
    raiz.setAttribute("aria-label", "Quadro");
    const cab = $("div", "kb-cab");
    contagemEl = $("span", "kb-contagem");
    buscaEl = $("input", "kb-busca");
    buscaEl.type = "search";
    buscaEl.autocomplete = "off";
    buscaEl.placeholder = "Buscar (inclui os feitos)";
    buscaEl.setAttribute("aria-label", "Buscar no quadro");
    buscaEl.addEventListener("input", () => { consulta = buscaEl.value; desenhar(); });
    cab.append($("h2", null, "Quadro"), contagemEl, buscaEl);
    dicaEl = $("p", "kb-dica");
    dicaEl.hidden = true;
    leituraEl = $("p", "kb-leitura", "Somente leitura: abra pelo start para mover cartões.");
    statusEl = $("p", "kb-aviso");
    statusEl.setAttribute("role", "status");
    alertaEl = $("p", "kb-aviso kb-erro");
    alertaEl.setAttribute("role", "alert");
    colunasEl = $("div", "kb-colunas");
    raiz.tabIndex = -1; // recebe o foco quando o cartão movido sai de vista
    raiz.append(cab, dicaEl, leituraEl, statusEl, alertaEl, colunasEl);
    // Rolagem automática nas bordas durante o arraste. A do navegador escolhe a lista de cartões da coluna sob o
    // mouse (que rola na vertical) e deixa o quadro parado; sem isto, não se chega a uma coluna fora da tela.
    colunasEl.addEventListener("dragover", (e) => {
      if (!arrastando) return;
      const r = colunasEl.getBoundingClientRect();
      if (e.clientX < r.left + 60) colunasEl.scrollLeft -= 18;
      else if (e.clientX > r.right - 60) colunasEl.scrollLeft += 18;
    });
  }

  function open() {
    if (!raiz) montar();
    if (typeof AGView !== "undefined") AGView.close();
    aberto = true;
    document.body.classList.add("board-open");
    raiz.hidden = false;
    btn.classList.add("on");
    btn.setAttribute("aria-pressed", "true");
    statusEl.textContent = alertaEl.textContent = "";
    consulta = buscaEl.value = "";
    desenhar();
    if (typeof setMenu === "function") setMenu(false); // celular: o quadro aparece logo abaixo dos botões
    if (window.matchMedia("(max-width: 860px)").matches) raiz.scrollIntoView();
  }

  function close() {
    if (!aberto) return;
    aberto = false;
    document.body.classList.remove("board-open");
    raiz.hidden = true;
    btn.classList.remove("on");
    btn.setAttribute("aria-pressed", "false");
  }

  // Aviso geral vindo de fora (servidor parado): a barra de avisos do documento fica escondida com o quadro aberto.
  function aviso(msg) {
    if (raiz) alertar(msg);
  }

  // Chamado quando a lista de documentos ou o estado da escrita mudou.
  function reload() {
    desenhar();
  }

  function init() {
    btn = document.getElementById("kb-btn");
    if (!btn || !document.getElementById("kb-view")) return;
    btn.addEventListener("click", () => (aberto ? close() : open()));
    // abrir o grafo fecha o quadro (o grafo já trata o próprio botão)
    const grafo = document.getElementById("graph-btn");
    if (grafo) grafo.addEventListener("click", close);
  }

  return { init, open, close, reload, aviso };
})();
