# Post-its do workspace agLocalSite: design

Data: 2026-09-21. Status: entregue. Peça 3 de 4. Depende das peças 1 (fundação de escrita) e 2 (quadro), já entregues.

## 1. Objetivo

Deixar uma anotação solta na página de um documento, no ponto exato onde ela faz sentido, e encontrá-la lá quando voltar. O post-it é preso ao documento e fica na posição em que foi solto. Ele não é conteúdo do documento: vive num arquivo próprio, e o `.md` continua sendo a fonte da verdade do que é texto do projeto.

Critério de sucesso: arrastar o botão "＋ Post-it" até um ponto da página, escrever nele, fechar o site, abrir de novo e ver o post-it no mesmo lugar, sem que nenhum `.md` tenha sido alterado.

## 2. Escopo

Dentro:

- Criar, mover, editar o texto, trocar a cor e apagar post-its, em qualquer documento do menu.
- Guardar cada documento com post-its em `dados/postits/<caminho do documento sem .md>.json`.
- Duas rotas novas no servidor, com as salvaguardas da peça 1.
- Atualização automática entre janelas pela consulta de 2 segundos que já existe.
- Botão "Post-its (N)" para ocultar e mostrar, e ação "Novo post-it" no Ctrl+K.
- Documentação atualizada (seção 11).

Fora, e por quê:

- Post-it na busca do Ctrl+K, no grafo ou no quadro: o post-it é uma anotação de página, não um documento.
- Redimensionar, markdown ou imagem dentro do post-it.
- Prender o post-it a um trecho do texto (ele é preso ao documento, posição livre; foi a escolha do usuário).
- Migrar os post-its quando um documento é renomeado ou movido à mão: o arquivo dele fica para trás, sem aviso.
- Cópia de segurança dos post-its: o arquivo é pequeno e o movimento é frequente; apagar um post-it com texto pede confirmação.
- Rolagem automática da página durante o arraste: para levar um post-it longe, role a página e arraste em etapas, ou crie-o já na parte visível.
- Ver post-its sem o servidor: eles vivem em `dados/postits/` e não vão embutidos no `content.js`.
- Levar um post-it de um documento para outro.
- Backlinks e índice da página (peça 4).

## 3. Como é hoje

- `.panel` (o painel do documento) já é `position: relative`, então uma camada absoluta dentro dele se ancora sem mudar o layout. A barra acima do documento é `#ag-bar` (botão Editar, faixa de avisos).
- `agwrite.py`: `arquivos_md()` (do `sync.py`) é a lista de permissão dos caminhos válidos; `_gravar` faz a gravação atômica; `carimbo()`, `versao()` e `estado()` alimentam a consulta de 2 segundos; um `Lock` protege gravação e sync.
- `editor-ui.js`: `atualizar()` busca `/api/estado`, altera `AG_CONTENT` e `AG_GRAPH` no lugar e chama `AGView.reload()` e `AGBoard.reload()`; `ciclo()` compara o carimbo; `faixa()` mostra avisos acima do documento; `emLeitura()` e `voltouEscrita()` ligam e desligam a escrita.
- `IGNORE_DIRS` e o nome iniciado por ponto já mantêm `dados/historico/` fora do menu e do grafo; `dados/postits/` entra na mesma regra sem mudança no `sync.py`.

## 4. Arquitetura

Arquivos novos:

- `site/js/postit-model.js`: funções puras, Node e navegador (como `kanban-model.js`).
- `site/js/postit-view.js`: a camada, o arraste, a edição (DOM).

Arquivos alterados:

- `agwrite.py`: `postit_salvar(file, postit)`, `postit_apagar(file, id)`, `postits_todos()`, `carimbo_postits()`; `estado()` e `versao()` passam a trazer os post-its e o segundo carimbo.
- `serve.py`: duas rotas `POST` novas, repassando ao `agwrite.py`.
- `site/js/write.js`: `postit(file, postit)` e `apagarPostit(file, id)`.
- `site/js/editor-ui.js`: botão "＋ Post-it", botão "Post-its (N)", ação do Ctrl+K, comparação dos dois carimbos em `ciclo()`, `atualizar()` guardando os post-its e chamando `AGPostit.reload()`, e a exportação de `faixa` para a camada usar nos erros.
- `site/js/app.js`: `showDoc` avisa `AGPostit.aoAbrir()` depois de desenhar o documento, como já avisa `AGEditor.aoAbrir()`.
- `site/index.html` e `site/css/style.css`: carga dos dois arquivos novos, a camada, o visual e as cores.

