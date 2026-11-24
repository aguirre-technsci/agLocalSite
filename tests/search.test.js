const test = require("node:test");
const assert = require("node:assert/strict");
const S = require("../site/js/search.js");

const mk = (id, file, curated, folder, text, title) => ({ id, title: title || id, file, tags: { curated, folder, text } });
const DOCS = [
  mk("d1", "02-a/Alfa/Alfa-Optimizer/README.md", ["algoritmo", "3d", "dados_abertos"], ["produtos", "produtos/alfa"], ["pressao"], "Otimizador"),
  mk("d2", "02-a/Alfa/Alfa-Dashboard/README.md", ["algoritmo", "3d"], ["produtos", "produtos/alfa"], [], "Painel"),
  mk("d3", "04-b/fontes.md", ["algoritmo", "3d", "dados_abertos", "ons"], ["pesquisa"], [], "Fontes"),
  mk("d4", "04-b/origem.md", ["dados_abertos"], ["pesquisa"], ["gasoduto"], "Origem"),
  mk("d5", "06-financeiro/custos.md", [], ["financeiro"], [], "Custos"),
  mk("d6", "04-b/dados.md", ["dados/ons", "dados/anp"], ["pesquisa"], [], "Dados"),
];
const TEXTS = {
  d1: "Algoritmo genético com pressão de gasoduto.",
  d2: "Renderização em três dimensões do blend de hidrogênio.",
  d3: "Fontes ONS e ANP.",
  d4: "Origem dos dados abertos do gasoduto Termoaçu.",
  d5: "Custos fixos.",
  d6: "Séries do ONS e da ANP.",
};
const getText = (id) => TEXTS[id];
const run = (q, mode = "any", extra = {}) => S.search(q, DOCS, { mode, getText, ...extra });
const ids = (q, mode, extra) => run(q, mode, extra).ids.slice().sort();

test("normTag: mesma tabela do graphdata.py", () => {
  const casos = { "Dados Abertos": "dados_abertos", "  #Algoritmo ": "algoritmo", "Otimização-Térmica": "otimizacao_termica",
    "3D": "3d", "dados/ONS": "dados/ons", "a__b": "a_b", "/a//b/": "a/b", "a_/_b": "a/b", "!!!": "" };
  for (const [entrada, esperado] of Object.entries(casos)) assert.equal(S.normTag(entrada), esperado, entrada);
});

test("tokenize: aspas, negação, operadores, OR, parênteses", () => {
  const { toks } = S.tokenize('tag:3d -tag:x "duas palavras" OR (a) -(b)');
  assert.deepEqual(toks.map((t) => t.t), ["term", "term", "term", "OR", "(", "term", ")", "NOT", "(", "term", ")"]);
  assert.equal(toks[0].op, "tag");
  assert.equal(toks[1].neg, true);
  assert.equal(toks[2].quoted, true);
  assert.equal(toks[2].val, "duas palavras");
});

test("tokenize: aspas abertas dão erro; operador sem valor é ignorado", () => {
  assert.equal(S.tokenize('"abc').error, "aspas abertas");
  assert.deepEqual(S.tokenize("tag:").toks, []);
  assert.equal(S.tokenize("unknown:x").toks[0].op, null); // operador desconhecido vira termo solto
});

test("consultas incompletas ou inválidas devolvem erro", () => {
  for (const q of ["(a", "a)", "a OR", "OR a", "()", "-(", '"a']) assert.ok(run(q).error, q);
  assert.equal(run("(a").error, "parêntese aberto");
  assert.equal(run("a)").error, "parêntese fechado sem abrir");
});

test("consulta vazia devolve todos", () => {
  const r = run("  ");
  assert.equal(r.all, true);
  assert.equal(r.ids.length, DOCS.length);
  assert.equal(run("tag:").all, true);
});

test("modo any: qualquer uma das tags", () => {
  assert.deepEqual(ids("algoritmo 3d dados_abertos", "any"), ["d1", "d2", "d3", "d4"]);
});

