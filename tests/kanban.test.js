const test = require("node:test");
const assert = require("node:assert/strict");
const K = require("../site/js/kanban-model.js");
const { markdownToHtml } = require("../site/js/markdown.js");

test("chaveColuna: acento, caixa e hífen não separam colunas", () => {
  for (const s of ["A fazer", "a-fazer", "À FAZER", " a  fazer "]) assert.equal(K.chaveColuna(s), "a fazer", s);
  assert.equal(K.chaveColuna("Em revisão"), "em revisao");
  assert.equal(K.chaveColuna("!!!"), "");
});

test("lerStatus: só o frontmatter conta", () => {
  assert.equal(K.lerStatus("---\ntags: [a]\nstatus: Fazendo\n---\n# T\n"), "Fazendo");
  assert.equal(K.lerStatus("---\r\nstatus: Em revisão\r\n---\r\n# T\r\n"), "Em revisão");
  assert.equal(K.lerStatus("---\nSTATUS :  'Feito' \n---\n"), "Feito");
  assert.equal(K.lerStatus('---\nstatus: "A fazer"\n---\n'), "A fazer");
  assert.equal(K.lerStatus("---\nstatus:\n---\n"), null, "vazio");
  assert.equal(K.lerStatus("# T\n\nstatus: Fazendo\n"), null, "sem frontmatter");
  assert.equal(K.lerStatus("---\ntags: [a]\n---\n# T\n\nstatus: Fazendo\n"), null, "status no corpo não conta");
  assert.equal(K.lerStatus("---\ntags: [a]\n---\n# T\n"), null);
});

test("alterarStatus: troca só a linha do status", () => {
  const t = "---\ntags: [a, b]\nstatus: Ideia\n---\n# T\n\nstatus: Ideia\n- [ ] x\n";
  assert.equal(K.alterarStatus(t, "Fazendo"), t.replace("status: Ideia\n---", "status: Fazendo\n---"));
  assert.equal(K.alterarStatus("---\r\nstatus: a\r\n---\r\n# T\r\n", "b"), "---\r\nstatus: b\r\n---\r\n# T\r\n");
  assert.equal(K.alterarStatus("---\ntags: [a]\n---\n# T\n", "b"), null, "sem linha de status");
  assert.equal(K.alterarStatus("# T\n\nstatus: a\n", "b"), null, "status no corpo não conta");
});

const DOCS = [
  { id: "inicio", title: "Início", file: "INICIO.md", fallback: "# Início\n\n- [ ] um\n- [x] dois\n```\n- [ ] no código\n```\n- [ ] tres\n" },
  { id: "a-ideia", title: "Ideia A", file: "01-A/ideia-a.md", fallback: "---\ntags: [x]\nstatus: Ideia\n---\n# Ideia A\n\n- [ ] item da nota\n" },
  { id: "a-fazer1", title: "Tarefa", file: "01-A/tarefa.md", fallback: "---\nstatus: a-fazer\n---\n# Tarefa\n" },
  { id: "b-pronta", title: "Pronta", file: "02-B/sub/pronta.md", fallback: "---\nstatus: FEITO\n---\n# Pronta\n" },
  { id: "b-rev", title: "Revisar", file: "02-B/revisar.md", fallback: "---\nstatus: Em revisão\n---\n# Revisar\n" },
  { id: "b-rev2", title: "Revisar 2", file: "02-B/revisar2.md", fallback: "---\nstatus: em-revisao\n---\n# Revisar 2\n" },
  { id: "b-prog", title: "Andamento", file: "02-B/andamento.md", fallback: "---\nstatus: em-progresso\n---\n# Andamento\n" },
  { id: "c-sem", title: "Sem status", file: "03-C/sem.md", fallback: "---\ntags: [x]\n---\n# Sem\n" },
  { id: "c-vazio", title: "Vazio", file: "03-C/vazio.md", fallback: "---\nstatus: !!!\n---\n# Vazio\n" },
];

