const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const W = require("../site/js/write.js");
const { markdownToHtml } = require("../site/js/markdown.js");

// Os mesmos casos que tests/test_agwrite.py usa para o agwrite.py: prévia e arquivo criado não podem divergir.
const CASOS = JSON.parse(fs.readFileSync(path.join(__dirname, "casos_nota.json"), "utf8"));

test("slugTitulo: casos compartilhados com o Python", () => {
  for (const [entrada, esperado] of CASOS.slug) assert.equal(W.slugTitulo(entrada), esperado, entrada);
});

test("montarNota: casos compartilhados com o Python (com e sem tags, com e sem '# ' no corpo)", () => {
  for (const c of CASOS.nota) assert.equal(W.montarNota(c.titulo, c.tags, c.corpo, c.status), c.esperado, JSON.stringify(c));
});

test("frontmatter: só existe com tags, sem repetição", () => {
  assert.equal(W.frontmatter([]), "");
  assert.equal(W.frontmatter(["", "!!!"]), "");
  assert.equal(W.frontmatter(["A B", "a-b", "C"]), "---\ntags: [a_b, c]\n---\n");
  assert.equal(W.frontmatter([], "Fazendo"), "---\nstatus: Fazendo\n---\n");
  assert.equal(W.frontmatter(["x"], "Em  revisão"), "---\ntags: [x]\nstatus: Em revisão\n---\n");
  assert.equal(W.frontmatter(["x"], "  "), "---\ntags: [x]\n---\n");
});

const ARQ = "---\ntags: [a]\n---\n# T\n\n- [ ] um\n- [x] dois\n- [X] tres\ntexto\n";

test("alternarCaixa: marca e desmarca só a linha certa (frontmatter desloca o índice)", () => {
  const linhas = ARQ.split("\n");
  const um = linhas.indexOf("- [ ] um");
  assert.equal(um, 5);
  assert.equal(W.alternarCaixa(ARQ, um), ARQ.replace("- [ ] um", "- [x] um"));
  assert.equal(W.alternarCaixa(ARQ, um + 1), ARQ.replace("- [x] dois", "- [ ] dois"));
  assert.equal(W.alternarCaixa(ARQ, um + 2), ARQ.replace("- [X] tres", "- [ ] tres"));
  assert.equal(W.alternarCaixa(W.alternarCaixa(ARQ, um), um), ARQ, "duas vezes volta ao original");
});

test("alternarCaixa: linha que deixou de ser checklist devolve null e não mexe em nada", () => {
  for (const n of [0, 1, 2, 3, 4, 8, 99, -1]) assert.equal(W.alternarCaixa(ARQ, n), null, String(n));
  assert.equal(W.alternarCaixa("- [ ]sem espaço\n", 0), null);
  assert.equal(W.alternarCaixa("- [ ] ok\n", 0), "- [x] ok\n");
});

test("alternarCaixa: item recuado e final de linha CRLF", () => {
  assert.equal(W.alternarCaixa("  - [ ] filho\n", 0), "  - [x] filho\n");
  assert.equal(W.alternarCaixa("- [ ] a\r\n- [ ] b\r\n", 1), "- [ ] a\r\n- [x] b\r\n");
});

test("alternarCaixa e markdownToHtml concordam: o data-linha de cada caixa aponta para a linha dela", () => {
  const html = markdownToHtml(ARQ);
  const linhas = [...html.matchAll(/data-linha="(\d+)"/g)].map((m) => Number(m[1]));
  assert.deepEqual(linhas, [5, 6, 7]);
  for (const n of linhas) assert.notEqual(W.alternarCaixa(ARQ, n), null);
});

test("filtrarPaleta: título e caminho, sem acento nem caixa, todas as palavras", () => {
  const itens = [
    { titulo: "Nova nota", caminho: "" },
    { titulo: "Reunião de Sexta", caminho: "99-etc/reuniao-de-sexta.md" },
    { titulo: "Modelo de Negócio", caminho: "01-Visao-e-Negocio/modelo-de-negocio.md" },
    { titulo: "Custos", caminho: "06-Financeiro/modelo-de-custos.md" },
  ];
  const t = (q) => W.filtrarPaleta(itens, q).map((i) => i.titulo);
  assert.deepEqual(t(""), itens.map((i) => i.titulo));
  assert.deepEqual(t("reuniao"), ["Reunião de Sexta"]);
  assert.deepEqual(t("NEGOCIO"), ["Modelo de Negócio"]);
  assert.deepEqual(t("financeiro"), ["Custos"], "acha pelo caminho");
  assert.deepEqual(t("modelo custos"), ["Custos"], "todas as palavras, em qualquer ordem");
  assert.deepEqual(t("modelo"), ["Modelo de Negócio", "Custos"], "mantém a ordem recebida");
  assert.deepEqual(t("zzz"), []);
});
