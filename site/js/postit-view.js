// Camada de post-its do documento aberto. As regras (posição, tamanho, cor) estão em postit-model.js.
//
// A "superfície" dos post-its é a própria camada (.pi-camada): um item do grid do .shell, colado ao
// lado de <main> (mesma coluna, mesma linha), então cobre toda a largura à direita da barra lateral —
// não só o .panel do documento — e a mesma altura de <main>. x/y de cada post-it são relativos a ela.
//
// Cada post-it grava sozinho por AGEditor: sem base_mtime e sem aviso de conflito (peça 3, seção 6) —
// duas janelas mexendo em post-its diferentes do mesmo documento não se sobrescrevem.

const AGPostit = (function () {
  const $ = (tag, cls, text) => {
    const e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text != null) e.textContent = text;
    return e;
  };

  const NOME_COR = { amarelo: "Amarelo", verde: "Verde", azul: "Azul", rosa: "Rosa", laranja: "Laranja" };

  let camadaEl = null;   // .pi-camada: a superfície inteira (grid item ao lado de <main>)
  let statusEl = null;   // role="status" para os anúncios
  let oculta = false;    // preferência do navegador (ag-postits-ocultos)
  let arrastando = null; // id do post-it em arraste/redimensionamento — trava o redesenho
  let focoTexto = null;  // id do post-it com foco na caixa de texto — trava o redesenho
  let ultimaChave = null; // instantâneo do que está desenhado, para não redesenhar à toa
  let fila = Promise.resolve(); // uma gravação de post-it por vez, nesta janela

  try { oculta = localStorage.getItem("ag-postits-ocultos") === "1"; } catch (e) { /* sem storage: começa visível */ }

  // ---------- utilidades ----------

  function superficie() { return camadaEl; } // mede a própria camada: ela já tem o tamanho da área útil

  function anunciar(msg) {
    if (!statusEl) return;
    statusEl.textContent = "";
    requestAnimationFrame(() => { statusEl.textContent = msg; });
  }

  function doc() { return typeof currentDoc === "function" ? currentDoc() : null; }

  function lista(file) {
    return file && typeof AGEditor !== "undefined" ? AGEditor.postitsDoDoc(file) : [];
  }

  // ---------- gravação (uma de cada vez; erro vai para a faixa do documento) ----------

  function enfileirar(fn) {
    const r = fila.then(fn, fn);
    fila = r.catch(() => {});
    return r;
  }

  function salvar(file, postit) {
    return enfileirar(async () => {
      try {
        const r = await AGWrite.postit(file, postit);
        if (r.status !== 200) {
          if (typeof AGEditor !== "undefined") AGEditor.faixa("Não foi possível gravar o post-it: " + r.erro);
          return false;
        }
      } catch (e) {
        if (typeof AGEditor !== "undefined") AGEditor.faixa("Sem conexão com o servidor. O post-it fica como está.");
        return false;
      }
      try { await AGEditor.atualizar(); } catch (e) { /* gravou; a consulta periódica traz o resto */ }
      return true;
    });
  }

  function apagar(file, id) {
    return enfileirar(async () => {
      try {
        const r = await AGWrite.apagarPostit(file, id);
        if (r.status !== 200 && typeof AGEditor !== "undefined") {
          AGEditor.faixa("Não foi possível apagar o post-it: " + r.erro);
        }
      } catch (e) {
        if (typeof AGEditor !== "undefined") AGEditor.faixa("Sem conexão com o servidor. O post-it não foi apagado.");
        return false;
      }
      try { await AGEditor.atualizar(); } catch (e) { /* gravou; a consulta periódica traz o resto */ }
      return true;
    });
  }

  // ---------- um post-it ----------

  function posicionar(nota, p) {
    const sup = superficie();
    if (!sup) return;
    const { left, top } = AGPostitModel.posicaoParaPx(p, sup.clientWidth, sup.clientHeight, p.w, p.h);
    nota.style.left = left + "px";
    nota.style.top = top + "px";
  }

  function ligarArraste(nota, p, file, alca) {
    let inicio = null;
    alca.addEventListener("pointerdown", (e) => {
      if (!AGEditor.temEscrita()) return;
      const sup = superficie();
      if (!sup) return;
      e.preventDefault();
      alca.setPointerCapture(e.pointerId);
      const r = sup.getBoundingClientRect();
      inicio = { dx: e.clientX - nota.offsetLeft - r.left, dy: e.clientY - nota.offsetTop - r.top };
      arrastando = p.id;
      nota.classList.add("pi-arrastando");
    });
    alca.addEventListener("pointermove", (e) => {
      if (arrastando !== p.id || !inicio) return;
      const r = superficie().getBoundingClientRect();
      nota.style.left = (e.clientX - r.left - inicio.dx) + "px";
      nota.style.top = (e.clientY - r.top - inicio.dy) + "px";
    });
    const soltar = () => {
      if (arrastando !== p.id) return;
      arrastando = null;
      inicio = null;
      nota.classList.remove("pi-arrastando");
      const sup = superficie();
      const { x, y } = AGPostitModel.pxParaPosicao(nota.offsetLeft, nota.offsetTop, sup.clientWidth, sup.clientHeight, p.w, p.h);
      p.x = x; p.y = y;
      salvar(file, p);
    };
    alca.addEventListener("pointerup", soltar);
    alca.addEventListener("pointercancel", soltar);

    let espera;
    alca.addEventListener("keydown", (e) => {
      if (!AGEditor.temEscrita()) return;
      const passo = { ArrowLeft: [-1, 0], ArrowRight: [1, 0], ArrowUp: [0, -1], ArrowDown: [0, 1] }[e.key];
      if (!passo) return;
      e.preventDefault();
      const salto = e.shiftKey ? 48 : 12;
      const sup = superficie();
      const { x, y } = AGPostitModel.pxParaPosicao(
        nota.offsetLeft + passo[0] * salto, nota.offsetTop + passo[1] * salto,
        sup.clientWidth, sup.clientHeight, p.w, p.h,
      );
      const px = AGPostitModel.posicaoParaPx({ x, y }, sup.clientWidth, sup.clientHeight, p.w, p.h);
      nota.style.left = px.left + "px";
      nota.style.top = px.top + "px";
      arrastando = p.id; // trava o redesenho até a gravação (400 ms depois da última seta)
      clearTimeout(espera);
      espera = setTimeout(() => {
        arrastando = null;
        p.x = x; p.y = y;
        salvar(file, p);
        anunciar("Post-it movido");
      }, 400);
    });
  }

  // Alça no canto inferior direito: redimensiona por Pointer Events (mouse, toque, caneta) ou setas
  // (com foco na alça), do mesmo jeito que mover — só que muda w/h em vez de x/y.
  function ligarRedimensionar(nota, p, file, alca) {
    let inicio = null;
    alca.addEventListener("pointerdown", (e) => {
      if (!AGEditor.temEscrita()) return;
      e.preventDefault();
      e.stopPropagation();
      alca.setPointerCapture(e.pointerId);
      inicio = { x: e.clientX, y: e.clientY, w: nota.offsetWidth, h: nota.offsetHeight };
      arrastando = p.id;
      nota.classList.add("pi-arrastando");
    });
    alca.addEventListener("pointermove", (e) => {
      if (arrastando !== p.id || !inicio) return;
      const { w, h } = AGPostitModel.tamanhoValido(inicio.w + (e.clientX - inicio.x), inicio.h + (e.clientY - inicio.y));
      nota.style.width = w + "px";
      nota.style.height = h + "px";
    });
    const soltar = () => {
      if (arrastando !== p.id) return;
      arrastando = null;
      inicio = null;
      nota.classList.remove("pi-arrastando");
      const { w, h } = AGPostitModel.tamanhoValido(nota.offsetWidth, nota.offsetHeight);
      p.w = w; p.h = h;
      salvar(file, p);
    };
    alca.addEventListener("pointerup", soltar);
    alca.addEventListener("pointercancel", soltar);

    let espera;
    alca.addEventListener("keydown", (e) => {
      if (!AGEditor.temEscrita()) return;
      const passo = { ArrowLeft: [-1, 0], ArrowRight: [1, 0], ArrowUp: [0, -1], ArrowDown: [0, 1] }[e.key];
      if (!passo) return;
      e.preventDefault();
      const salto = e.shiftKey ? 48 : 12;
      const { w, h } = AGPostitModel.tamanhoValido(nota.offsetWidth + passo[0] * salto, nota.offsetHeight + passo[1] * salto);
      nota.style.width = w + "px";
      nota.style.height = h + "px";
      arrastando = p.id;
      clearTimeout(espera);
      espera = setTimeout(() => {
        arrastando = null;
        p.w = w; p.h = h;
        salvar(file, p);
        anunciar("Post-it redimensionado");
      }, 400);
    });
  }

  function notaEl(p, file, escrita) {
    const nota = $("div", "pi-nota pi-" + p.cor);
    nota.dataset.id = p.id;
    nota.style.width = p.w + "px";
    nota.style.height = p.h + "px";

    const cab = $("div", "pi-cab");
    const alca = $("button", "pi-alca");
    alca.type = "button";
    alca.setAttribute("aria-label", "Mover post-it, use as setas");
    alca.disabled = !escrita;

    const cor = $("button", "pi-cor");
    cor.type = "button";
    cor.setAttribute("aria-label", "Cor: " + NOME_COR[p.cor]);
    cor.disabled = !escrita;
    cor.addEventListener("click", () => {
      p.cor = AGPostitModel.proximaCor(p.cor);
      nota.className = "pi-nota pi-" + p.cor;
      cor.setAttribute("aria-label", "Cor: " + NOME_COR[p.cor]);
      salvar(file, p);
    });

    const fechar = $("button", "pi-fechar", "×");
    fechar.type = "button";
    fechar.setAttribute("aria-label", "Apagar post-it");
    fechar.disabled = !escrita;
    fechar.addEventListener("click", () => {
      if (ta.value && !confirm("Apagar este post-it?")) return;
      nota.remove();
      apagar(file, p.id);
    });

    cab.append(alca, cor, fechar);

    const ta = $("textarea", "pi-corpo");
    ta.maxLength = 1000;
    ta.readOnly = !escrita;
    ta.setAttribute("aria-label", "Texto do post-it");
    ta.value = p.texto;

    let espera;
    const gravarTexto = () => { clearTimeout(espera); p.texto = ta.value; salvar(file, p); };
    ta.addEventListener("input", () => { clearTimeout(espera); espera = setTimeout(gravarTexto, 600); });
    ta.addEventListener("focus", () => { focoTexto = p.id; });
    ta.addEventListener("blur", () => { if (focoTexto === p.id) focoTexto = null; gravarTexto(); });

    const redim = $("button", "pi-redim");
    redim.type = "button";
    redim.setAttribute("aria-label", "Redimensionar post-it, use as setas");
    redim.disabled = !escrita;

    nota.append(cab, ta, redim);
    if (escrita) { ligarArraste(nota, p, file, alca); ligarRedimensionar(nota, p, file, redim); }
    posicionar(nota, p);
    return nota;
  }

  // ---------- criar ----------

  function criar(file, p, focar) {
    if (oculta) { oculta = false; try { localStorage.setItem("ag-postits-ocultos", "0"); } catch (e) { /* ignora */ } }
    camadaEl.hidden = false;
    const nota = notaEl(p, file, true);
    camadaEl.append(nota);
    ultimaChave = null; // força o próximo reload a confirmar contra o servidor
    anunciar("Post-it criado");
    if (focar) nota.querySelector("textarea").focus();
    salvar(file, p);
  }

  function criarNaTela() {
    if (!AGEditor.temEscrita()) return;
    const d = doc();
    if (!d || document.body.classList.contains("ag-editando")) return;
    criar(d.file, AGPostitModel.novoPostit(62, 80), true);
  }

  // Botão "＋ Post-it": clique cria na tela; arrastar (HTML5, como os cartões do quadro) e soltar cria
  // onde soltou — em qualquer ponto da superfície, inclusive à direita do painel do documento.
  function ligarBotaoCriar(btn) {
    let arrastou = false;
    btn.draggable = true;
    btn.addEventListener("click", () => { if (!arrastou) criarNaTela(); });
    btn.addEventListener("dragstart", (e) => {
      if (!AGEditor.temEscrita()) { e.preventDefault(); return; }
      arrastou = true;
      if (camadaEl) camadaEl.classList.add("pi-recebendo"); // só durante o arraste ela aceita clique/soltura
      e.dataTransfer.effectAllowed = "copy";
      e.dataTransfer.setData("text/plain", "novo-postit");
    });
    btn.addEventListener("dragend", () => {
      if (camadaEl) camadaEl.classList.remove("pi-recebendo");
      setTimeout(() => { arrastou = false; }, 0);
    });
  }

  function ligarSoltura(sup) {
    sup.addEventListener("dragover", (e) => {
      if ([...e.dataTransfer.types].includes("text/plain")) e.preventDefault();
    });
    sup.addEventListener("drop", (e) => {
      if (e.dataTransfer.getData("text/plain") !== "novo-postit") return;
      e.preventDefault();
      const d = doc();
      if (!d || !AGEditor.temEscrita() || document.body.classList.contains("ag-editando")) return;
      const r = sup.getBoundingClientRect();
      const { x, y } = AGPostitModel.pxParaPosicao(
        e.clientX - r.left - AGPostitModel.LARGURA_PADRAO / 2, e.clientY - r.top - 16,
        sup.clientWidth, sup.clientHeight, AGPostitModel.LARGURA_PADRAO, AGPostitModel.ALTURA_PADRAO,
      );
      criar(d.file, AGPostitModel.novoPostit(x, y), false);
    });
  }

  // ---------- ocultar / mostrar ----------

  function estaOculto() { return oculta; }

  function contagem() {
    const d = doc();
    return d ? lista(d.file).length : 0;
  }

  function alternarOcultar() {
    oculta = !oculta;
    try { localStorage.setItem("ag-postits-ocultos", oculta ? "1" : "0"); } catch (e) { /* só vale nesta visita */ }
    if (camadaEl) camadaEl.hidden = oculta;
  }

  // ---------- desenho ----------

  function desenhar(file, itens, escrita) {
    camadaEl.replaceChildren();
    camadaEl.hidden = oculta;
    itens.forEach((p) => camadaEl.append(notaEl(p, file, escrita)));
  }

  // Redesenha só se a lista do documento aberto (ou o estado de escrita) mudou, e nunca com um post-it
  // em arraste, redimensionamento ou com foco de digitação: a atualização espera o fim do gesto.
  function talvezDesenhar() {
    if (!camadaEl) return;
    const d = doc();
    const file = d && d.file;
    const escrita = typeof AGEditor !== "undefined" && AGEditor.temEscrita();
    const itens = lista(file);
    const chave = file + "|" + escrita + "|" + JSON.stringify(itens);
    if (chave === ultimaChave) return;
    if (arrastando || focoTexto) return; // tenta de novo no próximo reload()
    ultimaChave = chave;
    desenhar(file, itens, escrita);
  }

  // ---------- integração ----------

  function aoAbrir() {
    if (!camadaEl) return;
    ultimaChave = null; // documento novo: nada em arraste/foco dele, redesenha sempre
    talvezDesenhar();
  }

  function reload() { talvezDesenhar(); }

  function init() {
    const shell = document.querySelector(".shell");
    if (!shell) return;
    camadaEl = $("div", "pi-camada");
    camadaEl.setAttribute("role", "region");
    camadaEl.setAttribute("aria-label", "Post-its deste documento");
    camadaEl.hidden = true;
    shell.append(camadaEl); // item do grid do .shell, na mesma coluna/linha de <main> (ver style.css)
    statusEl = $("p", "pi-status");
    statusEl.setAttribute("role", "status");
    document.body.append(statusEl);
    ligarSoltura(camadaEl);
    window.addEventListener("resize", () => { ultimaChave = null; talvezDesenhar(); });
  }

  return { init, aoAbrir, reload, criarNaTela, ligarBotaoCriar, alternarOcultar, estaOculto, contagem };
})();

if (typeof module !== "undefined") module.exports = AGPostit;