test("montarQuadro: A fazer, Em progresso e Feito são fixas; o resto vem no meio, em ordem alfabética, na primeira grafia", () => {
  const q = K.montarQuadro([], {});
  assert.deepEqual(q.colunas.map((c) => c.rotulo), ["A fazer", "Em progresso", "Feito"], "as três fixas existem vazias");
  const c = K.montarQuadro(DOCS, { "a-ideia": ["x"] }).colunas;
  assert.deepEqual(c.map((x) => x.rotulo), ["A fazer", "Em progresso", "Em revisão", "Ideia", "Feito"]);
  assert.equal(c[2].cartoes.length, 2, "'Em revisão' e 'em-revisao' são a mesma coluna");
  assert.deepEqual(c.map((x) => x.fixa), [true, true, false, false, true]);
  assert.deepEqual(c[1].cartoes.map((x) => x.chave), ["n:02-B/andamento.md"], "'em-progresso' cai na coluna fixa Em progresso");
});

test("montarQuadro: colunas extras aparecem mesmo vazias e mantêm a grafia recebida", () => {
  const c = K.montarQuadro([DOCS[0]], {}, ["Ideia", "em-revisao", "A fazer", "em-progresso", "!!!"]).colunas;
  assert.deepEqual(c.map((x) => x.rotulo), ["A fazer", "Em progresso", "em-revisao", "Ideia", "Feito"], "'em-progresso' não cria outra coluna");
  assert.deepEqual(c.map((x) => x.cartoes.length), [2, 0, 0, 0, 1]);
  const d = K.montarQuadro(DOCS, {}, ["Revisão"]).colunas.map((x) => x.rotulo);
  assert.ok(d.includes("Revisão") && d.includes("Em revisão"), "colunas diferentes continuam diferentes");
});

test("montarQuadro: notas e itens misturados, em ordem de documento", () => {
  const c = Object.fromEntries(K.montarQuadro(DOCS, { "a-ideia": ["x"] }).colunas.map((x) => [x.chave, x]));
  assert.deepEqual(c["a fazer"].cartoes.map((x) => x.chave), ["i:INICIO.md:2", "i:INICIO.md:7", "i:01-A/ideia-a.md:6", "n:01-A/tarefa.md"]);
  assert.deepEqual(c["feito"].cartoes.map((x) => x.chave), ["i:INICIO.md:3", "n:02-B/sub/pronta.md"]);
  assert.deepEqual(c["ideia"].cartoes.map((x) => x.chave), ["n:01-A/ideia-a.md"], "os itens da nota ficam em A fazer/Feito");
  const nota = c["ideia"].cartoes[0];
  assert.deepEqual([nota.tipo, nota.titulo, nota.pasta, nota.tags, nota.id], ["nota", "Ideia A", "01-A", ["x"], "a-ideia"]);
  const item = c["a fazer"].cartoes[0];
  assert.deepEqual([item.tipo, item.texto, item.docTitulo, item.linha, item.feito], ["item", "um", "Início", 2, false]);
  assert.ok(c["a fazer"].cartoes.some((x) => x.chave === "i:01-A/ideia-a.md:6"), "o item do documento com status também é cartão");
  const todos = Object.values(c).flatMap((x) => x.cartoes.map((k) => k.chave));
  assert.ok(!todos.some((k) => k.includes("sem.md") && k.startsWith("n:")), "nota sem status fica fora");
  assert.ok(!todos.includes("n:03-C/vazio.md"), "status sem letra nem número fica fora");
  assert.ok(!todos.includes("i:INICIO.md:5"), "item dentro de bloco de código não conta");
});

test("itens: a linha de cada item é a mesma que o markdown.js põe em data-linha", () => {
  for (const d of DOCS) {
    const html = [...markdownToHtml(d.fallback).matchAll(/data-linha="(\d+)"/g)].map((m) => Number(m[1]));
    assert.deepEqual(K.itens(d.fallback).map((i) => i.linha), html, d.id);
  }
  const crlf = "---\r\nstatus: a\r\n---\r\n# T\r\n\r\n- [ ] x\r\n";
  assert.deepEqual(K.itens(crlf).map((i) => i.linha), [5]);
});

test("destinoPermitido: item só em A fazer ou Feito; mesma coluna não é movimento", () => {
  const nota = { tipo: "nota", coluna: "ideia" };
  const item = { tipo: "item", coluna: "a fazer" };
  assert.equal(K.destinoPermitido(nota, "fazendo"), true);
  assert.equal(K.destinoPermitido(nota, "ideia"), false);
  assert.equal(K.destinoPermitido(item, "feito"), true);
  assert.equal(K.destinoPermitido(item, "fazendo"), false);
  assert.equal(K.destinoPermitido(item, "a fazer"), false);
});