test("modo all: todas as tags", () => {
  assert.deepEqual(ids("algoritmo 3d dados_abertos", "all"), ["d1", "d3"]);
});

test("modo exact: exatamente essas tags curadas", () => {
  assert.deepEqual(ids("algoritmo 3d dados_abertos", "exact"), ["d1"]); // d3 tem uma a mais (ons)
  assert.deepEqual(ids("3d algoritmo", "exact"), ["d2"]);
  assert.deepEqual(ids("dados_abertos", "exact"), ["d4"]);
});

test("modo exact ignora tags automáticas e o botão Automáticas", () => {
  assert.deepEqual(ids("pesquisa", "exact"), []); // 'pesquisa' é tag de pasta, não curada
  assert.deepEqual(ids("algoritmo 3d dados_abertos", "exact", { auto: false }), ["d1"]);
});

test("modo text: trecho no título, tags e corpo, sem acento e sem caixa", () => {
  assert.deepEqual(ids("pressao", "text"), ["d1"]);       // corpo tem 'pressão'
  assert.deepEqual(ids("RENDERIZACAO", "text"), ["d2"]);
  assert.deepEqual(ids("painel", "text"), ["d2"]);        // título
  assert.deepEqual(ids("dados abertos", "text"), ["d1", "d3", "d4"]); // tag dados_abertos e corpo
  assert.deepEqual(ids("gasoduto termoacu", "text"), ["d4"]); // termos do texto: todos precisam aparecer
});

test("roll-up: tag pai encontra as filhas", () => {
  assert.deepEqual(ids("tag:dados"), ["d6"]);
  assert.deepEqual(ids("tag:dados/ons"), ["d6"]);
  assert.deepEqual(ids("tag:produtos"), ["d1", "d2"]);
  assert.deepEqual(ids("tag:produtos/alfa"), ["d1", "d2"]);
  assert.deepEqual(ids("tag:alfa"), []); // roll-up é para cima, não por sufixo
});

test("botão Automáticas desligado: só tags curadas", () => {
  assert.deepEqual(ids("tag:produtos", "any", { auto: false }), []);
  assert.deepEqual(ids("tag:gasoduto"), ["d4"]);
  assert.deepEqual(ids("tag:gasoduto", "any", { auto: false }), []);
});

test("exclusão com hífen", () => {
  assert.deepEqual(ids("tag:algoritmo -tag:dados_abertos"), ["d2"]);
  assert.deepEqual(ids("-tag:algoritmo"), ["d4", "d5", "d6"]);
  assert.deepEqual(ids("tag:algoritmo -(tag:ons OR tag:dados_abertos)"), ["d2"]);
});

test("OR e parênteses; E é mais forte que OR", () => {
  assert.deepEqual(ids("tag:financeiro OR tag:ons"), ["d3", "d5"]);
  assert.deepEqual(ids("tag:3d (tag:ons OR tag:financeiro)"), ["d3"]);
  assert.deepEqual(ids("tag:ons tag:3d OR tag:financeiro"), ["d3", "d5"]); // (ons E 3d) OR financeiro
});

test("path, file e content", () => {
  assert.deepEqual(ids("path:04-b"), ["d3", "d4", "d6"]);
  assert.deepEqual(ids("file:custos"), ["d5"]);
  assert.deepEqual(ids("file:otimizador"), ["d1"]); // título também conta em file:
  assert.deepEqual(ids("content:termoacu"), ["d4"]);
  assert.deepEqual(ids("content:otimizador"), []);  // título não é corpo
});

test("frase entre aspas", () => {
  assert.deepEqual(ids('"dados abertos do gasoduto"'), ["d4"]);
  assert.deepEqual(ids('"três dimensões"'), ["d2"]);
});

test("operador combina com termos soltos, que seguem o modo", () => {
  assert.deepEqual(ids("path:04-b algoritmo dados_abertos", "any"), ["d3", "d4"]);
  assert.deepEqual(ids("path:04-b algoritmo dados_abertos", "all"), ["d3"]);
});

