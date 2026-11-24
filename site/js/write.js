// Escrita no workspace: funções puras (rodam no navegador e no Node) e as chamadas à API do serve.py.
// slugTitulo e montarNota têm o mesmo resultado que slug_titulo e montar_nota do agwrite.py:
// os dois lados são testados com tests/casos_nota.json, para a prévia nunca divergir do arquivo criado.

const AGWrite = (function () {
  const S = typeof AGSearch !== "undefined" ? AGSearch : require("./search.js");

  // 'Reunião de Sexta!' -> 'reuniao-de-sexta' (até 80 caracteres)
  function slugTitulo(titulo) {
    return S.norm(titulo).replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "").slice(0, 80).replace(/-+$/, "");
  }

  // Frontmatter de nota nova: 'tags:' se houver tags, 'status:' se houver status (espaços repetidos viram um só).
  function frontmatter(tags, status) {
    const lista = [...new Set(tags.map(S.normTag).filter(Boolean))];
    const st = (status || "").split(/\s+/).filter(Boolean).join(" ");
    const linhas = [];
    if (lista.length) linhas.push(`tags: [${lista.join(", ")}]`);
    if (st) linhas.push(`status: ${st}`);
    return linhas.length ? `---\n${linhas.join("\n")}\n---\n` : "";
  }

  // Conteúdo do arquivo novo. Corpo que já começa com '# ' mantém o próprio título.
  function montarNota(titulo, tags, corpo, status) {
    corpo = corpo.replace(/\r\n/g, "\n").trim();
    if (!corpo.startsWith("# ")) corpo = "# " + titulo.split(/\s+/).filter(Boolean).join(" ") + (corpo ? "\n\n" + corpo : "");
    return frontmatter(tags, status) + corpo + "\n";
  }

  // Alterna [ ] e [x] na linha `linha` (a partir de 0, no arquivo inteiro, frontmatter incluído).
  // Devolve null se essa linha não é mais um item de checklist: o arquivo mudou e quem chamou deve cancelar.
  function alternarCaixa(texto, linha) {
    const linhas = texto.split("\n");
    const m = /^(\s*-\s+\[)([ xX])(\]\s+[\s\S]*)$/.exec(linhas[linha] ?? "");
    if (!m) return null;
    linhas[linha] = m[1] + (m[2] === " " ? "x" : " ") + m[3];
    return linhas.join("\n");
  }

  // Itens {titulo, caminho, ...} que contêm todas as palavras da consulta no título ou no caminho.
  // Ignora acento e caixa; consulta vazia devolve todos. Mantém a ordem recebida.
  function filtrarPaleta(itens, consulta) {
    const palavras = S.norm(consulta).split(/\s+/).filter(Boolean);
    return itens.filter((it) => {
      const alvo = S.norm(it.titulo + " " + it.caminho);
      return palavras.every((p) => alvo.includes(p));
    });
  }

  // ---------- API ----------

  // Devolve { status, ...corpo }. Erros de rede (servidor parado) propagam como exceção.
  async function chamar(rota, corpo) {
    const opcoes = corpo === undefined
      ? { cache: "no-store" }
      : { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(corpo) };
    const r = await fetch(rota, opcoes);
    let dados;
    try { dados = await r.json(); } catch (e) { dados = { erro: "Resposta inesperada do servidor.", codigo: "resposta" }; }
    return { status: r.status, ...dados };
  }

  return {
    slugTitulo, frontmatter, montarNota, alternarCaixa, filtrarPaleta,
    ping: () => chamar("/api/ping"),
    versao: () => chamar("/api/versao"),
    estado: () => chamar("/api/estado"),
    salvar: (file, texto, base_mtime) => chamar("/api/salvar", { file, texto, base_mtime }),
    nova: (pasta, titulo, tags, corpo, status) => chamar("/api/nova", { pasta, titulo, tags, corpo, status: status || "" }),
    config: () => chamar("/api/config"),
    configSalvar: (valores, base_versao) => chamar("/api/config", { valores, base_versao }),
    configDesfazer: () => chamar("/api/config/desfazer", {}),
    postit: (file, postit) => chamar("/api/postit", { file, postit }),
    apagarPostit: (file, id) => chamar("/api/postit/apagar", { file, id }),
  };
})();

if (typeof module !== "undefined") module.exports = AGWrite;
