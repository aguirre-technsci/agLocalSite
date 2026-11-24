// painel-model.js: lógica pura do painel de configurações (sem DOM e sem rede).
const test = require("node:test");
const assert = require("node:assert/strict");
const M = require("../site/js/painel-model.js");

test("montarEnvio: sem mudança, nada a enviar", () => {
  assert.deepEqual(M.montarEnvio({}, {}), {});
  const v = { titulo: "A", textos: { grafo: "G" }, tema: { paleta: "oceano" }, ignorar: ["x"], rotulos: { a: "A" }, home_prioridade: ["a"] };
  assert.deepEqual(M.montarEnvio(v, JSON.parse(JSON.stringify(v))), {});
  assert.deepEqual(M.montarEnvio(undefined, undefined), {});
});

test("montarEnvio: espaço nas pontas e vazio equivalente a ausente não geram diferença", () => {
  assert.deepEqual(M.montarEnvio({ titulo: "A" }, { titulo: "  A  " }), {});
  assert.deepEqual(M.montarEnvio({}, { titulo: "", subtitulo: "   " }), {});
  assert.deepEqual(M.montarEnvio({}, { ignorar: [], rotulos: {} }), {});   // vazio = padrão
});

test("montarEnvio: só as chaves alteradas", () => {
  assert.deepEqual(M.montarEnvio({ titulo: "A", etiqueta: "E" }, { titulo: "B", etiqueta: "E" }), { titulo: "B" });
  assert.deepEqual(M.montarEnvio({}, { titulo: "Novo", subtitulo: "S" }), { titulo: "Novo", subtitulo: "S" });
});

test("montarEnvio: voltar um campo ao vazio envia null", () => {
  assert.deepEqual(M.montarEnvio({ titulo: "A" }, { titulo: "" }), { titulo: null });
  assert.deepEqual(M.montarEnvio({ titulo: "A" }, {}), { titulo: null });
  assert.deepEqual(M.montarEnvio({ ignorar: ["a"] }, { ignorar: [] }), { ignorar: null });
  assert.deepEqual(M.montarEnvio({ rotulos: { a: "A" } }, { rotulos: {} }), { rotulos: null });
});

test("montarEnvio: textos e tema só com a subchave que mudou", () => {
  assert.deepEqual(M.montarEnvio({ textos: { grafo: "G", quadro: "Q" } }, { textos: { grafo: "Novo", quadro: "Q" } }), { textos: { grafo: "Novo" } });
  assert.deepEqual(M.montarEnvio({ textos: { grafo: "G" } }, { textos: {} }), { textos: { grafo: null } });
  assert.deepEqual(M.montarEnvio({ textos: { grafo: "G" } }, { textos: { grafo: "" } }), { textos: { grafo: null } });
  assert.deepEqual(M.montarEnvio({}, { tema: { paleta: "ameixa", modo: "claro" } }), { tema: { paleta: "ameixa", modo: "claro" } });
  assert.deepEqual(M.montarEnvio({ tema: { paleta: "oceano", modo: "escuro" } }, { tema: { paleta: "oceano", modo: "sistema" } }), { tema: { modo: "sistema" } });
});

test("montarEnvio: o rodapé vazio quer dizer ocultar, e é diferente de ausente", () => {
  assert.deepEqual(M.montarEnvio({}, { textos: { rodape: "" } }), { textos: { rodape: "" } });
  assert.deepEqual(M.montarEnvio({ textos: { rodape: "" } }, {}), { textos: { rodape: null } });
  assert.deepEqual(M.montarEnvio({ textos: { rodape: "" } }, { textos: { rodape: "" } }), {});
});

test("montarEnvio: lista ou mapa alterado vai inteiro; ordem da lista conta; ordem das chaves do mapa não", () => {
  assert.deepEqual(M.montarEnvio({ ignorar: ["a"] }, { ignorar: ["a", "b"] }), { ignorar: ["a", "b"] });
  assert.deepEqual(M.montarEnvio({ home_prioridade: ["a", "b"] }, { home_prioridade: ["b", "a"] }), { home_prioridade: ["b", "a"] });
  assert.deepEqual(M.montarEnvio({ rotulos: { a: "A", b: "B" } }, { rotulos: { b: "B", a: "A" } }), {});
  assert.deepEqual(M.montarEnvio({ rotulos: { a: "A" } }, { rotulos: { a: "A", b: "B" } }), { rotulos: { a: "A", b: "B" } });
});

