const test = require("node:test");
const assert = require("node:assert/strict");
const M = require("../site/js/graph-model.js");

const mk = (id, file, curated, folder, text) => ({ id, title: id, file, tags: { curated, folder, text } });
const DOCS = [
  mk("a", "02-x/Alfa/A/README.md", ["algoritmo", "dados/ons"], ["x", "x/alfa", "x/alfa/a"], ["pressao"]),
  mk("b", "02-x/Alfa/B/README.md", ["algoritmo"], ["x", "x/alfa", "x/alfa/b"], ["pressao", "vazao"]),
  mk("c", "04-y/c.md", ["dados/anp"], ["y"], []),
  mk("d", "INICIO.md", [], [], []),
];
const ids = (arr) => arr.map((n) => n.id).sort();
const has = (g, s, t) => g.links.some((l) => l.source === s && l.target === t);

test("groupOf: pasta de topo, ou home para arquivo na raiz", () => {
  assert.equal(M.groupOf("02-x/a/b.md"), "02-x");
  assert.equal(M.groupOf("INICIO.md"), "home");
});

test("modo tags: documento liga só à tag mais funda de cada cadeia", () => {
  const g = M.build(DOCS, { mode: "tags" });
  assert.ok(has(g, "a", "tag:x/alfa/a"));
  assert.ok(!has(g, "a", "tag:x"));
  assert.ok(!has(g, "a", "tag:x/alfa"));
  assert.ok(has(g, "a", "tag:algoritmo"));
  assert.ok(has(g, "a", "tag:dados/ons"));
});

test("modo tags: tag aninhada liga à tag pai, formando a árvore", () => {
  const g = M.build(DOCS, { mode: "tags" });
  assert.ok(has(g, "tag:x/alfa/a", "tag:x/alfa"));
  assert.ok(has(g, "tag:x/alfa", "tag:x"));
  assert.ok(has(g, "tag:dados/ons", "tag:dados"));
  assert.ok(has(g, "tag:dados/anp", "tag:dados"));
});

test("modo tags: sem ligações duplicadas e sem nós de tag soltos", () => {
  const g = M.build(DOCS, { mode: "tags" });
  const keys = g.links.map((l) => l.source + "|" + l.target);
  assert.equal(new Set(keys).size, keys.length);
  g.nodes.filter((n) => n.type === "tag").forEach((n) => assert.ok(n.deg > 0, n.id));
});

test("modo tags: n de uma tag conta documentos, incluindo os das filhas", () => {
  const g = M.build(DOCS, { mode: "tags" });
  const n = (t) => g.nodes.find((x) => x.id === "tag:" + t).n;
  assert.equal(n("x/alfa"), 2);
  assert.equal(n("x"), 2);
  assert.equal(n("dados"), 2);
  assert.equal(n("algoritmo"), 2);
  assert.equal(n("x/alfa/a"), 1);
});

test("modo tags: documento sem tags continua como nó solto", () => {
  const g = M.build(DOCS, { mode: "tags" });
  const d = g.nodes.find((x) => x.id === "d");
  assert.equal(d.deg, 0);
  assert.equal(d.group, "home");
});

test("Automáticas desligado: só tags curadas", () => {
  const g = M.build(DOCS, { mode: "tags", auto: false });
  assert.deepEqual(ids(g.nodes.filter((n) => n.type === "tag")), ["tag:algoritmo", "tag:dados", "tag:dados/anp", "tag:dados/ons"]);
  assert.ok(!g.nodes.some((n) => n.id === "tag:pressao"));
});

test("only: mantém só os documentos pedidos e as tags deles", () => {
  const g = M.build(DOCS, { mode: "tags", only: new Set(["c"]) });
  assert.deepEqual(ids(g.nodes), ["c", "tag:dados", "tag:dados/anp", "tag:y"]);
});

test("modo direct: peso = tags em comum; pasta não conta", () => {
  const g = M.build(DOCS, { mode: "direct" });
  const ab = g.links.find((l) => l.source === "a" && l.target === "b");
  assert.equal(ab.w, 2); // algoritmo + pressao (as tags de pasta x e x/alfa ficam de fora)
  assert.equal(g.nodes.every((n) => n.type === "doc"), true);
});

test("modo direct: tag pai de curadas aninhadas liga documentos", () => {
  const g = M.build(DOCS, { mode: "direct" });
  const ac = g.links.find((l) => l.source === "a" && l.target === "c");
  assert.equal(ac.w, 1); // dados/ons e dados/anp compartilham o pai 'dados'
});

test("modo direct: sem tags em comum não há ligação; Automáticas desligado tira o peso do texto", () => {
  const g = M.build(DOCS, { mode: "direct" });
  assert.ok(!g.links.some((l) => l.source === "b" && l.target === "c"));
  assert.equal(M.build(DOCS, { mode: "direct", auto: false }).links.find((l) => l.source === "a" && l.target === "b").w, 1);
});

test("deg reflete o número de ligações", () => {
  const g = M.build(DOCS, { mode: "direct" });
  assert.equal(g.nodes.find((n) => n.id === "a").deg, 2);
  assert.equal(g.nodes.find((n) => n.id === "d").deg, 0);
});
