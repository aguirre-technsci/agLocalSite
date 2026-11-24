// Regras do quadro Kanban: funções puras (rodam no navegador e no Node). A tela está em kanban-view.js.
//
// Dois tipos de cartão, lidos do texto dos documentos (AG_CONTENT, campo fallback):
//   nota  = documento com 'status:' no frontmatter; a coluna é o valor do status;
//   item  = cada '- [ ]' / '- [x]' de qualquer documento; '[ ]' cai em "A fazer" e '[x]' em "Feito".
// Colunas fixas: A fazer, Em progresso e Feito. A coluna Feito fica escondida e só aparece buscando (filtrarQuadro).

const AGKanban = (function () {
  const S = typeof AGSearch !== "undefined" ? AGSearch : require("./search.js");
  const W = typeof AGWrite !== "undefined" ? AGWrite : require("./write.js");
  const strip = typeof stripFrontmatter !== "undefined" ? stripFrontmatter : require("./markdown.js").stripFrontmatter;

  const A_FAZER = { chave: "a fazer", rotulo: "A fazer" };
  const EM_PROGRESSO = { chave: "em progresso", rotulo: "Em progresso" };
  const FEITO = { chave: "feito", rotulo: "Feito" };

  // 'A fazer', 'a-fazer' e 'À FAZER' são a mesma coluna.
  const chaveColuna = (s) => S.norm(s).replace(/[^a-z0-9]+/g, " ").trim();

  // Frontmatter cru (com as quebras de linha); "" se o texto não tem.
  const bloco = (texto) => texto.slice(0, texto.length - strip(texto).length);

  const LINHA_STATUS = /^status[ \t]*:[ \t]*(.*?)[ \t]*$/i;

  // Valor da primeira linha 'status:' do frontmatter, ou null. Um 'status:' no corpo não conta.
  function lerStatus(texto) {
    for (const l of bloco(texto).split(/\r?\n/)) {
      const m = LINHA_STATUS.exec(l);
      if (m) return m[1].replace(/^(["'])(.*)\1$/, "$2").trim() || null;
    }
    return null;
  }

  // Troca só a linha 'status:' do frontmatter. null se ela não existe.
  function alterarStatus(texto, valor) {
    const fm = bloco(texto);
    const linhas = fm.split("\n");
    const i = linhas.findIndex((l) => LINHA_STATUS.test(l.replace(/\r$/, "")));
    if (i < 0) return null;
    linhas[i] = "status: " + valor + (linhas[i].endsWith("\r") ? "\r" : "");
    return linhas.join("\n") + texto.slice(fm.length);
  }

  // Itens de checklist do documento, com o mesmo critério do markdown.js: as linhas dentro de blocos de três
  // crases não contam, e 'linha' é o índice (a partir de 0) no arquivo inteiro, frontmatter incluído.
  function itens(texto) {
    const corpo = strip(texto);
    const deslocamento = bloco(texto).split("\n").length - 1;
    const out = [];
    let emCodigo = false;
    corpo.replace(/\r\n/g, "\n").split("\n").forEach((l, i) => {
      if (/^```/.test(l)) { emCodigo = !emCodigo; return; }
      const m = !emCodigo && /^\s*-\s+\[( |x|X)\]\s+(.*)$/.exec(l);
      if (m) out.push({ linha: i + deslocamento, feito: m[1] !== " ", texto: m[2] });
    });
    return out;
  }

  // docs: documentos na ordem do menu ({ id, title, file, fallback }); tagsPorId: id -> tags curadas;
  // extras: rótulos de colunas que já apareceram na sessão e ficam mesmo vazias (quem esvazia a coluna
  // "Ideia" ainda precisa poder devolver um cartão a ela).
  function montarQuadro(docs, tagsPorId, extras) {
    const colunas = new Map();
    const coluna = (chave, rotulo, fixa) => {
      if (!colunas.has(chave)) colunas.set(chave, { chave, rotulo, fixa, cartoes: [] });
      return colunas.get(chave);
    };
    coluna(A_FAZER.chave, A_FAZER.rotulo, true);
    coluna(EM_PROGRESSO.chave, EM_PROGRESSO.rotulo, true);
    coluna(FEITO.chave, FEITO.rotulo, true);
    (extras || []).forEach((r) => { const k = chaveColuna(r); if (k) coluna(k, r, false); });

    docs.forEach((d) => {
      const status = lerStatus(d.fallback);
      const chave = status && chaveColuna(status);
      if (chave) {
        coluna(chave, status, false).cartoes.push({
          chave: "n:" + d.file, tipo: "nota", coluna: chave, id: d.id, titulo: d.title, arquivo: d.file,
          pasta: d.file.split("/").slice(0, -1).join("/"), tags: (tagsPorId && tagsPorId[d.id]) || [],
        });
      }
      itens(d.fallback).forEach((it) => {
        const destino = it.feito ? FEITO.chave : A_FAZER.chave;
        colunas.get(destino).cartoes.push({
          chave: `i:${d.file}:${it.linha}`, tipo: "item", coluna: destino, arquivo: d.file, docId: d.id,
          docTitulo: d.title, linha: it.linha, texto: it.texto, feito: it.feito,
        });
      });
    });

    const outras = [...colunas.values()].filter((c) => !c.fixa).sort((a, b) => (a.chave < b.chave ? -1 : a.chave > b.chave ? 1 : 0));
    return { colunas: [colunas.get(A_FAZER.chave), colunas.get(EM_PROGRESSO.chave), ...outras, colunas.get(FEITO.chave)] };
  }

  // O que a tela mostra. Sem consulta, a coluna Feito fica escondida (só se sabe quantos cartões há nela).
  // Com consulta, todas as colunas mostram só os cartões que combinam, e Feito aparece junto.
  // A consulta ignora acento e caixa; todas as palavras têm que aparecer no título, tags, pasta, texto ou coluna
  // do cartão (buscar "feito" mostra tudo o que está feito).
  function filtrarQuadro(quadro, consulta) {
    const palavras = S.norm(consulta || "").split(/\s+/).filter(Boolean);
    const busca = palavras.length > 0;
    const combina = (c) => {
      const alvo = S.norm((c.tipo === "nota" ? [c.titulo, c.pasta, c.arquivo, ...c.tags, c.coluna] : [c.texto, c.docTitulo, c.arquivo, c.coluna]).join(" "));
      return palavras.every((p) => alvo.includes(p));
    };
    const feitos = quadro.colunas.find((c) => c.chave === FEITO.chave).cartoes.length;
    const colunas = quadro.colunas
      .filter((c) => busca || c.chave !== FEITO.chave)
      .map((c) => (busca ? { ...c, cartoes: c.cartoes.filter(combina) } : c));
    return { colunas, busca, feitosOcultos: busca ? 0 : feitos };
  }

  // Nota vai para qualquer coluna; item só para A fazer ou Feito (o .md só guarda [ ] e [x]). Mesma coluna não é movimento.
  function destinoPermitido(cartao, chave) {
    return cartao.coluna !== chave && (cartao.tipo === "nota" || chave === A_FAZER.chave || chave === FEITO.chave);
  }

  // Texto novo do arquivo depois de mover o cartão, ou null se o arquivo mudou e o movimento deve ser cancelado.
  function moverCartao(cartao, coluna, texto) {
    if (cartao.tipo === "nota") return alterarStatus(texto, coluna.rotulo);
    const item = itens(texto).find((x) => x.linha === cartao.linha);
    if (!item || item.texto !== cartao.texto || item.feito === (coluna.chave === FEITO.chave)) return null;
    return W.alternarCaixa(texto, cartao.linha);
  }

  return { chaveColuna, lerStatus, alterarStatus, itens, montarQuadro, filtrarQuadro, destinoPermitido, moverCartao };
})();

if (typeof module !== "undefined") module.exports = AGKanban;