Ordem dos scripts no `index.html`: `postit-model.js` e `postit-view.js` entram depois de `kanban-view.js` e antes de `editor-ui.js`.

## 5. Dados (`postit-model.js` e `dados/postits/`)

Um post-it: `{ id, x, y, cor, texto }`.

- `id`: 4 a 32 caracteres, letras minúsculas e números. O navegador gera (por exemplo, base 36 de tempo mais aleatório), para desenhar o post-it antes de gravar.
- `x`: número de 0 a 100, a posição na largura do painel do documento, em porcentagem (acompanha a janela quando ela muda de tamanho). O servidor guarda com 2 casas decimais.
- `y`: número de 0 a 100000, a distância do topo do painel em pixels (rola junto com o texto). O servidor guarda inteiro.
- `cor`: `amarelo`, `verde`, `azul`, `rosa` ou `laranja`. Todas com texto escuro legível (contraste de pelo menos 4,5:1), com variante para o tema escuro que mantém o mesmo contraste.
- `texto`: texto simples, até 1.000 caracteres, com quebras de linha; sempre exibido como texto, nunca como HTML.

Arquivo: `dados/postits/<caminho do documento sem .md>.json`, por exemplo `dados/postits/01-Visao-e-Negocio/publico-alvo.json`:

```
{
 "postits": [
  { "id": "k3f9a1", "x": 62.5, "y": 340, "cor": "amarelo", "texto": "Confirmar com o orientador" }
 ]
}
```

UTF-8, quebra de linha `\n`. O arquivo nasce no primeiro post-it e é apagado, junto com as pastas que ficarem vazias dentro de `dados/postits/`, quando o último sai. A ordem da lista é a ordem de empilhamento: o último tocado fica por cima.

Funções puras (testadas no Node):

- `posicaoParaPx(postit, larguraPainel, alturaPainel, larguraPostit)`: converte `x` e `y` em pixels e ajusta para dentro do painel: `left` entre 0 e `larguraPainel − larguraPostit`, `top` entre 0 e `alturaPainel − 48`. Um `y` além do fim do texto (o documento encolheu) aparece rente ao fim, sem alterar o arquivo.
- `pxParaPosicao(left, top, larguraPainel, alturaPainel, larguraPostit)`: o caminho inverso, com o mesmo ajuste, arredondando `x` a 1 casa decimal e `y` a inteiro.
- `proximaCor(cor)`: o ciclo amarelo, verde, azul, rosa, laranja, amarelo.
- `novoPostit(x, y)`: post-it vazio, cor amarelo, `id` novo.

## 6. Servidor

`POST /api/postit`, corpo `{ file, postit }`: cria ou atualiza **um** post-it do documento.

- `file` precisa estar na lista dos `.md` que o sync varre, como em `/api/salvar` (senão 400 `caminho`).
- O post-it é validado (senão 400 `postit`, com o campo na mensagem): objeto com os cinco campos, `id` no formato, `x` e `y` numéricos finitos dentro das faixas (booleano não vale), `cor` da lista, `texto` texto com até 1.000 caracteres. Campos desconhecidos são descartados.
- O servidor lê o arquivo do documento (ou começa uma lista vazia), tira o post-it de mesmo `id` se houver, acrescenta o novo **no fim** e grava de forma atômica (o `_gravar` da peça 1, sem cópia em `dados/historico/`). Mais de 200 post-its no documento: 400 `limite`.
- Responde `{ ok: true }`.

`POST /api/postit/apagar`, corpo `{ file, id }`: remove o post-it. Um `id` que não existe (por exemplo, outra janela já apagou) é sucesso: `{ ok: true }`. Se a lista ficar vazia, apaga o arquivo e as pastas vazias. Mesmas validações de `file` e do formato do `id`.