test("montarEnvio: home_prioridade vazia é uma escolha (nenhum arquivo primeiro), não o padrão", () => {
  assert.deepEqual(M.montarEnvio({}, { home_prioridade: [] }), { home_prioridade: [] });
  assert.deepEqual(M.montarEnvio({ home_prioridade: ["a"] }, { home_prioridade: [] }), { home_prioridade: [] });
});

test("montarEnvio não altera os argumentos", () => {
  const o = { textos: { grafo: "G" }, ignorar: ["a"] }, a = { textos: { grafo: "N" }, ignorar: ["a", "b"] };
  const co = JSON.stringify(o), ca = JSON.stringify(a);
  M.montarEnvio(o, a);
  assert.equal(JSON.stringify(o), co);
  assert.equal(JSON.stringify(a), ca);
});

test("envioPadroes: todas as chaves recebidas em null", () => {
  const chaves = ["titulo", "textos", "tema", "ignorar"];
  assert.deepEqual(M.envioPadroes(chaves), { titulo: null, textos: null, tema: null, ignorar: null });
  assert.deepEqual(M.envioPadroes([]), {});
});

test("rodapeEstado e rodapeValor: padrão, ocultar e personalizado", () => {
  assert.equal(M.rodapeEstado(undefined), "padrao");
  assert.equal(M.rodapeEstado({}), "padrao");
  assert.equal(M.rodapeEstado({ rodape: "" }), "ocultar");
  assert.equal(M.rodapeEstado({ rodape: "Meu rodapé" }), "personalizado");
  assert.equal(M.rodapeValor("padrao", "x"), null);
  assert.equal(M.rodapeValor("ocultar", "x"), "");
  assert.equal(M.rodapeValor("personalizado", "Meu rodapé"), "Meu rodapé");
  assert.equal(M.rodapeValor("personalizado", "   "), null);   // personalizado sem texto volta ao padrão, não oculta por engano
});

test("validarCampo: tamanhos com os limites recebidos do servidor", () => {
  const lim = { texto: 5, rodape: 8, nome: 4 };
  assert.equal(M.validarCampo("titulo", "12345", lim), null);
  assert.match(M.validarCampo("titulo", "123456", lim), /5 caracteres/);
  assert.match(M.validarCampo("textos.grafo", "123456", lim), /5 caracteres/);
  assert.equal(M.validarCampo("rodape", "12345678", lim), null);
  assert.match(M.validarCampo("rodape", "123456789", lim), /8 caracteres/);
  assert.match(M.validarCampo("rotulo", "123456", lim), /5 caracteres/);
  assert.match(M.validarCampo("ignorar", "12345", lim), /4 caracteres/);
});

test("validarCampo: sem limites usa os padrões da spec (120, 2000, 100)", () => {
  assert.equal(M.validarCampo("titulo", "a".repeat(120)), null);
  assert.match(M.validarCampo("titulo", "a".repeat(121)), /120 caracteres/);
  assert.match(M.validarCampo("rodape", "a".repeat(2001)), /2000 caracteres/);
  assert.match(M.validarCampo("ignorar", "a".repeat(101)), /100 caracteres/);
});

test("validarCampo: nomes de pasta e de arquivo", () => {
  assert.match(M.validarCampo("ignorar", "a/b"), /sem "\/" nem "\\"/);
  assert.match(M.validarCampo("ignorar", "a\\b"), /sem "\/" nem "\\"/);
  assert.match(M.validarCampo("ignorar", "   "), /nome/);
  assert.equal(M.validarCampo("ignorar", "dist"), null);
  assert.match(M.validarCampo("home_prioridade", "readme.md"), /sem "\.md"/);
  assert.match(M.validarCampo("home_prioridade", "README.MD"), /sem "\.md"/);
  assert.equal(M.validarCampo("home_prioridade", "leia-me"), null);
});

test("validarCampo: campo desconhecido não é erro do cliente (o servidor decide)", () => {
  assert.equal(M.validarCampo("inventado", "x"), null);
  assert.equal(M.validarCampo("titulo", 5), null);
});

test("moverItem: sobe, desce, respeita os extremos e não altera a original", () => {
  const l = ["a", "b", "c"];
  assert.deepEqual(M.moverItem(l, 1, -1), ["b", "a", "c"]);
  assert.deepEqual(M.moverItem(l, 1, 1), ["a", "c", "b"]);
  assert.deepEqual(M.moverItem(l, 0, -1), ["a", "b", "c"]);
  assert.deepEqual(M.moverItem(l, 2, 1), ["a", "b", "c"]);
  assert.deepEqual(M.moverItem(l, 9, 1), ["a", "b", "c"]);
  assert.deepEqual(l, ["a", "b", "c"]);
  assert.notEqual(M.moverItem(l, 0, 0), l);   // sempre uma cópia
});
