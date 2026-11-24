// Deriva nós e ligações do grafo a partir de AG_GRAPH.docs. Funções puras: rodam no navegador e no Node.
//
// mode "tags":   documento -> suas tags; cada tag aninhada -> tag pai (desenha a árvore de pastas).
// mode "direct": documento -> documento, com peso = número de tags curadas/de texto em comum.
//                Tags de pasta ficam de fora: ligariam todos os documentos de uma pasta.

const AGModel = (function () {
  const groupOf = (file) => (file.includes("/") ? file.split("/")[0] : "home");

  function visible(d, auto) {
    const t = d.tags;
    return [...new Set(auto ? [...t.curated, ...t.folder, ...t.text] : t.curated)];
  }

  function ancestors(tag) {
    const p = tag.split("/");
    return p.slice(0, -1).map((_, i) => p.slice(0, i + 1).join("/"));
  }

  function docNode(d, auto) {
    return { id: d.id, type: "doc", label: d.title, file: d.file, group: groupOf(d.file), tags: visible(d, auto) };
  }

  function viaTags(list, auto) {
    const nodes = new Map();
    const links = [];
    const seen = new Set();
    const docsOf = new Map(); // tag -> Set de ids, contando as tags-pai
    const link = (a, b) => {
      const k = a + "|" + b;
      if (!seen.has(k)) { seen.add(k); links.push({ source: a, target: b, w: 1 }); }
    };
    const tagNode = (t) => {
      const id = "tag:" + t;
      if (!nodes.has(id)) nodes.set(id, { id, type: "tag", label: "#" + t, tag: t, n: 0 });
      return id;
    };

    list.forEach((d) => {
      nodes.set(d.id, docNode(d, auto));
      const tags = visible(d, auto);
      // O documento liga só à tag mais funda de cada cadeia; as tags-pai ligam entre si.
      const leaves = tags.filter((t) => !tags.some((u) => u !== t && u.startsWith(t + "/")));
      leaves.forEach((t) => {
        link(d.id, tagNode(t));
        let child = t;
        [...ancestors(t)].reverse().forEach((a) => {
          link(tagNode(child), tagNode(a));
          child = a;
        });
        [t, ...ancestors(t)].forEach((x) => {
          if (!docsOf.has(x)) docsOf.set(x, new Set());
          docsOf.get(x).add(d.id);
        });
      });
    });

    nodes.forEach((n) => { if (n.type === "tag") n.n = docsOf.get(n.tag).size; });
    return finish(nodes, links);
  }

  function direct(list, auto) {
    const nodes = new Map();
    const sets = list.map((d) => {
      nodes.set(d.id, docNode(d, auto));
      const s = new Set();
      [...d.tags.curated, ...(auto ? d.tags.text : [])].forEach((t) => {
        s.add(t);
        ancestors(t).forEach((a) => s.add(a));
      });
      return s;
    });
    const links = [];
    for (let i = 0; i < list.length; i++) {
      for (let j = i + 1; j < list.length; j++) {
        let w = 0;
        sets[i].forEach((t) => { if (sets[j].has(t)) w++; });
        if (w > 0) links.push({ source: list[i].id, target: list[j].id, w });
      }
    }
    return finish(nodes, links);
  }

  function finish(nodes, links) {
    const deg = new Map();
    links.forEach((l) => {
      deg.set(l.source, (deg.get(l.source) || 0) + 1);
      deg.set(l.target, (deg.get(l.target) || 0) + 1);
    });
    const arr = [...nodes.values()];
    arr.forEach((n) => { n.deg = deg.get(n.id) || 0; });
    return { nodes: arr, links };
  }

  // opts: { mode: "tags"|"direct", auto: bool, only: Set de ids de documentos | null }
  function build(docs, opts) {
    const o = opts || {};
    const list = o.only ? docs.filter((d) => o.only.has(d.id)) : docs;
    const auto = o.auto !== false;
    return o.mode === "direct" ? direct(list, auto) : viaTags(list, auto);
  }

  return { build, groupOf };
})();

if (typeof module !== "undefined") module.exports = AGModel;
