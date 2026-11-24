// Conversor markdown -> HTML minimalista, sem dependências externas.
// Cobre: headers, negrito/itálico, listas (com checkbox: cada caixa leva data-linha), tabelas,
// links, código inline/bloco, citações, hr e parágrafos.
// Trecho entre crases que termina em .md e bate com um documento do menu
// (caminho completo ou nome de arquivo único) vira link para ele.
// Não é um parser completo de markdown — é suficiente para os
// documentos deste workspace. Se precisar de mais recursos,
// edite as funções abaixo.

function escapeHtml(str) {
  return str
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")   // sem isso, uma aspa em [t](url) fecha o href e injeta atributo (onmouseover=...)
    .replace(/'/g, "&#39;");
}

// Destino de link: só http(s), mailto, âncora (#) e caminho relativo. javascript:, data:, vbscript: etc. viram texto puro.
// Espaços e caracteres de controle no meio do esquema ("java\tscript:") são ignorados pelos navegadores, então saem antes da checagem.
function safeUrl(u) {
  const s = u.trim();
  const esquema = /^([a-z][a-z0-9+.\-]*):/i.exec(s.replace(/[\u0000-\u0020\u007f-\u009f]/g, ""));
  if (!esquema) return s;
  return /^(https?|mailto)$/i.test(esquema[1]) ? s : null;
}

// Documentos do menu. content.js carrega depois deste arquivo, então a lista é lida na hora do uso.
function docList() {
  return typeof AG_CONTENT !== "undefined" ? AG_CONTENT.flatMap((g) => g.items) : [];
}

// Rótulos da interface. Começam pelos do config.json (AG_CONFIG, do content.js); o painel de configurações troca por
// agDefinirTextos(...) ao salvar, sem recarregar a página (null volta a ler o AG_CONFIG).
let agTextosAtuais = null;
function agDefinirTextos(textos) {
  agTextosAtuais = textos && typeof textos === "object" ? textos : null;
}

// Texto da interface: o que o config.json > textos define, senão o padrão.
function agTexto(chave, padrao) {
  const t = agTextosAtuais !== null ? agTextosAtuais : (typeof AG_CONFIG !== "undefined" ? AG_CONFIG.textos : null);
  return t && typeof t[chave] === "string" && t[chave] !== "" ? t[chave] : padrao;
}

// Caminho completo primeiro; sem barra, vale o nome do arquivo se só um documento tem esse nome.
function resolveDocRef(ref, docs) {
  const key = ref.toLowerCase();
  const byPath = docs.find((d) => d.file.toLowerCase() === key);
  if (byPath || ref.includes("/")) return byPath || null;
  const byName = docs.filter((d) => d.file.split("/").pop().toLowerCase() === key);
  return byName.length === 1 ? byName[0] : null;
}

function codeSpan(ref) {
  const doc = /\.md$/i.test(ref) ? resolveDocRef(ref, docList()) : null;
  return doc ? `<a class="doc-link" href="#${doc.id}"><code>${ref}</code></a>` : `<code>${ref}</code>`;
}

// Pasta do documento que está sendo desenhado (relativa à raiz, ex.: "docs/plans"); null = não sabe, então nenhuma imagem local.
let pastaAtual = null;
const EXT_IMAGEM = /\.(png|jpe?g|gif|webp|avif|bmp|svg)$/i;

// Caminho de imagem do .md -> endereço no site (mesmo padrão "../" dos documentos), ou null se não for local e segura.
// Recebe o texto já escapado (&amp; &quot;). Recusa: esquema (http:, data:, javascript:), "//", caminho absoluto, "?" ou "#",
// extensão que não é imagem e ".." que sobe acima da raiz.
function srcImagemLocal(u) {
  if (pastaAtual === null) return null;
  let p = u.trim().replace(/\s+&quot;.*&quot;$/, "").replace(/&amp;/g, "&");   // tira o título opcional: ![a](x.png "titulo")
  try { p = decodeURIComponent(p); } catch (e) { return null; }
  if (!p || /^[a-z][a-z0-9+.-]*:/i.test(p) || /^[\\/]/.test(p) || /[?#\u0000-\u001f\\]/.test(p) || !EXT_IMAGEM.test(p)) return null;
  const partes = pastaAtual ? pastaAtual.split("/") : [];
  for (const seg of p.split("/")) {
    if (seg === "" || seg === ".") continue;
    if (seg === "..") { if (!partes.length) return null; partes.pop(); continue; }
    partes.push(seg);
  }
  if (!partes.length) return null;
  return "../" + partes.map(encodeURIComponent).join("/");
}

function inlineMd(text) {
  text = escapeHtml(text.replace(/\u0000/g, ""));
  // código inline (citação de documento do menu vira link). Sai do texto durante as outras trocas, para não receber negrito nem link por dentro.
  const spans = [];
  text = text.replace(/`([^`]+)`/g, (_, ref) => { spans.push(codeSpan(ref)); return `\u0000${spans.length - 1}\u0000`; });
  // imagem ![alt](caminho): só imagem local, relativa à pasta do documento, vira <img>. De fora (http, data:, //) nada é carregado:
  // um .md de terceiros poderia rastrear quem o abre. Nesses casos fica o texto alternativo, sem o "!" solto.
  text = text.replace(/!\[([^\]]*)\]\(((?:[^()]|\([^()]*\))+)\)/g, (_, alt, u) => {
    const src = srcImagemLocal(u);
    return src ? `<img src="${src}" alt="${alt}" loading="lazy">` : `[imagem${alt ? ": " + alt : ""}]`;
  });
  // negrito
  text = text.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
  // itálico
  text = text.replace(/(^|[^*])\*([^*]+)\*(?!\*)/g, "$1<em>$2</em>");
  // links [texto](url)
  // o destino aceita um nível de parênteses: [x](https://pt.wikipedia.org/wiki/Foo_(bar))
  text = text.replace(/\[([^\]]+)\]\(((?:[^()]|\([^()]*\))+)\)/g, (_, t, u) => {
    const url = safeUrl(u);
    if (url === null) return t;
    return url.startsWith("#") ? `<a href="${url}">${t}</a>` : `<a href="${url}" target="_blank" rel="noopener noreferrer">${t}</a>`;
  });
  return text.replace(/\u0000(\d+)\u0000/g, (_, n) => spans[Number(n)]);
}

// Divide uma linha de tabela em células: "|" dentro de `código` ou escapado (\|) não separa.
function splitRow(linha) {
  const l = linha.trim().replace(/^\||\|$/g, "");
  const out = [];
  let atual = "", emCodigo = false;
  for (let i = 0; i < l.length; i++) {
    const c = l[i];
    if (c === "\\" && l[i + 1] === "|") { atual += "|"; i++; continue; }
    if (c === "`") emCodigo = !emCodigo;
    if (c === "|" && !emCodigo) { out.push(atual.trim()); atual = ""; continue; }
    atual += c;
  }
  out.push(atual.trim());
  return out;
}

function parseTableBlock(lines) {
  // lines[0] = header, lines[1] = separator (---|---), lines[2..] = rows
  const header = splitRow(lines[0]);
  const rows = lines.slice(2).map(splitRow);
  let html = "<table><thead><tr>";
  header.forEach(h => html += `<th>${inlineMd(h)}</th>`);
  html += "</tr></thead><tbody>";
  rows.forEach(r => {
    html += "<tr>";
    r.forEach(c => html += `<td>${inlineMd(c)}</td>`);
    html += "</tr>";
  });
  html += "</tbody></table>";
  return html;
}

// Frontmatter (bloco '---' com YAML no topo do arquivo) não aparece no texto renderizado.
// Mesma regra do graphdata.py: se as linhas não parecem YAML, é uma linha horizontal e fica.
function stripFrontmatter(md) {
  const m = /^\ufeff?---[ \t]*\r?\n([\s\S]*?)\r?\n---[ \t]*(?:\r?\n|$)/.exec(md);
  if (!m) return md;
  const yaml = m[1].split(/\r?\n/).every((l) => /^(\s*#.*|\s*-\s.*|\s+\S.*|[A-Za-z_][\w -]*:.*|\s*)$/.test(l));
  return yaml ? md.slice(m[0].length) : md;
}

// id de título no estilo do GitHub ("Visão geral" -> "visao-geral"), para links [x](#visao-geral).
function slugTitulo(texto) {
  return texto.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase()
    .replace(/[`*_\[\]()]/g, "").replace(/[^a-z0-9\s-]/g, "").trim().replace(/\s+/g, "-");
}

function markdownToHtml(md, opcoes) {
  pastaAtual = opcoes && typeof opcoes.pasta === "string" ? opcoes.pasta : null;
  try {
    return renderMarkdown(md);
  } finally {
    pastaAtual = null;
  }
}

function renderMarkdown(md) {
  const body = stripFrontmatter(md);
  const offset = md.slice(0, md.length - body.length).split("\n").length - 1; // linhas do frontmatter removido
  const lines = body.replace(/\r\n/g, "\n").split("\n");
  let html = "";
  let i = 0;
  let inCode = false;
  let codeBuf = [];
  let listBuf = [];
  let listType = null; // 'ul' | 'ol'
  const idsUsados = new Map();

  function flushList() {
    if (listBuf.length) {
      html += `<${listType}>` + listBuf.join("") + `</${listType}>`;
      listBuf = [];
      listType = null;
    }
  }

  while (i < lines.length) {
    const line = lines[i];

    // bloco de código ```
    if (/^```/.test(line)) {
      flushList();
      if (!inCode) { inCode = true; codeBuf = []; }
      else {
        html += `<pre><code>${escapeHtml(codeBuf.join("\n"))}</code></pre>`;
        inCode = false;
      }
      i++; continue;
    }
    if (inCode) { codeBuf.push(line); i++; continue; }

    // tabela: linha com | seguida de linha separadora ---|---
    if (/^\s*\|.*\|\s*$/.test(line) && lines[i + 1] && /^\s*\|?\s*-{2,}/.test(lines[i + 1])) {
      flushList();
      const tblLines = [line];
      let j = i + 1;
      while (j < lines.length && /^\s*\|.*\|\s*$/.test(lines[j])) { tblLines.push(lines[j]); j++; }
      html += parseTableBlock(tblLines);
      i = j; continue;
    }

    // headers
    let m;
    if ((m = line.match(/^(#{1,4})\s+(.*)$/))) {
      flushList();
      const level = m[1].length;
      let id = slugTitulo(m[2]);
      if (id) { const n = idsUsados.get(id) || 0; idsUsados.set(id, n + 1); if (n) id += "-" + n; }
      html += `<h${level}${id ? ` id="${id}"` : ""}>${inlineMd(m[2])}</h${level}>`;
      i++; continue;
    }

    // hr
    if (/^---+\s*$/.test(line) && line.trim() !== "") {
      flushList();
      html += "<hr>";
      i++; continue;
    }

    // blockquote
    if (/^>\s?/.test(line)) {
      flushList();
      const quoteLines = [];
      let j = i;
      while (j < lines.length && /^>\s?/.test(lines[j])) {
        quoteLines.push(lines[j].replace(/^>\s?/, ""));
        j++;
      }
      html += `<blockquote>${inlineMd(quoteLines.join(" "))}</blockquote>`;
      i = j; continue;
    }

    // listas com checkbox: - [ ] ou - [x]
    if ((m = line.match(/^\s*-\s+\[( |x|X)\]\s+(.*)$/))) {
      if (listType !== "ul") { flushList(); listType = "ul"; }
      const checked = m[1].toLowerCase() === "x" ? "checked disabled" : "disabled";
      // data-linha: índice (a partir de 0) da linha no arquivo original; o editor grava a marca por ele
      listBuf.push(`<li><input type="checkbox" data-linha="${i + offset}" ${checked}>${inlineMd(m[2])}</li>`);
      i++; continue;
    }

    // lista não ordenada
    if ((m = line.match(/^\s*[-*]\s+(.*)$/))) {
      if (listType !== "ul") { flushList(); listType = "ul"; }
      listBuf.push(`<li>${inlineMd(m[1])}</li>`);
      i++; continue;
    }

    // lista ordenada
    if ((m = line.match(/^\s*\d+\.\s+(.*)$/))) {
      if (listType !== "ol") { flushList(); listType = "ol"; }
      listBuf.push(`<li>${inlineMd(m[1])}</li>`);
      i++; continue;
    }

    // linha em branco
    if (line.trim() === "") {
      flushList();
      i++; continue;
    }

    // parágrafo (junta linhas seguintes até linha em branco ou bloco especial)
    flushList();
    const paraLines = [line];
    let j = i + 1;
    while (
      j < lines.length &&
      lines[j].trim() !== "" &&
      !/^(#{1,4})\s+/.test(lines[j]) &&
      !/^\s*[-*]\s+/.test(lines[j]) &&
      !/^\s*\d+\.\s+/.test(lines[j]) &&
      !/^```/.test(lines[j]) &&
      !/^>\s?/.test(lines[j]) &&
      !/^\s*\|.*\|\s*$/.test(lines[j])
    ) {
      paraLines.push(lines[j]);
      j++;
    }
    html += `<p>${inlineMd(paraLines.join(" "))}</p>`;
    i = j;
  }
  flushList();
  // fence ``` que nunca fecha: mostra o que veio depois como código, em vez de descartar o resto do documento
  if (inCode) html += `<pre><code>${escapeHtml(codeBuf.join("\n"))}</code></pre>`;
  return html;
}

if (typeof module !== "undefined") {
  module.exports = { markdownToHtml, slugTitulo, splitRow, resolveDocRef, stripFrontmatter, escapeHtml, safeUrl, agTexto, agDefinirTextos };
}
