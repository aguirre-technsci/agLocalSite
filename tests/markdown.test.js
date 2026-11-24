const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const { markdownToHtml, resolveDocRef } = require("../site/js/markdown.js");

const doc = (file, id) => ({ file, id, title: id, fallback: "" });
const DOCS = [
  doc("00-a/base.md", "base"),
  doc("03-b/registros.md", "registros"),
  doc("02-c/M1/README.md", "m1"),
  doc("02-c/M2/README.md", "m2"),
  doc("99-etc/Banca_X.md", "banca"),
];
globalThis.AG_CONTENT = [{ id: "g", items: DOCS }];
const html = (md) => markdownToHtml(md);
const link = (id, txt) => `<a class="doc-link" href="#${id}"><code>${txt}</code></a>`;

test("resolveDocRef: caminho completo, nome único, ambíguo, inexistente", () => {
  assert.equal(resolveDocRef("03-b/registros.md", DOCS).id, "registros");
  assert.equal(resolveDocRef("Banca_X.md", DOCS).id, "banca");
  assert.equal(resolveDocRef("README.md", DOCS), null);
  assert.equal(resolveDocRef("02-c/M2/README.md", DOCS).id, "m2");
  assert.equal(resolveDocRef("03-b/nao-existe.md", DOCS), null);
  assert.equal(resolveDocRef("outra-pasta/registros.md", DOCS), null);
  assert.equal(resolveDocRef(".md", DOCS), null);
});

test("resolveDocRef: ignora maiúsculas e minúsculas", () => {
  assert.equal(resolveDocRef("banca_x.MD", DOCS).id, "banca");
  assert.equal(resolveDocRef("03-B/Registros.md", DOCS).id, "registros");
});

test("citação entre crases vira link com o código dentro", () => {
  assert.equal(html("Ver `03-b/registros.md` agora."), `<p>Ver ${link("registros", "03-b/registros.md")} agora.</p>`);
  assert.ok(html("Ver `Banca_X.md`.").includes(link("banca", "Banca_X.md")));
});

test("o que não resolve continua código simples", () => {
  assert.equal(html("`README.md`"), "<p><code>README.md</code></p>");
  assert.equal(html("`Recalibracao.docx` e `extrair.py` e `.md`"), "<p><code>Recalibracao.docx</code> e <code>extrair.py</code> e <code>.md</code></p>");
  assert.equal(html("`03-b/nao-existe.md`"), "<p><code>03-b/nao-existe.md</code></p>");
});

test("vale em título, lista e célula de tabela", () => {
  assert.ok(html("# Ver `Banca_X.md`").includes(link("banca", "Banca_X.md")));
  assert.ok(html("- item `Banca_X.md`").includes(link("banca", "Banca_X.md")));
  assert.ok(html("| a | b |\n|---|---|\n| `Banca_X.md` | x |").includes(`<td>${link("banca", "Banca_X.md")}</td>`));
});

test("bloco de código cercado não vira link", () => {
  assert.equal(html("```\n`Banca_X.md`\n```"), "<pre><code>`Banca_X.md`</code></pre>");
});

test("dados reais: todo link gerado aponta para um documento do menu", { skip: !fs.existsSync(path.join(__dirname, "..", "site/js/content.js")) && "content.js ainda não foi gerado (rode sync.py)" }, () => {
  const root = path.join(__dirname, "..");
  const ctx = {};
  vm.createContext(ctx);
  vm.runInContext(fs.readFileSync(path.join(root, "site/js/content.js"), "utf8") + ";this.C = AG_CONTENT;", ctx);
  const items = ctx.C.flatMap((g) => g.items);
  globalThis.AG_CONTENT = ctx.C;
  const ids = new Set(items.map((i) => i.id));
  let total = 0;
  for (const it of items) {
    for (const m of html(it.fallback).matchAll(/<a class="doc-link" href="#([^"]+)">/g)) {
      total++;
      assert.ok(ids.has(m[1]), `${it.file} aponta para id inexistente: ${m[1]}`);
    }
  }
  assert.ok(total > 0);
});

