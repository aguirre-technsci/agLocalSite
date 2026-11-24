// Busca por tags e texto, no estilo do Obsidian. Funções puras: rodam no navegador e no Node.
//
// Operadores: tag:x  path:x  file:x  content:x  "frase"  -termo  OR  ( )
// Termos soltos seguem o modo: any (qualquer tag), all (todas), exact (só estas tags curadas), text (trecho).
// Espaço entre operadores vale E; OR é mais fraco que o E. Tudo ignora acento e caixa.

const AGSearch = (function () {
  const OPS = ["tag", "path", "file", "content"];

  function norm(s) {
    return String(s).normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase();
  }

  // Igual ao normalize_tag do graphdata.py.
  function normTag(s) {
    return norm(s)
      .trim()
      .replace(/^#+/, "")
      .replace(/[\s-]+/g, "_")
      .replace(/[^a-z0-9_/]/g, "")
      .replace(/_+/g, "_")
      .replace(/\/+/g, "/")
      .replace(/_?\/_?/g, "/")
      .replace(/^[_/]+|[_/]+$/g, "");
  }

  function tokenize(q) {
    const toks = [];
    const n = q.length;
    let i = 0;
    while (i < n) {
      const c = q[i];
      if (/\s/.test(c)) { i++; continue; }
      if (c === "(" || c === ")") { toks.push({ t: c }); i++; continue; }
      if (c === "-" && q[i + 1] === "(") { toks.push({ t: "NOT" }); i++; continue; }
      let neg = false;
      if (c === "-" && i + 1 < n && !/[\s)]/.test(q[i + 1])) { neg = true; i++; }
      let op = null;
      const m = /^([a-z]+):/.exec(q.slice(i, i + 9));
      if (m && OPS.includes(m[1])) { op = m[1]; i += m[0].length; }
      let val;
      let quoted = false;
      if (q[i] === '"') {
        const end = q.indexOf('"', i + 1);
        if (end < 0) return { error: "aspas abertas" };
        val = q.slice(i + 1, end);
        quoted = true;
        i = end + 1;
      } else {
        let j = i;
        while (j < n && !/[\s()"]/.test(q[j])) j++;
        val = q.slice(i, j);
        i = j;
      }
      if (!op && !neg && !quoted && val === "OR") { toks.push({ t: "OR" }); continue; }
      if (val === "") continue; // operador ainda sem valor (a pessoa está digitando)
      toks.push({ t: "term", op, val, neg, quoted });
    }
    return { toks };
  }

  // Lança Error com a mensagem para o usuário quando a consulta está incompleta.
  function parse(toks) {
    let p = 0;
    const peek = () => toks[p];
    const startsOperand = (t) => !!t && (t.t === "term" || t.t === "(" || t.t === "NOT");

    function parseOr() {
      const xs = [parseAnd()];
      while (peek() && peek().t === "OR") {
        p++;
        xs.push(parseAnd());
      }
      return xs.length === 1 ? xs[0] : { t: "or", xs };
    }
    function parseAnd() {
      const xs = [];
      while (startsOperand(peek())) xs.push(parseUnary());
      if (!xs.length) throw new Error("consulta incompleta");
      return xs.length === 1 ? xs[0] : { t: "and", xs };
    }
    function parseUnary() {
      if (peek().t === "NOT") {
        p++;
        if (!peek() || peek().t !== "(") throw new Error("consulta incompleta");
        return { t: "not", x: parsePrimary() };
      }
      return parsePrimary();
    }
    function parsePrimary() {
      const t = peek();
      p++;
      if (t.t === "term") {
        const node = { t: "term", op: t.op, val: t.val, quoted: t.quoted };
        return t.neg ? { t: "not", x: node } : node;
      }
      const e = parseOr(); // t.t === "("
      if (!peek() || peek().t !== ")") throw new Error("parêntese aberto");
      p++;
      return e;
    }

    const ast = parseOr();
    if (p < toks.length) throw new Error(toks[p].t === ")" ? "parêntese fechado sem abrir" : "consulta incompleta");
    return ast;
  }

  function visibleTags(doc, auto) {
    const t = doc.tags;
    return auto ? [...t.curated, ...t.folder, ...t.text] : t.curated.slice();
  }

  // A tag q casa com a tag x quando x é q ou uma filha de q (roll-up, como no Obsidian).
  const hasTag = (tags, q) => tags.some((x) => x === q || x.startsWith(q + "/"));

  function contextOf(doc, auto, getText) {
    const tags = visibleTags(doc, auto);
    const body = norm(getText(doc.id) || "");
    const tagWords = tags.map((t) => t.replace(/[_/]/g, " ")).join(" ");
    return {
      tags,
      curated: doc.tags.curated,
      path: norm(doc.file),
      file: norm(doc.file.split("/").pop() + " " + doc.title),
      body,
      hay: norm(doc.title) + " " + tagWords + " " + body,
    };
  }

  // opts: { mode: "any"|"all"|"exact"|"text", auto: bool, getText: id => corpo sem frontmatter }
  // Devolve { all, ids, matched: {id: [tags]}, terms: [tags buscadas] } ou { error }.
  function search(query, docs, opts) {
    const mode = (opts && opts.mode) || "any";
    const auto = !opts || opts.auto !== false;
    const getText = (opts && opts.getText) || (() => "");
    const everything = { all: true, ids: docs.map((d) => d.id), matched: {}, terms: [] };

    const q = (query || "").trim();
    if (!q) return everything;
    const tk = tokenize(q);
    if (tk.error) return { error: tk.error };
    if (!tk.toks.length) return everything;
    let ast;
    try {
      ast = parse(tk.toks);
    } catch (e) {
      return { error: e.message };
    }

    const evalTerm = (t, c) => {
      const op = t.op || (t.quoted ? "phrase" : mode === "text" ? "text" : "tag");
      switch (op) {
        case "tag": { const v = normTag(t.val); return v ? hasTag(c.tags, v) : true; }
        case "path": return c.path.includes(norm(t.val));
        case "file": return c.file.includes(norm(t.val));
        case "content": return c.body.includes(norm(t.val));
        default: return c.hay.includes(norm(t.val)); // frase ou modo texto
      }
    };
    const evalNode = (n, c) => {
      if (n.t === "and") return n.xs.every((x) => evalNode(x, c));
      if (n.t === "or") return n.xs.some((x) => evalNode(x, c));
      if (n.t === "not") return !evalNode(n.x, c);
      return evalTerm(n, c);
    };

    // Os botões de modo só decidem como os termos soltos do nível principal se juntam.
    const top = ast.t === "and" ? ast.xs : [ast];
    const isBare = (x) => x.t === "term" && !x.op && !x.quoted;
    const bare = top.filter(isBare);
    const rest = top.filter((x) => !isBare(x));
    const wanted = new Set(bare.map((b) => normTag(b.val)).filter(Boolean));

    const combineBare = (c) => {
      if (!bare.length) return true;
      if (mode === "exact") {
        if (!wanted.size) return true;
        const have = new Set(c.curated);
        return have.size === wanted.size && [...wanted].every((x) => have.has(x));
      }
      const r = bare.map((b) => evalTerm(b, c));
      return mode === "any" ? r.some(Boolean) : r.every(Boolean);
    };

    // Tags procuradas de forma positiva (fora de exclusões), para destacar e ordenar.
    const terms = [];
    (function collect(n) {
      if (n.t === "not") return;
      if (n.t === "and" || n.t === "or") return n.xs.forEach(collect);
      if (n.op === "tag" || (isBare(n) && mode !== "text")) {
        const v = normTag(n.val);
        if (v && !terms.includes(v)) terms.push(v);
      }
    })(ast);

    const ids = [];
    const matched = {};
    docs.forEach((d) => {
      const c = contextOf(d, auto, getText);
      if (!combineBare(c) || !rest.every((x) => evalNode(x, c))) return;
      ids.push(d.id);
      const pool = mode === "exact" ? c.curated : c.tags;
      matched[d.id] = pool.filter((t) => terms.some((x) => t === x || t.startsWith(x + "/")));
    });
    if (terms.length) ids.sort((a, b) => matched[b].length - matched[a].length); // estável: mantém a ordem do menu nos empates
    return { all: false, ids, matched, terms };
  }

  // Quantos documentos têm cada tag (contando as tags-pai das aninhadas).
  function tagIndex(docs, auto) {
    const counts = new Map();
    docs.forEach((d) => {
      const seen = new Set();
      visibleTags(d, auto).forEach((t) => {
        const parts = t.split("/");
        for (let i = 1; i <= parts.length; i++) seen.add(parts.slice(0, i).join("/"));
      });
      seen.forEach((t) => counts.set(t, (counts.get(t) || 0) + 1));
    });
    return counts;
  }

  function suggest(prefix, docs, auto, limit) {
    const p = normTag(prefix);
    const out = [];
    tagIndex(docs, auto).forEach((count, tag) => {
      if (!p || tag.includes(p)) out.push({ tag, count });
    });
    out.sort((a, b) =>
      (b.tag.startsWith(p) - a.tag.startsWith(p)) || (b.count - a.count) || a.tag.localeCompare(b.tag));
    return out.slice(0, limit || 8);
  }

  // Palavras da consulta que dá para marcar no texto de um documento (fora de negações, path: e file:).
  // Tag vira o último nível, com "_" como espaço: tag:dados/ons -> "ons"; dados_abertos -> "dados abertos".
  function highlightTerms(query, mode) {
    const tk = tokenize((query || "").trim());
    if (tk.error || !tk.toks.length) return [];
    let ast;
    try { ast = parse(tk.toks); } catch (e) { return []; }
    const out = [];
    (function walk(n) {
      if (n.t === "not") return;
      if (n.t === "and" || n.t === "or") return n.xs.forEach(walk);
      const op = n.op || (n.quoted ? "phrase" : mode === "text" ? "text" : "tag");
      if (op === "path" || op === "file") return;
      const v = (op === "tag" ? normTag(n.val).split("/").pop().replace(/_/g, " ") : n.val).trim();
      if (v && !out.includes(v)) out.push(v);
    })(ast);
    return out;
  }

  // Trechos [início, fim) de `text` que casam com algum termo. Ignora acento e caixa; entre palavras
  // do termo vale espaço, "_" ou "-"; o trecho começa em início de palavra (tag "ons" não marca "conselho").
  function findRanges(text, terms) {
    const pats = terms
      .map((t) => norm(t).split(/[\s_-]+/).filter(Boolean).map((w) => w.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")).join("[\\s_-]+"))
      .filter(Boolean)
      .sort((a, b) => b.length - a.length);
    if (!pats.length) return [];
    let flat = ""; // mesmo tamanho de `text`, para os índices valerem no original
    for (let i = 0; i < text.length; i++) flat += text[i].normalize("NFD")[0].toLowerCase()[0];
    const re = new RegExp("(?<![\\p{L}\\p{N}])(?:" + pats.join("|") + ")", "gu");
    const out = [];
    let m;
    while ((m = re.exec(flat))) out.push([m.index, m.index + m[0].length]);
    return out;
  }

  return { norm, normTag, tokenize, parse, search, tagIndex, suggest, visibleTags, highlightTerms, findRanges };
})();

if (typeof module !== "undefined") module.exports = AGSearch;
