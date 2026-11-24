// Tema do site: paleta (data-palette) e modo claro/escuro (data-theme), aplicados no <head> antes da primeira pintura.
// Os dados vêm de tema-dados.js (GERADO pelo sync a partir do config.json); aqui fica só a lógica.
// Modo, em ordem: escolha pessoal de quem visita (botão Claro/Escuro, guardada em localStorage "ag-theme") > "tema.modo" do projeto
// (claro, escuro ou sistema) > claro. Paleta fora da lista cai em "padrao" (que é o :root do style.css, sem atributo).

// "dark" ou "light" se a pessoa já escolheu neste navegador; senão null. Armazenamento bloqueado ou ausente conta como sem escolha.
function lerPessoal(storage) {
  try {
    const v = storage && storage.getItem("ag-theme");
    return v === "dark" || v === "light" ? v : null;
  } catch (e) {
    return null;
  }
}

function resolverModo(pessoal, projeto, sistemaEscuro) {
  if (pessoal === "dark" || pessoal === "light") return pessoal;
  if (projeto === "escuro") return "dark";
  if (projeto === "sistema") return sistemaEscuro ? "dark" : "light";
  return "light";
}

function paletaValida(nome, lista) {
  return typeof nome === "string" && Array.isArray(lista) && lista.indexOf(nome) !== -1 ? nome : "padrao";
}

// opc: { paleta, modo, pessoal, sistemaEscuro, paletas }. raiz é o <html> (ou, nos testes, um objeto com dataset).
function aplicar(raiz, opc) {
  raiz.dataset.theme = resolverModo(opc.pessoal, opc.modo, opc.sistemaEscuro);
  const p = paletaValida(opc.paleta, opc.paletas);
  if (p === "padrao") delete raiz.dataset.palette;
  else raiz.dataset.palette = p;
}

const AGTema = { lerPessoal, resolverModo, paletaValida, aplicar };

if (typeof document !== "undefined" && document.documentElement) {
  const t = typeof AG_TEMA !== "undefined" ? AG_TEMA : {};   // sem tema-dados.js (nunca rodou o sync): só vale a escolha pessoal
  let sistemaEscuro = false;
  let storage = null;
  try { sistemaEscuro = !!(window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches); } catch (e) { /* sem matchMedia */ }
  try { storage = window.localStorage; } catch (e) { /* armazenamento bloqueado */ }
  aplicar(document.documentElement, { paleta: t.paleta, modo: t.modo, pessoal: lerPessoal(storage), sistemaEscuro, paletas: t.paletas });
}

if (typeof module !== "undefined" && module.exports) module.exports = AGTema;