test("checklist: cada caixa leva data-linha com a linha do arquivo original, frontmatter contado", () => {
  assert.equal(html("- [ ] a\n- [x] b"), '<ul><li><input type="checkbox" data-linha="0" disabled>a</li><li><input type="checkbox" data-linha="1" checked disabled>b</li></ul>');
  const com = html("---\ntags: [x]\n---\n# T\n\n- [ ] a");
  assert.ok(com.includes('data-linha="5"'), com);
  assert.ok(html("---\r\ntags: [x]\r\n---\r\n- [ ] a").includes('data-linha="3"'));
  assert.ok(!html("- item comum\n1. outro").includes("data-linha"));
  assert.ok(!html("```\n- [ ] no código\n```").includes("data-linha"));
});

test("links: aspas no destino não fecham o href nem injetam atributo", () => {
  for (const md of ['[x](http://a" onmouseover="alert(1)', '[x](http://a" onmouseover="alert1)', "[x](http://a' onmouseover='alert1)"]) {
    const h = html(md);
    // sem o conteúdo entre aspas (valores de atributo), nenhuma tag pode ter onmouseover como atributo próprio
    assert.doesNotMatch(h.replace(/"[^"]*"/g, '""'), /<[^>]*\sonmouseover=/, md);
  }
  assert.match(html('[x](http://a" onmouseover="alert1)'), /<a href="http:\/\/a&quot; onmouseover=&quot;alert1"/);
});

test("links: esquemas perigosos viram texto, sem <a>", () => {
  for (const u of ["javascript:alert(1)", "JaVaScRiPt:alert(1)", "java\tscript:alert(1)", " javascript:1", "data:text/html;base64,AAAA", "vbscript:x", "file:///etc/passwd"]) {
    const h = html(`[clique](${u})`);
    assert.doesNotMatch(h, /<a /, u);
    assert.match(h, /clique/);
  }
});

test("links: http, https, mailto, relativo e âncora continuam funcionando", () => {
  assert.match(html("[a](https://exemplo.com/p?x=1&y=2)"), /<a href="https:\/\/exemplo.com\/p\?x=1&amp;y=2" target="_blank" rel="noopener noreferrer">a<\/a>/);
  assert.match(html("[a](mailto:oi@exemplo.com)"), /href="mailto:oi@exemplo.com"/);
  assert.match(html("[a](../outra/nota.md)"), /href="..\/outra\/nota.md"/);
  assert.match(html("[a](#secao)"), /<a href="#secao">a<\/a>/);
});

test("links: um nível de parênteses no destino não corta a URL", () => {
  const h = html("veja [Foo](https://pt.wikipedia.org/wiki/Foo_(bar)) hoje");
  assert.match(h, /href="https:\/\/pt.wikipedia.org\/wiki\/Foo_\(bar\)"/);
  assert.match(h, /<\/a> hoje/);
});

test("escapeHtml escapa aspas simples e duplas", () => {
  const { escapeHtml } = require("../site/js/markdown.js");
  assert.equal(escapeHtml(`<a href="x" t='y'>&`), "&lt;a href=&quot;x&quot; t=&#39;y&#39;&gt;&amp;");
});

test("agTexto: usa o config.json > textos; chave ausente ou vazia mantém o padrão", () => {
  const { agTexto } = require("../site/js/markdown.js");
  const antes = globalThis.AG_CONFIG;
  try {
    delete globalThis.AG_CONFIG;
    assert.equal(agTexto("grafo", "◎ Grafo de tags"), "◎ Grafo de tags");
    globalThis.AG_CONFIG = { textos: { grafo: "◎ Mapa", quadro: "", menu: 5 } };
    assert.equal(agTexto("grafo", "padrão"), "◎ Mapa");
    assert.equal(agTexto("quadro", "padrão"), "padrão");
    assert.equal(agTexto("menu", "padrão"), "padrão");
    assert.equal(agTexto("outra", "padrão"), "padrão");
  } finally {
    if (antes === undefined) delete globalThis.AG_CONFIG; else globalThis.AG_CONFIG = antes;
  }
});

test("agDefinirTextos: troca os rótulos em uso sem recarregar; null volta ao AG_CONFIG", () => {
  const { agTexto, agDefinirTextos } = require("../site/js/markdown.js");
  const antes = globalThis.AG_CONFIG;
  try {
    globalThis.AG_CONFIG = { textos: { grafo: "do arquivo" } };
    assert.equal(agTexto("grafo", "padrão"), "do arquivo");
    agDefinirTextos({ grafo: "◎ Novo" });                 // o painel acabou de salvar
    assert.equal(agTexto("grafo", "padrão"), "◎ Novo");
    agDefinirTextos({});                                  // todos voltaram ao padrão
    assert.equal(agTexto("grafo", "padrão"), "padrão");
    agDefinirTextos(null);                                // sem textos novos: volta a ler o AG_CONFIG
    assert.equal(agTexto("grafo", "padrão"), "do arquivo");
  } finally {
    agDefinirTextos(null);
    if (antes === undefined) delete globalThis.AG_CONFIG; else globalThis.AG_CONFIG = antes;
  }
});

test("fence ``` sem fechar: o texto depois dele continua visível (como código), não some", () => {
  const html = markdownToHtml("# T\n\nantes\n\n```js\ncodigo\ndepois");
  assert.match(html, /<h1 id="t">T<\/h1>/);
  assert.match(html, /<pre><code>codigo\ndepois<\/code><\/pre>/);
});

test("código inline não recebe negrito nem link por dentro", () => {
  const html = markdownToHtml("`**x**` e `[a](http://x.com)`");
  assert.equal(html, "<p><code>**x**</code> e <code>[a](http://x.com)</code></p>");
});

test("imagem não vira link nem deixa '!' solto; carrega nada", () => {
  const html = markdownToHtml("![logo](img/logo.png) texto ![](a.png)");
  assert.ok(!html.includes("<a ") && !html.includes("<img") && !html.includes("!"));
  assert.match(html, /\[imagem: logo\].*\[imagem\]/);
});

test("tabela: | dentro de `código` ou escapado não separa a célula", () => {
  const html = markdownToHtml("| a | b |\n|---|---|\n| `x|y` | z \\| w |");
  assert.equal((html.match(/<td>/g) || []).length, 2);
  assert.match(html, /<td><code>x\|y<\/code><\/td><td>z \| w<\/td>/);
});

test("títulos ganham id estilo GitHub (sem acento, repetido ganha sufixo) e link #id continua seguro", () => {
  const html = markdownToHtml("# Visão geral\n\n## Visão geral\n\n[ir](#visao-geral)\n\n# <b>x</b> \"q\"");
  assert.match(html, /<h1 id="visao-geral">/);
  assert.match(html, /<h2 id="visao-geral-1">/);
  for (const [, id] of html.matchAll(/ id="([^"]*)"/g)) assert.match(id, /^[a-z0-9-]+$/);
});

test("imagem local relativa vira <img> apontando para a pasta do documento", () => {
  const h = (md, pasta) => markdownToHtml(md, { pasta });
  assert.equal(h("![logo](img/a b.png)", "docs/plans"), '<p><img src="../docs/plans/img/a%20b.png" alt="logo" loading="lazy"></p>');
  assert.match(h("![x](../fig.PNG \"titulo\")", "docs/plans"), /<img src="\.\.\/docs\/fig\.PNG" alt="x"/);
  assert.match(h("![x](./a.svg)", ""), /<img src="\.\.\/a\.svg"/);
});

test("imagem que não é local e segura nunca vira <img>", () => {
  const ruins = ["http://x.com/a.png", "https://x.com/a.png", "//x.com/a.png", "data:image/png;base64,AAAA", "javascript:alert(1)//.png",
    "/etc/a.png", "\\\\srv\\a.png", "../../fora.png", "a.png?x=1", "a.png#f", "doc.pdf", "semextensao", "a.png\" onerror=\"x"];
  for (const u of ruins) {
    const html = markdownToHtml(`![alt](${u})`, { pasta: "docs" });
    assert.ok(!html.includes("<img"), `virou <img>: ${u} => ${html}`);
  }
  assert.ok(!markdownToHtml("![a](x.png)").includes("<img"), "sem pasta do documento não resolve");
  assert.ok(!markdownToHtml("![a](x.png)", { pasta: "docs" }).includes("onerror"));
});
