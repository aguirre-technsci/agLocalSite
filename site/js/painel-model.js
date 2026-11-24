// Modelo do painel de configurações: só lógica pura (sem DOM e sem rede), para poder ser testada em Node.
// O que vai para o servidor é sempre um envio PARCIAL: só as chaves que mudaram, no contrato de docs/specs/2026-11-21-painel-de-configuracoes-design.md
// (null remove a chave e volta ao padrão; textos e tema vão só com a subchave alterada; listas e mapas vão inteiros).
// O servidor valida tudo de novo: as checagens daqui são só para mostrar o erro ao lado do campo antes de enviar.

const PAINEL_TEXTOS_SIMPLES = ["titulo", "subtitulo", "etiqueta", "titulo_aba"];
const PAINEL_LIMITES_PADRAO = { texto: 120, rodape: 2000, nome: 100 };   // os mesmos de sync.LIMITES; na prática vêm de GET /api/config

function painelLimpo(v) {   // texto em branco ou ausente equivale a "padrão" (null)
  if (v === undefined || v === null) return null;
  if (typeof v === "string") { const t = v.trim(); return t === "" ? null : t; }
  return v;
}

function painelCanon(v) {   // JSON estável: mapas comparam sem depender da ordem das chaves; listas mantêm a ordem
  if (Array.isArray(v)) return v.map(painelCanon);
  if (v && typeof v === "object") return Object.keys(v).sort().reduce((o, k) => { o[k] = painelCanon(v[k]); return o; }, {});
  return v;
}

function painelIgual(a, b) {
  return JSON.stringify(painelCanon(a === undefined ? null : a)) === JSON.stringify(painelCanon(b === undefined ? null : b));
}

function painelVazio(v) {
  return v === undefined || v === null || (Array.isArray(v) && v.length === 0) || (typeof v === "object" && !Array.isArray(v) && Object.keys(v).length === 0);
}

// Valor de uma subchave de textos ou tema. No rodapé, "" é uma escolha (ocultar) e não pode virar null.
function painelSub(chave, sub, v) {
  if (chave === "textos" && sub === "rodape") return v === undefined || v === null ? null : String(v);
  return painelLimpo(v);
}

function montarEnvio(original, atual) {
  const o = original || {}, a = atual || {}, envio = {};
  for (const k of PAINEL_TEXTOS_SIMPLES) {
    const vo = painelLimpo(o[k]), va = painelLimpo(a[k]);
    if (vo !== va) envio[k] = va;
  }
  for (const k of ["textos", "tema"]) {
    const so = o[k] || {}, sa = a[k] || {}, sub = {};
    for (const s of new Set([...Object.keys(so), ...Object.keys(sa)])) {
      const vo = painelSub(k, s, so[s]), va = painelSub(k, s, sa[s]);
      if (vo !== va) sub[s] = va;
    }
    if (Object.keys(sub).length) envio[k] = sub;
  }
  for (const k of ["ignorar", "rotulos", "home_prioridade"]) {
    const vo = o[k], va = a[k];
    const vazioEhPadrao = k !== "home_prioridade";   // ignorar e rotulos vazios = padrão; home_prioridade [] é "nenhum arquivo primeiro"
    if (painelIgual(vo, va) || (vazioEhPadrao && painelVazio(vo) && painelVazio(va))) continue;
    envio[k] = vazioEhPadrao && painelVazio(va) ? null : (va === undefined ? null : va);
  }
  return envio;
}

function envioPadroes(chavesEditaveis) {
  return (chavesEditaveis || []).reduce((o, k) => { o[k] = null; return o; }, {});
}

function rodapeEstado(textos) {
  if (!textos || textos.rodape === undefined || textos.rodape === null) return "padrao";
  return textos.rodape === "" ? "ocultar" : "personalizado";
}

function rodapeValor(estado, texto) {
  if (estado === "ocultar") return "";
  if (estado === "personalizado") return painelLimpo(texto);   // sem texto volta ao padrão, em vez de ocultar por engano
  return null;
}

// Mensagem em português para o campo, ou null se está tudo certo. chave: titulo, subtitulo, etiqueta, titulo_aba, textos.<chave>,
// rodape, rotulo (rótulo de uma pasta), ignorar ou home_prioridade (um item por vez).
function validarCampo(chave, valor, limites) {
  const lim = Object.assign({}, PAINEL_LIMITES_PADRAO, limites || {});
  if (typeof valor !== "string") return null;
  const v = valor.trim();
  const maximo = (n) => (v.length > n ? `Use no máximo ${n} caracteres.` : null);
  if (PAINEL_TEXTOS_SIMPLES.includes(chave) || chave === "rotulo" || (typeof chave === "string" && chave.startsWith("textos.") && chave !== "textos.rodape")) return maximo(lim.texto);
  if (chave === "rodape" || chave === "textos.rodape") return maximo(lim.rodape);
  if (chave === "ignorar" || chave === "home_prioridade") {
    if (v === "") return "Escreva um nome.";
    if (v.length > lim.nome) return `Use no máximo ${lim.nome} caracteres.`;
    if (v.includes("/") || v.includes("\\")) return 'Use só o nome, sem "/" nem "\\".';
    if (chave === "home_prioridade" && v.toLowerCase().endsWith(".md")) return 'Escreva o nome sem ".md".';
  }
  return null;
}

function moverItem(lista, indice, delta) {
  const copia = lista.slice();
  const destino = indice + delta;
  if (indice < 0 || indice >= copia.length || destino < 0 || destino >= copia.length || delta === 0) return copia;
  const [item] = copia.splice(indice, 1);
  copia.splice(destino, 0, item);
  return copia;
}

const AGPainelModel = { montarEnvio, envioPadroes, rodapeEstado, rodapeValor, validarCampo, moverItem };

if (typeof module !== "undefined" && module.exports) module.exports = AGPainelModel;