test("moverCartao: nota troca o status; item alterna a caixa; arquivo que mudou devolve null", () => {
  const c = Object.fromEntries(K.montarQuadro(DOCS, {}).colunas.map((x) => [x.chave, x]));
  const nota = c["ideia"].cartoes[0];
  const doc = DOCS[1];
  assert.equal(K.moverCartao(nota, { chave: "fazendo", rotulo: "Fazendo" }, doc.fallback), doc.fallback.replace("status: Ideia", "status: Fazendo"));
  assert.equal(K.moverCartao(nota, { chave: "fazendo", rotulo: "Fazendo" }, "# sem frontmatter\n"), null);

  const item = c["a fazer"].cartoes[0];
  const inicio = DOCS[0].fallback;
  assert.equal(K.moverCartao(item, { chave: "feito", rotulo: "Feito" }, inicio), inicio.replace("- [ ] um", "- [x] um"));
  assert.equal(K.moverCartao(item, { chave: "a fazer", rotulo: "A fazer" }, inicio), null, "já está lá");
  const feito = c["feito"].cartoes.find((x) => x.tipo === "item");
  assert.equal(K.moverCartao(feito, { chave: "a fazer", rotulo: "A fazer" }, inicio), inicio.replace("- [x] dois", "- [ ] dois"));
  // o arquivo mudou por fora: linhas novas no começo deslocam o item, ou o texto dele foi trocado
  assert.equal(K.moverCartao(item, { chave: "feito", rotulo: "Feito" }, "novo\n" + inicio), null);
  assert.equal(K.moverCartao(item, { chave: "feito", rotulo: "Feito" }, inicio.replace("um", "outro")), null);
});

test("filtrarQuadro: sem consulta a coluna Feito fica escondida e só se sabe quantos cartões há nela", () => {
  const q = K.montarQuadro(DOCS, {});
  const v = K.filtrarQuadro(q, "");
  assert.deepEqual(v.colunas.map((c) => c.rotulo), ["A fazer", "Em progresso", "Em revisão", "Ideia"]);
  assert.equal(v.busca, false);
  assert.equal(v.feitosOcultos, 2, "o item [x] e a nota com status FEITO");
  assert.deepEqual(K.filtrarQuadro(q, "   ").colunas.length, 4, "só espaços não é busca");
});

test("filtrarQuadro: com consulta, todas as colunas (Feito também) mostram só o que combina", () => {
  const q = K.montarQuadro(DOCS, { "a-ideia": ["dados"], "b-pronta": ["ons"] });
  const v = K.filtrarQuadro(q, "PRONTA");
  assert.deepEqual(v.colunas.map((c) => c.rotulo), ["A fazer", "Em progresso", "Em revisão", "Ideia", "Feito"]);
  assert.equal(v.busca, true);
  assert.equal(v.feitosOcultos, 0);
  assert.deepEqual(v.colunas.flatMap((c) => c.cartoes.map((k) => k.chave)), ["n:02-B/sub/pronta.md"], "a nota feita aparece buscando");
  const chaves = (consulta) => K.filtrarQuadro(q, consulta).colunas.flatMap((c) => c.cartoes.map((k) => k.chave));
  assert.deepEqual(chaves("dados"), ["n:01-A/ideia-a.md"], "acha pela tag");
  assert.deepEqual(chaves("02-b sub"), ["n:02-B/sub/pronta.md"], "acha pela pasta, em qualquer ordem de palavras");
  assert.deepEqual(chaves("dois"), ["i:INICIO.md:3"], "acha o texto de um item feito");
  assert.deepEqual(chaves("inicio tres"), ["i:INICIO.md:7"], "acha o item pelo documento de origem, com todas as palavras");
  assert.deepEqual(chaves("revisão"), ["n:02-B/revisar.md", "n:02-B/revisar2.md"], "ignora acento e acha pelo nome da coluna");
  assert.deepEqual(chaves("feito"), ["i:INICIO.md:3", "n:02-B/sub/pronta.md"], "buscar 'feito' mostra tudo o que está feito");
  assert.deepEqual(chaves("zzz"), []);
  assert.equal(K.filtrarQuadro(q, "zzz").colunas.length, 5, "as colunas continuam, vazias");
});