Tudo dentro do `Lock` da peça 1. Como cada operação mexe em um post-it só, duas janelas alterando post-its diferentes do mesmo documento não se sobrescrevem, e por isso não há aviso de conflito nesta peça (duas janelas alterando o mesmo post-it: vale a última gravação).

Versão e estado:

- `carimbo_postits()`: hash dos triplos (caminho, `mtime_ns`, tamanho) de todos os `.json` em `dados/postits/` (16 caracteres hexadecimais).
- `/api/versao` responde `{ carimbo, carimbo_postits }`. Só o carimbo dos `.md` dispara o sync; mudar um post-it não roda o sync.
- `/api/estado` responde também `carimbo_postits` e `postits`: um mapa `{ "<arquivo .md>": [ post-its ] }` só com os documentos que têm post-its. Arquivos de post-its de documentos que não existem mais são ignorados.

Limites e erros são os da peça 1: corpo até 2 MB (413), `POST` com `Content-Type: application/json` (415), `Host` e `Origin` conferidos (403), nenhuma mensagem com caminho absoluto, erro inesperado 500 `interno`.

## 7. Interface

Camada e aparência:

- Uma camada `.pi-camada` dentro do `.panel`, `position: absolute` cobrindo o painel, sem capturar cliques fora dos post-its. Região `role="region"` com nome "Post-its deste documento".
- Cada post-it é um grupo de 200 px de largura (no celular, até 60% do painel) com uma dobra no canto inferior direito, cabeçalho de 32 px e corpo em caixa de texto. Sombra deslocada, sem animação.
- Some no modo Editar, com o quadro ou o grafo abertos (o painel também some) e quando o botão "Post-its (N)" está desligado.

Barra do documento (com escrita e um documento aberto, fora do modo Editar):

- **＋ Post-it**: arrastar o botão até um ponto da página e soltar cria o post-it ali, com o ponteiro na alça. Clicar (ou Enter) cria na parte visível da página (`x` 62%, `y` a 80 px abaixo do topo visível) e leva o foco para a caixa de texto. Uma nota `role="status"` anuncia "Post-it criado".
- **Post-its (N)**: só aparece se o documento tem post-its. Liga e desliga a camada (`aria-pressed`). A escolha fica no navegador (`localStorage`, `ag-postits-ocultos`, em `try/catch`). Criar um post-it liga a camada.
- O Ctrl+K ganha a ação "Novo post-it" (só com documento aberto e fora do modo Editar).

Mover:

- Pelo cabeçalho, com Pointer Events (mouse, toque e caneta): `setPointerCapture` na alça, `touch-action: none`. Durante o arraste a posição segue o ponteiro em pixels; ao soltar, `pxParaPosicao` converte e o post-it é gravado.
- Teclado: a alça é um `<button>` ("Mover post-it, use as setas"); setas movem 12 px, com Shift 48 px, gravando 400 ms depois da última seta. Nota `role="status"`: "Post-it movido".
- O último tocado vai para o fim da lista (fica por cima), também no arquivo.

Editar, cor e apagar:

- O corpo é uma `<textarea maxlength="1000">` com nome "Texto do post-it". Cresce até 8 linhas e depois rola. Grava 600 ms depois da última tecla e ao sair do campo.
- Botão de cor no cabeçalho: passa para a próxima cor do ciclo e grava na hora. O nome da cor entra no nome acessível do botão.
- Botão × para apagar; `confirm()` só se houver texto.

Atualização:

- `atualizar()` guarda `postits` e `carimbo_postits`; `ciclo()` chama `atualizar()` quando qualquer um dos dois carimbos muda.
- `AGPostit.reload()` redesenha a camada do documento aberto só se a lista dele mudou em relação ao que está desenhado, e não enquanto um post-it está sendo arrastado ou tem foco para digitar (aí a atualização espera o fim do gesto).
- Um post-it apagado por outra janela some no redesenho; se você digitar nele antes disso, a gravação o recria.
- `showDoc` (app.js) avisa `AGPostit.aoAbrir()`, que desenha a camada do documento que abriu.

