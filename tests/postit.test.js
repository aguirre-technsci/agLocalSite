const test = require("node:test");
const assert = require("node:assert/strict");
const P = require("../site/js/postit-model.js");

test("posicaoParaPx: converte % e px, ajustando para dentro da superfície", () => {
  assert.deepEqual(P.posicaoParaPx({ x: 50, y: 100 }, 1000, 800, 200, 160), { left: 500, top: 100 });
  assert.deepEqual(P.posicaoParaPx({ x: 0, y: 0 }, 1000, 800, 200, 160), { left: 0, top: 0 });
  // x=100% encostaria a borda direita: ajusta para caber a largura do post-it
  assert.deepEqual(P.posicaoParaPx({ x: 100, y: 0 }, 1000, 800, 200, 160), { left: 800, top: 0 });
});

test("posicaoParaPx: y além do fim da superfície (documento encolheu) fica rente ao fim", () => {
  const r = P.posicaoParaPx({ x: 0, y: 5000 }, 1000, 400, 200, 160);
  assert.equal(r.top, 400 - 160);
});

test("posicaoParaPx: usa a altura do próprio post-it (redimensionado) no ajuste", () => {
  const pequeno = P.posicaoParaPx({ x: 0, y: 1000 }, 1000, 400, 200, 120);
  const grande = P.posicaoParaPx({ x: 0, y: 1000 }, 1000, 400, 200, 300);
  assert.equal(pequeno.top, 400 - 120);
  assert.equal(grande.top, 400 - 300);
});

test("posicaoParaPx: superfície menor que o post-it não dá left/top negativo", () => {
  assert.deepEqual(P.posicaoParaPx({ x: 50, y: 10 }, 150, 30, 200, 160), { left: 0, top: 0 });
});

test("pxParaPosicao: caminho inverso, x a 1 casa decimal e y inteiro", () => {
  assert.deepEqual(P.pxParaPosicao(500, 100.4, 1000, 800, 200, 160), { x: 50, y: 100 });
  assert.deepEqual(P.pxParaPosicao(83, 12, 1000, 800, 200, 160), { x: 8.3, y: 12 });
});

test("pxParaPosicao: ajusta para dentro da superfície antes de converter", () => {
  assert.deepEqual(P.pxParaPosicao(-40, -10, 1000, 800, 200, 160), { x: 0, y: 0 });
  assert.deepEqual(P.pxParaPosicao(5000, 5000, 1000, 800, 200, 160), { x: 80, y: 800 - 160 });
});

test("posicaoParaPx e pxParaPosicao: ida e volta preserva a posição", () => {
  const original = { x: 37.5, y: 812 };
  const px = P.posicaoParaPx(original, 1200, 2000, 200, 160);
  const volta = P.pxParaPosicao(px.left, px.top, 1200, 2000, 200, 160);
  assert.deepEqual(volta, original);
});

test("tamanhoValido: dentro dos limites, arredondado", () => {
  assert.deepEqual(P.tamanhoValido(250.4, 300.6), { w: 250, h: 301 });
});

test("tamanhoValido: abaixo do mínimo ou acima do máximo é ajustado", () => {
  assert.deepEqual(P.tamanhoValido(1, 1), { w: P.LARGURA_MIN, h: P.ALTURA_MIN });
  assert.deepEqual(P.tamanhoValido(9999, 9999), { w: P.LARGURA_MAX, h: P.ALTURA_MAX });
});

test("proximaCor: o ciclo amarelo, verde, azul, rosa, laranja, amarelo", () => {
  assert.equal(P.proximaCor("amarelo"), "verde");
  assert.equal(P.proximaCor("verde"), "azul");
  assert.equal(P.proximaCor("azul"), "rosa");
  assert.equal(P.proximaCor("rosa"), "laranja");
  assert.equal(P.proximaCor("laranja"), "amarelo");
});

test("proximaCor: cor desconhecida volta ao início do ciclo", () => {
  assert.equal(P.proximaCor("roxo"), "amarelo");
  assert.equal(P.proximaCor(undefined), "amarelo");
});

test("novoPostit: cor e tamanho padrão, texto vazio, x/y como pedidos, id no formato", () => {
  const p = P.novoPostit(62, 80);
  assert.equal(p.cor, "amarelo");
  assert.equal(p.texto, "");
  assert.equal(p.x, 62);
  assert.equal(p.y, 80);
  assert.equal(p.w, P.LARGURA_PADRAO);
  assert.equal(p.h, P.ALTURA_PADRAO);
  assert.match(p.id, /^[a-z0-9]{4,32}$/);
});

test("novoPostit: dois post-its seguidos não colidem no id", () => {
  const ids = new Set(Array.from({ length: 20 }, () => P.novoPostit(0, 0).id));
  assert.equal(ids.size, 20);
});