test("matched lista as tags que casaram e ordena por mais casamentos", () => {
  const r = run("algoritmo 3d dados_abertos", "any");
  assert.deepEqual(r.matched.d1, ["algoritmo", "3d", "dados_abertos"]);
  assert.deepEqual(r.matched.d4, ["dados_abertos"]);
  assert.deepEqual(r.ids.slice(0, 2), ["d1", "d3"]); // 3 casamentos primeiro, na ordem do menu
  assert.equal(r.ids.at(-1), "d4");
  assert.deepEqual(r.terms, ["algoritmo", "3d", "dados_abertos"]);
});

test("tagIndex conta documentos, incluindo as tags-pai", () => {
  const idx = S.tagIndex(DOCS, true);
  assert.equal(idx.get("dados"), 1);
  assert.equal(idx.get("dados/ons"), 1);
  assert.equal(idx.get("produtos"), 2);
  assert.equal(idx.get("algoritmo"), 3);
  assert.equal(S.tagIndex(DOCS, false).has("produtos"), false);
});

test("suggest: começa-com primeiro, depois contagem; aceita acento e caixa", () => {
  const s = S.suggest("Dad", DOCS, true, 5).map((x) => x.tag);
  assert.equal(s[0], "dados_abertos"); // 3 documentos
  assert.ok(s.includes("dados"));
  assert.deepEqual(S.suggest("zzz", DOCS, true), []);
  assert.equal(S.suggest("", DOCS, true, 3).length, 3);
});

test("highlightTerms: tag vira palavra, frase e content ficam literais, negação/path/file saem", () => {
  assert.deepEqual(S.highlightTerms("dados_abertos"), ["dados abertos"]);
  assert.deepEqual(S.highlightTerms("tag:dados/ons"), ["ons"]);
  assert.deepEqual(S.highlightTerms('"blend de hidrogênio" content:zenodo'), ["blend de hidrogênio", "zenodo"]);
  assert.deepEqual(S.highlightTerms("tag:alfa -tag:publicacao path:04- file:custos"), ["alfa"]);
  assert.deepEqual(S.highlightTerms("algoritmo -(tag:a OR tag:b)"), ["algoritmo"]);
  assert.deepEqual(S.highlightTerms("pressão gás", "text"), ["pressão", "gás"]);
  assert.deepEqual(S.highlightTerms("algoritmo OR algoritmo"), ["algoritmo"]);
});

test("highlightTerms: vazio, incompleto e só-exclusão não marcam nada", () => {
  assert.deepEqual(S.highlightTerms(""), []);
  assert.deepEqual(S.highlightTerms("   "), []);
  assert.deepEqual(S.highlightTerms('"aspas abertas'), []);
  assert.deepEqual(S.highlightTerms("(tag:a"), []);
  assert.deepEqual(S.highlightTerms("-tag:financeiro"), []);
});

test("findRanges: ignora acento e caixa, índices valem no texto original", () => {
  const t = "A Pressão média; a PRESSAO final.";
  assert.deepEqual(S.findRanges(t, ["pressao"]).map(([a, b]) => t.slice(a, b)), ["Pressão", "PRESSAO"]);
  assert.deepEqual(S.findRanges("otimização", ["OTIMIZACAO"]), [[0, 10]]);
});

test("findRanges: espaço, _ e - equivalem entre palavras; começa em início de palavra", () => {
  const t = "dados abertos, dados_abertos e dados-abertos; conselho e ONS.";
  assert.equal(S.findRanges(t, ["dados abertos"]).length, 3);
  assert.deepEqual(S.findRanges(t, ["ons"]).map(([a, b]) => t.slice(a, b)), ["ONS"]); // não marca "conselho"
});

test("findRanges: escapa regex, prefere o termo mais longo, sem termos não marca", () => {
  assert.deepEqual(S.findRanges("custo (R$) 3.5", ["(r$)"]), [[6, 10]]);
  assert.deepEqual(S.findRanges("blend de hidrogênio verde", ["blend", "blend de hidrogenio"]), [[0, 19]]);
  assert.deepEqual(S.findRanges("texto", []), []);
  assert.deepEqual(S.findRanges("texto", ["   "]), []);
});