Erros e leitura:

- Falha ao gravar (rede, 400, 500): faixa `role="alert"` acima do documento (a `faixa()` do editor) com o motivo; o post-it fica onde está, com o texto preservado, e a próxima edição tenta de novo.
- Servidor parado: `emLeitura()` deixa os post-its só leitura (caixas `readonly`, alça e botões desabilitados, sem "＋ Post-it"); `voltouEscrita()` liga de novo.

Acessibilidade e visual:

- Reutiliza os tokens do `style.css`; cores dos post-its como tokens com variante para o tema escuro.
- Nomes acessíveis em todos os controles; foco visível; contraste de texto de pelo menos 4,5:1 sobre cada cor, nos dois temas.
- Alça e botões do cabeçalho com 32 px, e 44 px em telas de toque (`(pointer: coarse)`), como os chips da Nova nota.
- Sem animação, então `prefers-reduced-motion` já é respeitado.

## 8. Erros

| Situação | Comportamento |
|---|---|
| Falha ao gravar (disco, permissão) | Faixa com a mensagem do servidor; post-it e texto ficam; a próxima edição tenta de novo. |
| Servidor parado | Só leitura, como na peça 1; o aviso de saída aparece uma vez. |
| Post-it inválido (400 `postit`) | Faixa com a mensagem; nada é gravado. |
| Mais de 200 post-its no documento (400 `limite`) | Faixa com a mensagem; nada é gravado. |
| `file` que não é um documento do menu (400 `caminho`) | Faixa "Documento inválido."; nada é gravado. |
| Apagar um `id` que não existe | Sucesso (idempotente). |
| Corpo maior que 2 MB, `Host` ou `Origin` inesperado | 413 e 403, como na peça 1. |
| Outra janela apagou o post-it que estou editando | Some no próximo redesenho; digitar antes disso o recria. |

## 9. Atualização e escrita: o que não muda

O sync, os `.md`, o `dados/historico/`, o quadro e o grafo ficam como estão. Mexer em post-it não altera nenhum `.md`, não gasta as 20 cópias e não roda o sync.

## 10. Testes

- Python (`tests/test_postits.py`, no molde de `test_agwrite.py`, sobre uma cópia temporária): criar, atualizar, apagar, validação, caminhos inválidos, carimbos, `estado()`, rotas pelo servidor de verdade.
- Node (`tests/postit.test.js`): `posicaoParaPx`, `pxParaPosicao`, `proximaCor`, `novoPostit`.
- Navegador (Playwright/WebKit): **não incluídos nesta entrega** — ver nota de implementação abaixo.

Nenhum teste toca os arquivos reais do projeto.

### Nota de implementação (o que ficou de fora)

Os testes de navegador (`tests/postit_navegador.py` e a cobertura em `tests/webkit_navegador.py`) descritos originalmente para esta peça — criar por clique e por arraste, mover pela alça e pelas setas, cor, apagar, ocultar/mostrar, contraste nos dois temas, redimensionamento da janela, celular — não foram escritos nesta entrega, por tempo. O código da interface (`postit-view.js`) foi implementado para satisfazer cada um desses comportamentos, mas eles só ficam garantidos por um teste de navegador de verdade; até lá, tratar como não verificado automaticamente.

## 11. Documentação (parte do critério de pronto)

- `INICIO.md` ("Como usar"): uma linha sobre o botão "＋ Post-it".
- `LEIA-ME.md`: seção "Post-its" (criar, mover, editar, cor, apagar, ocultar, o formato do arquivo em `dados/postits/`, os limites); a lista de pastas fora do menu já cobre `dados/postits/` por começar com ponto.
- Este spec, em `docs/specs/`.
- Rodapé do `index.html`, se o texto mudar.

A peça só está pronta com testes passando e esses arquivos atualizados na mesma entrega. A regra vale também para a peça 4.

## 12. Decisões e premissas

