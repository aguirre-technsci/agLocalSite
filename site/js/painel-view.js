// Painel "⚙ Configurar": edita as opções seguras do config.json (título, rótulos, paleta, pastas) sem abrir arquivo nenhum.
// Contrato e regras: docs/specs/2026-11-21-painel-de-configuracoes-design.md. A lógica pura fica em painel-model.js; o servidor valida tudo de novo.
// Tudo que vem do config entra na tela por textContent/value (nunca innerHTML). raiz, prefixo_url e porta só aparecem como leitura.

const AGPainel = (function () {
  const M = AGPainelModel;
  const $ = (tag, cls, text) => {
    const e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text != null) e.textContent = text;
    return e;
  };
  const copia = (o) => JSON.parse(JSON.stringify(o === undefined ? null : o));

  const btn = document.getElementById("cfg-btn");
  const ROTULOS_TEXTO = [
    ["grafo", "Botão do grafo de tags"], ["quadro", "Botão do quadro"], ["mais", "Botão da barra de comandos"], ["menu", "Botão do menu (celular)"],
    ["tema_claro", "Botão de tema, quando o site está escuro"], ["tema_escuro", "Botão de tema, quando o site está claro"],
    ["home", "Nome do grupo dos .md soltos na raiz"],
  ];
  const MODOS = [["claro", "Claro"], ["escuro", "Escuro"], ["sistema", "Seguir o sistema"]];

  let escrita = false;
  let est = null;      // último estado do servidor (GET /api/config)
  let orig = {};       // valores no arquivo (base para saber o que mudou)
  let cur = {};        // valores em edição
  let aberto = null;   // { fechar, raiz, previaAntes } enquanto o diálogo está na tela
  let avisoEl = null, salvarEl = null, desfazerEl = null, padroesEl = null, erros = {};

  function setEscrita(ativa) {
    escrita = ativa;
    if (btn) btn.hidden = !ativa;
    if (!ativa && aberto) aberto.fechar();   // o servidor parou: o painel não faz mais sentido
  }

  // ---------- prévia de paleta e modo ----------

  function sistemaEscuro() {
    try { return !!(window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches); } catch (e) { return false; }
  }
  function storage() { try { return window.localStorage; } catch (e) { return null; } }
  function repintar() {
    if (typeof paintThemeBtn === "function") paintThemeBtn();
    if (typeof AGView !== "undefined") AGView.applyTheme();
  }
  function previa() {
    const t = cur.tema || {};
    AGTema.aplicar(document.documentElement, { paleta: t.paleta, modo: t.modo, pessoal: null, sistemaEscuro: sistemaEscuro(), paletas: est.paletas.map((p) => p.nome) });
    repintar();
  }
  function restaurarPrevia() {
    if (!aberto) return;
    const h = document.documentElement.dataset, a = aberto.previaAntes;
    if (a.theme === undefined) delete h.theme; else h.theme = a.theme;
    if (a.palette === undefined) delete h.palette; else h.palette = a.palette;
    repintar();
  }
  function lerPrevia() { const h = document.documentElement.dataset; return { theme: h.theme, palette: h.palette }; }

  // ---------- campos ----------

  function campo(rotulo, filho, erroChave) {
    const l = $("label", "ag-campo");
    l.append($("span", null, rotulo), filho);
    const e = $("div", "ag-erro");
    e.setAttribute("role", "alert");
    if (erroChave) erros[erroChave] = e;
    l.append(e);
    return l;
  }
  function erroEm(chave, msg) { if (erros[chave]) erros[chave].textContent = msg || ""; }

  function entrada(valor, padrao, aoMudar) {
    const i = $("input");
    i.type = "text";
    i.value = valor || "";
    if (padrao) i.placeholder = padrao;
    i.addEventListener("input", () => aoMudar(i.value));
    return i;
  }

  // texto simples (titulo, subtitulo...) dentro de cur
  function campoTexto(chave, rotulo) {
    const i = entrada(cur[chave], est.padroes[chave], (v) => {
      if (v.trim() === "") delete cur[chave]; else cur[chave] = v;
      erroEm(chave, M.validarCampo(chave, v, est.limites));
    });
    return campo(rotulo, i, chave);
  }

  function textoDe(chave) { return (cur.textos && cur.textos[chave]) || ""; }
  function definirTexto(chave, v) {
    cur.textos = cur.textos || {};
    if (v === undefined || (chave !== "rodape" && v.trim() === "")) delete cur.textos[chave]; else cur.textos[chave] = v;
    if (!Object.keys(cur.textos).length) delete cur.textos;
  }

  function campoTextoUi(chave, rotulo) {
    const linha = $("div", "cfg-linha");
    const i = entrada(textoDe(chave), est.padroes.textos[chave], (v) => {
      definirTexto(chave, v);
      erroEm("textos." + chave, M.validarCampo("textos." + chave, v, est.limites));
    });
    const reset = $("button", "ag-btn cfg-mini", "padrão");
    reset.type = "button";
    reset.title = "Voltar ao texto padrão";
    reset.addEventListener("click", () => { i.value = ""; definirTexto(chave, undefined); erroEm("textos." + chave, ""); i.focus(); });
    linha.append(i, reset);
    return campo(rotulo, linha, "textos." + chave);
  }

  function blocoRodape() {
    const caixa = $("div", "ag-campo");
    caixa.append($("span", null, "Rodapé"));
    const grupo = $("div", "cfg-radios");
    grupo.setAttribute("role", "radiogroup");
    grupo.setAttribute("aria-label", "Rodapé");
    const area = $("textarea");
    area.rows = 3;
    area.value = cur.textos && typeof cur.textos.rodape === "string" && cur.textos.rodape !== "" ? cur.textos.rodape : "";
    let estado = M.rodapeEstado(cur.textos);
    const aplica = () => {
      area.hidden = estado !== "personalizado";
      const v = M.rodapeValor(estado, area.value);
      definirTexto("rodape", v === null ? undefined : v);
      erroEm("textos.rodape", estado === "personalizado" ? M.validarCampo("rodape", area.value, est.limites) : "");
    };
    for (const [valor, nome] of [["padrao", "Padrão (explica os atalhos)"], ["ocultar", "Ocultar"], ["personalizado", "Personalizado"]]) {
      const l = $("label", "cfg-radio");
      const r = $("input");
      r.type = "radio"; r.name = "cfg-rodape"; r.value = valor; r.checked = estado === valor;
      r.addEventListener("change", () => { estado = valor; aplica(); if (valor === "personalizado") area.focus(); });
      l.append(r, $("span", null, nome));
      grupo.append(l);
    }
    area.addEventListener("input", aplica);
    aplica();
    caixa.append(grupo, area);
    const e = $("div", "ag-erro");
    e.setAttribute("role", "alert");
    erros["textos.rodape"] = e;
    caixa.append(e);
    return caixa;
  }

  // ---------- aparência ----------

  function blocoAparencia() {
    const caixa = $("div");
    const t = () => cur.tema || {};
    const definir = (sub, valor, padrao) => {
      cur.tema = cur.tema || {};
      if (valor === padrao) delete cur.tema[sub]; else cur.tema[sub] = valor;
      if (!Object.keys(cur.tema).length) delete cur.tema;
      previa();
    };
    const modo = $("select");
    for (const [v, n] of MODOS) { const o = $("option", null, n); o.value = v; modo.append(o); }
    modo.value = t().modo || "claro";
    modo.addEventListener("change", () => definir("modo", modo.value, "claro"));
    caixa.append(campo("Modo inicial (a escolha de cada visitante no botão Claro/Escuro vale mais)", modo));

    const pal = $("div", "ag-campo");
    pal.append($("span", null, "Paleta (a página já mostra a escolhida)"));
    const grupo = $("div", "cfg-radios");
    grupo.setAttribute("role", "radiogroup");
    grupo.setAttribute("aria-label", "Paleta");
    for (const p of est.paletas) {
      const l = $("label", "cfg-radio");
      const r = $("input");
      r.type = "radio"; r.name = "cfg-paleta"; r.value = p.nome; r.checked = (t().paleta || "padrao") === p.nome;
      r.addEventListener("change", () => definir("paleta", p.nome, "padrao"));
      l.append(r, $("span", null, p.rotulo));
      grupo.append(l);
    }
    pal.append(grupo);
    caixa.append(pal);
    return caixa;
  }

  // ---------- pastas ----------

  function listaDeNomes(chave, titulo, vazioEhPadrao, ajuda, ordenavel) {
    const caixa = $("div", "ag-campo");
    caixa.append($("span", null, titulo));
    if (ajuda) caixa.append($("p", "ag-dica cfg-dica", ajuda));
    const lista = $("ul", "cfg-itens");
    const ler = () => (Array.isArray(cur[chave]) ? cur[chave] : (ordenavel ? copia(est.padroes[chave]) : []));
    const gravar = (l) => { if (!l.length && vazioEhPadrao) delete cur[chave]; else cur[chave] = l; };
    const desenhar = () => {
      lista.textContent = "";
      ler().forEach((nome, i, l) => {
        const li = $("li", "cfg-item");
        li.append($("span", "cfg-nome", nome));
        const acao = (txt, rot, fn, off) => {
          const b = $("button", "ag-btn cfg-mini", txt);
          b.type = "button"; b.setAttribute("aria-label", rot + " " + nome); b.disabled = !!off;
          b.addEventListener("click", fn);
          li.append(b);
        };
        if (ordenavel) {
          acao("↑", "Subir", () => { gravar(M.moverItem(ler(), i, -1)); desenhar(); }, i === 0);
          acao("↓", "Descer", () => { gravar(M.moverItem(ler(), i, 1)); desenhar(); }, i === l.length - 1);
        }
        acao("✕", "Remover", () => { gravar(ler().filter((_, j) => j !== i)); desenhar(); });
        lista.append(li);
      });
    };
    const novo = $("input");
    novo.type = "text";
    novo.placeholder = "adicionar nome";
    const add = $("button", "ag-btn cfg-mini", "adicionar");
    add.type = "button";
    const incluir = () => {
      const v = novo.value.trim();
      if (!v) return;
      const msg = M.validarCampo(chave, v, est.limites) || (ler().includes(v) ? "Esse nome já está na lista." : null);
      erroEm(chave, msg);
      if (msg) return;
      gravar(ler().concat([v]));
      novo.value = "";
      desenhar();
    };
    add.addEventListener("click", incluir);
    novo.addEventListener("keydown", (e) => { if (e.key === "Enter") { e.preventDefault(); incluir(); } });
    const linha = $("div", "cfg-linha");
    linha.append(novo, add);
    caixa.append(lista, linha);
    if (ordenavel) {
      const usar = $("button", "ag-btn cfg-mini", "usar a ordem padrão");
      usar.type = "button";
      usar.addEventListener("click", () => { delete cur[chave]; desenhar(); });
      caixa.append(usar);
    }
    const e = $("div", "ag-erro");
    e.setAttribute("role", "alert");
    erros[chave] = e;
    caixa.append(e);
    desenhar();
    return caixa;
  }

  function blocoRotulos() {
    const caixa = $("div");
    if (!est.pastas.length) return caixa;
    caixa.append($("p", "ag-dica cfg-dica", "Nome de cada grupo do menu (vazio usa o nome da pasta):"));
    for (const p of est.pastas) {
      const i = entrada((cur.rotulos && cur.rotulos[p.nome]) || "", p.nome, (v) => {
        cur.rotulos = cur.rotulos || {};
        if (v.trim() === "") delete cur.rotulos[p.nome]; else cur.rotulos[p.nome] = v;
        if (!Object.keys(cur.rotulos).length) delete cur.rotulos;
        erroEm("rotulos", M.validarCampo("rotulo", v, est.limites));
      });
      caixa.append(campo(p.nome, i));
    }
    const e = $("div", "ag-erro");
    e.setAttribute("role", "alert");
    erros.rotulos = e;
    caixa.append(e);
    return caixa;
  }

  // ---------- montagem do diálogo ----------

  function aviso(tipo, texto, botoes) {
    avisoEl.textContent = "";
    avisoEl.hidden = !texto;
    if (!texto) return;
    avisoEl.className = "ag-faixa cfg-aviso " + (tipo || "");
    avisoEl.append($("span", null, texto));
    for (const [rotulo, fn] of botoes || []) {
      const b = $("button", "ag-btn", rotulo);
      b.type = "button";
      b.addEventListener("click", fn);
      avisoEl.append(b);
    }
  }

  function secao(titulo) {
    const s = $("section", "cfg-secao");
    s.append($("h3", null, titulo));
    return s;
  }

  function desenhar() {
    const raiz = aberto.raiz;
    raiz.textContent = "";
    erros = {};
    raiz.append($("h2", null, "Configurar o site"));
    avisoEl = $("div", "ag-faixa cfg-aviso");
    avisoEl.hidden = true;
    avisoEl.setAttribute("role", "status");
    raiz.append(avisoEl);

    const ident = secao("Identidade");
    ident.append(campoTexto("titulo", "Título"), campoTexto("etiqueta", "Etiqueta (texto pequeno acima do título)"),
      campoTexto("subtitulo", "Subtítulo"), campoTexto("titulo_aba", "Título da aba do navegador"));
    const aparencia = secao("Aparência");
    aparencia.append(blocoAparencia());
    const textos = secao("Textos da interface");
    for (const [k, r] of ROTULOS_TEXTO) textos.append(campoTextoUi(k, r));
    textos.append(blocoRodape());
    const pastas = secao("Pastas");
    pastas.append(
      listaDeNomes("ignorar", "Pastas ignoradas", true, "Já ficam de fora sempre: " + est.padroes.ignoradas_sempre.join(", ") + ".", false),
      blocoRotulos(),
      listaDeNomes("home_prioridade", "Ordem dos arquivos soltos no Home", false, "Nomes sem .md; os primeiros da lista aparecem primeiro.", true));
    const leitura = secao("Só no config.json");
    leitura.append($("p", "ag-dica cfg-dica", "Estas opções definem o que o servidor lê e serve (ou exigem reiniciar o start): edite o arquivo e feche e abra o start de novo."));
    const dl = $("dl", "cfg-leitura");
    const sl = est.somente_leitura;
    for (const [k, v] of [["raiz", sl.raiz], ["prefixo_url", sl.prefixo_url], ["porta", sl.porta], ["arquivo", sl.arquivo]]) {
      dl.append($("dt", null, k), $("dd", null, String(v)));
    }
    leitura.append(dl);
    raiz.append(ident, aparencia, textos, pastas, leitura);

    const acoes = $("div", "ag-acoes cfg-acoes");
    desfazerEl = $("button", "ag-btn", "Desfazer");
    desfazerEl.type = "button";
    desfazerEl.disabled = !est.historico;
    desfazerEl.title = est.historico ? "Voltar à versão anterior do config.json" : "Ainda não há versão anterior";
    desfazerEl.addEventListener("click", desfazer);
    padroesEl = $("button", "ag-btn", "Restaurar padrões");
    padroesEl.type = "button";
    padroesEl.addEventListener("click", restaurarPadroes);
    const fechar = $("button", "ag-btn", "Fechar");
    fechar.type = "button";
    fechar.addEventListener("click", () => aberto.fechar());
    salvarEl = $("button", "ag-btn pri", "Salvar");
    salvarEl.type = "button";
    salvarEl.addEventListener("click", salvar);
    const espaco = $("span", "cfg-espaco");
    acoes.append(desfazerEl, padroesEl, espaco, fechar, salvarEl);
    raiz.append(acoes);

    if (!est.legivel) {
      const p = est.problema || {};
      aviso("erro", `O config.json está com JSON inválido (linha ${p.linha}, coluna ${p.coluna}: ${p.mensagem}). Corrija o arquivo e abra o painel de novo. Salvar fica desligado; Desfazer ainda funciona.`);
      salvarEl.disabled = true;
      padroesEl.disabled = true;
    }
  }

  // ---------- ações ----------

  function recebe(r) {   // estado novo do servidor: refaz a tela a partir dele
    est = r;
    orig = copia(r.valores);
    cur = copia(r.valores);
    desenhar();
  }

  function aplicarNaPagina(r, envio) {
    aplicarConfig(r.site);   // título, rótulos, rodapé (app.js)
    if (envio && envio.tema && Object.prototype.hasOwnProperty.call(envio.tema, "modo")) {
      try { storage().removeItem("ag-theme"); } catch (e) { /* sem armazenamento */ }   // senão a escolha pessoal anulava a mudança
    }
    AGTema.aplicar(document.documentElement, { paleta: r.site.tema.paleta, modo: r.site.tema.modo, pessoal: AGTema.lerPessoal(storage()), sistemaEscuro: sistemaEscuro(), paletas: r.paletas.map((p) => p.nome) });
    repintar();
    aberto.previaAntes = lerPrevia();
  }

  function mostrarErro(r) {
    if (r.codigo === "validacao" || r.codigo === "somente_leitura") {
      if (r.campo && erros[r.campo]) { erroEm(r.campo, r.erro); erros[r.campo].scrollIntoView && erros[r.campo].scrollIntoView({ block: "center" }); }
      else if (r.campo && r.campo.indexOf(".") > 0 && erros[r.campo.split(".")[0]]) erroEm(r.campo.split(".")[0], r.erro);
      aviso("erro", "Corrija o campo indicado." + (r.campo && !erros[r.campo] ? " (" + r.erro + ")" : ""));
    } else if (r.codigo === "conflito") {
      aviso("erro", "O config.json mudou por fora desde que o painel foi aberto.", [
        ["Recarregar valores (perde o que você mudou aqui)", recarregar],
        ["Salvar mesmo assim", () => enviar(M.montarEnvio(orig, cur), r.versao)],
      ]);
    } else if (r.codigo === "config_ilegivel") {
      aviso("erro", `O config.json está com JSON inválido (linha ${r.linha}, coluna ${r.coluna}). Corrija o arquivo e abra o painel de novo.`);
      salvarEl.disabled = true;
    } else {
      aviso("erro", r.erro || "Não foi possível concluir.");
    }
  }

  async function recarregar() {
    const r = await chamar(() => AGWrite.config());
    if (r.status !== 200) { mostrarErro(r); return; }
    recebe(r);
    aplicarNaPagina(r, null);   // a página passa a mostrar o que está no arquivo
    aviso("ok", "Valores recarregados do arquivo.");
  }

  async function chamar(fn) {
    try { return await fn(); } catch (e) { return { status: 0, codigo: "rede", erro: "Sem conexão com o servidor. O painel fecha quando a escrita para." }; }
  }

  async function enviar(envio, base) {
    if (!Object.keys(envio).length) { aviso("ok", "Nada mudou."); return; }
    salvarEl.disabled = true;
    const r = await chamar(() => AGWrite.configSalvar(envio, base));
    salvarEl.disabled = !est.legivel;
    if (r.status !== 200) { mostrarErro(r); return; }
    recebe(r);
    aplicarNaPagina(r, envio);
    aviso("ok", "Salvo.");
  }

  function salvar() {
    let problema = false;
    for (const [k, v] of [["titulo", cur.titulo], ["subtitulo", cur.subtitulo], ["etiqueta", cur.etiqueta], ["titulo_aba", cur.titulo_aba]]) {
      const m = M.validarCampo(k, v || "", est.limites);
      erroEm(k, m);
      problema = problema || !!m;
    }
    if (problema) { aviso("erro", "Corrija o campo indicado."); return; }
    aviso("", "");
    enviar(M.montarEnvio(orig, cur), est.versao);
  }

  async function desfazer() {
    desfazerEl.disabled = true;
    const r = await chamar(() => AGWrite.configDesfazer());
    if (r.status !== 200) { desfazerEl.disabled = false; mostrarErro(r); return; }
    recebe(r);
    aplicarNaPagina(r, { tema: { modo: true } });
    aviso("ok", "Voltou à versão anterior.");
  }

  async function restaurarPadroes() {
    if (padroesEl.dataset.confirma !== "1") {   // primeiro clique pede confirmação, o segundo faz
      padroesEl.dataset.confirma = "1";
      padroesEl.textContent = "Confirmar: voltar tudo ao padrão";
      setTimeout(() => { if (padroesEl && padroesEl.isConnected) { padroesEl.dataset.confirma = ""; padroesEl.textContent = "Restaurar padrões"; } }, 5000);
      return;
    }
    const chaves = ["titulo", "subtitulo", "etiqueta", "titulo_aba", "textos", "tema", "ignorar", "rotulos", "home_prioridade"];
    await enviar(M.envioPadroes(chaves.filter((k) => est.valores[k] !== undefined)), est.versao);
  }

  // ---------- abrir ----------

  async function abrir() {
    if (!escrita || aberto || document.querySelector(".ag-fundo")) return;
    const r = await chamar(() => AGWrite.config());
    const raiz = AGEditor.dialogo("ag-config", "Configurar o site");
    aberto = { raiz, previaAntes: lerPrevia(), fechar: null };
    // Esc, clique no fundo e o botão Fechar passam todos por aqui: a prévia não salva é desfeita e o estado limpo
    aberto.fechar = AGEditor.abrirDialogo(raiz, () => { restaurarPrevia(); aberto = null; });
    if (r.status !== 200) {
      const fechar = $("button", "ag-btn", "Fechar");
      fechar.type = "button";
      fechar.addEventListener("click", () => aberto.fechar());
      raiz.append($("h2", null, "Configurar o site"), $("p", "ag-erro", r.erro || "Não foi possível abrir as configurações."), fechar);
      return;
    }
    recebe(r);
  }

  if (btn) btn.addEventListener("click", abrir);
  return { setEscrita, abrir };
})();
