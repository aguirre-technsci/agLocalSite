// tema.js: paleta e modo inicial. Ordem do modo: escolha pessoal (localStorage) > tema.modo do projeto > claro.
const test = require("node:test");
const assert = require("node:assert/strict");
const AGTema = require("../site/js/tema.js");

const LISTA = ["padrao", "oceano", "floresta", "grafite", "ameixa"];

test("resolverModo: a escolha pessoal vence o projeto", () => {
  assert.equal(AGTema.resolverModo("dark", "claro", false), "dark");
  assert.equal(AGTema.resolverModo("light", "escuro", true), "light");
  assert.equal(AGTema.resolverModo("light", "sistema", true), "light");
});

test("resolverModo: sem escolha pessoal, vale o modo do projeto", () => {
  assert.equal(AGTema.resolverModo(null, "escuro", false), "dark");
  assert.equal(AGTema.resolverModo(null, "claro", true), "light");
  assert.equal(AGTema.resolverModo(null, "sistema", true), "dark");
  assert.equal(AGTema.resolverModo(null, "sistema", false), "light");
});

test("resolverModo: sem nada (ou com lixo) o padrão é claro", () => {
  assert.equal(AGTema.resolverModo(undefined, undefined, false), "light");
  assert.equal(AGTema.resolverModo("blue", "roxo", true), "light");
  assert.equal(AGTema.resolverModo(5, {}, true), "light");
});

test("paletaValida: só nomes da lista; o resto cai em padrao", () => {
  assert.equal(AGTema.paletaValida("oceano", LISTA), "oceano");
  assert.equal(AGTema.paletaValida("neon", LISTA), "padrao");
  assert.equal(AGTema.paletaValida("", LISTA), "padrao");
  assert.equal(AGTema.paletaValida(5, LISTA), "padrao");
  assert.equal(AGTema.paletaValida(["oceano"], LISTA), "padrao");
  assert.equal(AGTema.paletaValida("oceano", undefined), "padrao");   // sem a lista (tema-dados.js ausente) não arrisca
});

test("aplicar: define data-theme e data-palette; padrao não deixa atributo", () => {
  const raiz = { dataset: {} };
  AGTema.aplicar(raiz, { paleta: "oceano", modo: "escuro", pessoal: null, sistemaEscuro: false, paletas: LISTA });
  assert.deepEqual(raiz.dataset, { theme: "dark", palette: "oceano" });
  AGTema.aplicar(raiz, { paleta: "padrao", modo: "claro", pessoal: null, sistemaEscuro: false, paletas: LISTA });
  assert.deepEqual(raiz.dataset, { theme: "light" });
  AGTema.aplicar(raiz, { paleta: "neon", modo: "claro", pessoal: "dark", sistemaEscuro: false, paletas: LISTA });
  assert.deepEqual(raiz.dataset, { theme: "dark" });   // paleta fora da lista = padrão, e o pessoal vence o modo
});

test("lerPessoal: só dark e light valem; armazenamento ausente ou que lança erro é sem escolha", () => {
  const com = (v) => ({ getItem: (k) => (k === "ag-theme" ? v : null) });
  assert.equal(AGTema.lerPessoal(com("dark")), "dark");
  assert.equal(AGTema.lerPessoal(com("light")), "light");
  assert.equal(AGTema.lerPessoal(com("blue")), null);
  assert.equal(AGTema.lerPessoal(com(null)), null);
  assert.equal(AGTema.lerPessoal(null), null);
  assert.equal(AGTema.lerPessoal(undefined), null);
  assert.equal(AGTema.lerPessoal({ getItem() { throw new Error("bloqueado"); } }), null);
});