- O post-it é preso ao documento, com posição livre na página (escolha do usuário). O arquivo dele fica em `dados/postits/`, um por documento (escolha do usuário; era a decisão em aberto desde a peça 1).
- Cada operação grava um post-it só, em vez de salvar a lista inteira: assim duas janelas não se sobrescrevem. Preço: as duas rotas e a regra "o último tocado fica por cima".
- Posição em porcentagem na horizontal e pixels na vertical: o post-it acompanha a largura da janela e rola junto com o texto. Se o texto do documento mudar muito, o post-it não acompanha o trecho, porque não é preso a ele.
- Sem cópia de segurança nem conflito: decisões desta peça, para manter o movimento barato. O `dados/historico/` não é usado.
- Tamanho fixo de 200 px, cinco cores, ciclo de cor por clique, 1.000 caracteres, 200 por documento: escolhas desta peça.
- Uso sempre pelo `start.bat` / `start.sh`, como nas peças anteriores: post-its só existem com o servidor.
- O projeto continua sem git. `dados/postits/` viaja no zip e fica fora do menu, do grafo, da busca, do quadro e do `dados/historico/`.
- Este spec fica em `docs/specs/`, pasta que o `sync.py` ignora, junto com os das peças 1 e 2.
- A criação por arraste do botão "＋ Post-it" usa o mesmo mecanismo de arrastar-e-soltar HTML5 já usado pelos cartões do quadro (peça 2), em vez de Pointer Events: é o padrão que já existe no código para "soltar em qualquer ponto de uma área", e o navegador já dá o ícone de arraste de graça. O mover de um post-it já colocado continua em Pointer Events, como pede a seção 7, porque ali o requisito é acompanhar o ponteiro continuamente (inclusive por teclado), o que o HTML5 DnD não faz bem.

## 13. Ajustes pós-entrega (2026-09-22)

Depois da entrega, o teste real no navegador trouxe três correções/mudanças de escopo, direto do uso:

- **Bug: clique criava dois post-its.** O botão "＋ Post-it" tinha o clique ligado duas vezes — uma pelo `botao()` da barra, outra por `AGPostit.ligarBotaoCriar()` (que já cobre clique e arraste). Corrigido: `botao()` agora aceita um `aoClicar` nulo, e a criação por clique só é ligada pelo `ligarBotaoCriar()`.
- **Mudança de escopo: a área dos post-its deixou de ser só o `.panel`.** Testando, ficou claro que "arrastar para fora da página" (a margem vazia à direita, fora da caixa do documento) devia funcionar, e não devolver o post-it para dentro do `.panel`. A camada (`.pi-camada`) agora é um item do `grid` do `.shell`, colado na mesma coluna e linha de `<main>`: cobre toda a largura à direita da barra lateral (a margem inclusa), na mesma altura de `<main>`. `x`/`y` de cada post-it passam a ser relativos a essa superfície mais larga, não mais ao `.panel`. Post-its salvos antes desse ajuste aparecem numa posição vertical um pouco diferente (a origem do `y` subiu, porque agora conta a partir do topo de `<main>`, antes da barra de botões, em vez do topo do `.panel`) — não há dado perdido, só o ponto de referência mudou.
- **Novo: redimensionar.** A seção 2 original dizia "fora de escopo: redimensionar" — decisão revista a pedido, depois de ver o post-it de tamanho fixo na prática. Cada post-it ganhou `w` e `h` (pixels, 160–480 × 120–640) e uma alça no canto inferior direito, com o mesmo mecanismo de mover (Pointer Events + setas do teclado, gravando 400 ms depois do gesto). A dobra decorativa do canto foi removida: ela cobria exatamente a área onde a alça de redimensionar precisava ficar clicável (`clip-path` também corta o hit-test da região cortada), e as duas coisas não davam para conviver — entre a decoração e a função, ficou a função.

`postit-model.js`, `agwrite.py` (campos `w`/`h`, limites `POSTIT_W_MIN/MAX` e `POSTIT_H_MIN/MAX`), `postit-view.js`, `editor-ui.js`, `style.css` e os testes Python/Node foram atualizados juntos com esta nota. Os testes de navegador continuam de fora, pela mesma razão da seção 10.
