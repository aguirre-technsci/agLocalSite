// Regras dos post-its: funções puras (rodam no navegador e no Node). A tela está em postit-view.js.
//
// Um post-it: { id, x, y, w, h, cor, texto }. x é a posição horizontal em % da largura da superfície
// (acompanha a janela); y é a distância do topo em pixels (rola junto com o texto). w e h (largura e
// altura, em pixels) vêm do redimensionar. Ver docs/specs para o formato do arquivo em .postits/.

const AGPostitModel = (function () {
  const CORES = ["amarelo", "verde", "azul", "rosa", "laranja"];
  const LARGURA_PADRAO = 200, ALTURA_PADRAO = 160;
  const LARGURA_MIN = 160, LARGURA_MAX = 480;
  const ALTURA_MIN = 120, ALTURA_MAX = 640;

  const limitar = (v, min, max) => Math.min(Math.max(v, min), max);

  // Posição salva (x %, y px) -> pixels de tela, ajustados para o post-it (com seu tamanho) caber na
  // superfície. Um y além do fim (o documento encolheu) aparece rente ao fim, sem alterar o valor salvo.
  function posicaoParaPx(postit, larguraSuperficie, alturaSuperficie, larguraPostit, alturaPostit) {
    const maxLeft = Math.max(0, larguraSuperficie - larguraPostit);
    const maxTop = Math.max(0, alturaSuperficie - alturaPostit);
    return {
      left: limitar((postit.x / 100) * larguraSuperficie, 0, maxLeft),
      top: limitar(postit.y, 0, maxTop),
    };
  }

  // Caminho inverso: pixels de tela -> posição a salvar (x arredondado a 1 casa, y a inteiro).
  function pxParaPosicao(left, top, larguraSuperficie, alturaSuperficie, larguraPostit, alturaPostit) {
    const maxLeft = Math.max(0, larguraSuperficie - larguraPostit);
    const maxTop = Math.max(0, alturaSuperficie - alturaPostit);
    const l = limitar(left, 0, maxLeft);
    const t = limitar(top, 0, maxTop);
    const x = larguraSuperficie > 0 ? (l / larguraSuperficie) * 100 : 0;
    return { x: Math.round(x * 10) / 10, y: Math.round(t) };
  }

  // Tamanho pedido (redimensionar) -> tamanho válido, dentro dos limites.
  function tamanhoValido(w, h) {
    return { w: Math.round(limitar(w, LARGURA_MIN, LARGURA_MAX)), h: Math.round(limitar(h, ALTURA_MIN, ALTURA_MAX)) };
  }

  // O ciclo amarelo, verde, azul, rosa, laranja, amarelo. Cor desconhecida volta ao início.
  function proximaCor(cor) {
    const i = CORES.indexOf(cor);
    return CORES[(i + 1) % CORES.length];
  }

  // Base 36 de tempo + aleatório: 4 a 32 caracteres, letras minúsculas e números.
  function idNovo() {
    const bruto = (Date.now().toString(36) + Math.random().toString(36).slice(2)).replace(/[^a-z0-9]/g, "");
    return (bruto + "0000").slice(0, 20);
  }

  // Post-it vazio, tamanho e cor padrão, pronto para desenhar antes de gravar.
  function novoPostit(x, y) {
    return { id: idNovo(), x, y, w: LARGURA_PADRAO, h: ALTURA_PADRAO, cor: CORES[0], texto: "" };
  }

  return {
    CORES, LARGURA_PADRAO, ALTURA_PADRAO, LARGURA_MIN, LARGURA_MAX, ALTURA_MIN, ALTURA_MAX,
    posicaoParaPx, pxParaPosicao, tamanhoValido, proximaCor, novoPostit,
  };
})();

if (typeof module !== "undefined") module.exports = AGPostitModel;
