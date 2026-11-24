# Quadro Kanban do workspace agLocalSite: design

Data: 2026-09-20. Status: implementado. Ajustes durante a implementação vêm marcados com "(implementação)"; mudanças pedidas depois da entrega, com "(revisão 1)". Peça 2 de 4. Depende da peça 1 (fundação de escrita), já entregue.

## 1. Objetivo

Ver de uma vez o que está pendente, em andamento e feito, e mover uma coisa de coluna com um gesto, sem abrir arquivo. O `.md` continua sendo a fonte da verdade: o quadro não guarda nada fora dele.

Critério de sucesso: abrir o quadro, mover uma nota de "Ideia" para "Fazendo" e marcar um item de checklist como feito, tudo sem sair do site, e ver o `.md` certo alterado no disco (só a linha do `status:` ou só a linha da caixa).

## 2. Escopo

Dentro:

- Botão "Quadro" na barra lateral e a tela do quadro (`kanban-view.js`).
- Regras dos dados, em funções puras testáveis (`kanban-model.js`).
- Dois tipos de cartão: notas com `status:` no frontmatter e itens de checklist (`- [ ]` / `- [x]`) de qualquer documento.
- Mover cartão por arrastar (mouse) e por seletor "Mover para…" (teclado e toque).
- Campo opcional "Status" no painel "Nova nota" e o parâmetro `status` em `/api/nova`.
- Ação "Abrir o quadro" na barra Ctrl+K.
- Função geral `alterar(arquivo, transformação)` no `editor-ui.js`, que o quadro e o checklist compartilham.
- Documentação atualizada (seção 10).

Fora, e por quê:

- Ordem manual dos cartões dentro da coluna: exigiria guardar posição em algum lugar. É o mesmo problema em aberto do mural da peça 3.
- Filtro do quadro por tag ou pasta.
- Criar cartão direto pelo quadro.
- Botão para tirar uma nota do quadro (hoje: apagar a linha `status:` pelo Editar).
- Arrastar no toque: o arrastar do navegador não dispara em telas de toque. O seletor cobre o celular.
- Mover item de checklist para uma coluna personalizada: o `.md` só guarda `[ ]` e `[x]`.
- Renomear ou apagar coluna (renomear é trocar o `status:` nas notas).
- Backlinks e índice da página (peça 4) e o mural (peça 3). (implementação) O menu recolhível do celular, que era da peça 4, entrou aqui: sem ele o quadro ficava abaixo de um menu de mais de 800 px.

## 3. Como é hoje

- Peça 1 entregue: `serve.py` com `/api/ping`, `/api/versao`, `/api/estado`, `/api/salvar`, `/api/nova`; `agwrite.py`; `write.js` (`alternarCaixa`, `frontmatter`, `montarNota`, cliente da API); `editor-ui.js` (Ctrl+K, Nova nota, Editar, checklists, consulta a cada 2 s).
- No `editor-ui.js`, `atualizar()` busca `/api/estado`, altera `AG_CONTENT` e `AG_GRAPH` no lugar e chama `buildTree()` e `AGView.reload()`. `gravarCaixa` grava uma caixa por vez numa fila.
- `markdown.js` marca cada caixa com `data-linha` (índice da linha no arquivo original, frontmatter contado) e ignora linhas dentro de blocos que começam com três crases. Só exporta `markdownToHtml` e `resolveDocRef` para o Node.
- `AG_GRAPH.docs[i]` traz `id`, `title`, `file` e `tags.curated`.
- O leitor de frontmatter do projeto (`graphdata.py`) aceita qualquer linha `chave: valor`, então `status:` convive com `tags:` sem alterar as tags (conferido com `tags` inline, em lista e com CRLF).
- Nenhum `.md` atual tem `status:` no frontmatter. O quadro nasce com os itens de checklist em A fazer e Feito.

## 4. Arquitetura

O quadro é uma tela só no navegador. Os textos de todos os documentos já vêm em `AG_CONTENT` (campo `fallback`), então o quadro os lê de lá e grava por `/api/salvar`. Sem `sync.py` novo, sem arquivo de dados novo, sem rota nova. Como só lê dados que já estão na página, o quadro também aparece sem servidor, só para leitura.

Arquivos novos:

- `site/js/kanban-model.js`: funções puras, Node e navegador (como `graph-model.js`).
- `site/js/kanban-view.js`: a tela (DOM), `AGBoard.open()`, `close()`, `reload()`.

Arquivos alterados:

- `site/js/write.js`: `frontmatter(tags, status)` e `montarNota(titulo, tags, corpo, status)`.
- `agwrite.py`: `frontmatter(tags, status)`, `montar_nota(...)` e `nova(pasta, titulo, tags, corpo, status="")`.
- `serve.py`: repassa `status` de `/api/nova`. Nenhuma outra mudança.
- `site/js/editor-ui.js`: função `alterar` (fila geral), `temEscrita()`, campo Status na Nova nota, ação "Abrir o quadro", chamada a `AGBoard.reload()` em `atualizar()`, `emLeitura()` e `voltouEscrita()`.
- `site/js/markdown.js`: exporta também `stripFrontmatter` para o Node.
- `site/js/app.js`: `selectItem` fecha o quadro, como já fecha o grafo.
- `site/index.html` e `site/css/style.css`: botão Quadro, carga dos dois arquivos novos, visual do quadro, barra lateral em duas linhas.

Ordem dos scripts no `index.html`: `kanban-model.js` e `kanban-view.js` entram depois de `write.js` e antes de `editor-ui.js` (que fica antes de `app.js`, como hoje).

## 5. Regras dos dados (`kanban-model.js`)

Chave de coluna: `chaveColuna(s)` = texto sem acento, em minúsculas, com qualquer sequência de caracteres que não sejam letra ou número trocada por um espaço, sem espaços nas pontas. `A fazer`, `a-fazer` e `À FAZER` dão a mesma chave (`a fazer`).

Leitura e troca de status:

- `lerStatus(texto)`: usa `stripFrontmatter` para achar o bloco de frontmatter e devolve o valor da primeira linha `status:` dentro dele (chave sem diferenciar caixa, aspas simples ou duplas nas pontas removidas). Sem frontmatter, sem a linha ou com valor vazio: `null`. Um `status:` no corpo do documento não conta.
- `alterarStatus(texto, valor)`: troca só essa linha, dentro do frontmatter, por `status: valor`. O resto do arquivo fica igual. Sem linha de status: `null`.

Cartões, em ordem de documento no menu e, dentro do documento, nota primeiro e depois os itens na ordem das linhas:

- Nota: documento com `lerStatus` não nulo. Campos: `chave` (`n:<arquivo>`), `tipo: "nota"`, `id`, `titulo`, `arquivo`, `pasta`, `tags` (as curadas, de `AG_GRAPH`), `coluna`.
- Item: cada linha `- [ ] texto` ou `- [x] texto` de qualquer documento, com o mesmo critério do `markdown.js` (linhas dentro de blocos de três crases não contam). Campos: `chave` (`i:<arquivo>:<linha>`), `tipo: "item"`, `arquivo`, `docId`, `docTitulo`, `linha` (a partir de 0, no arquivo inteiro), `texto`, `feito`. `[ ]` cai em A fazer e `[x]`/`[X]` em Feito. Um documento com `status:` gera o cartão da nota e os cartões dos seus itens.

Colunas de `montarQuadro(docs, tagsPorId)`:

- `A fazer` (chave `a fazer`) e `Feito` (chave `feito`) existem sempre, mesmo vazias, com esses rótulos fixos. (revisão 1) `Em progresso` (chave `em progresso`) também é fixa: a coluna intermediária do fluxo. `em-progresso` e `Em Progresso` são a mesma coluna.
- Cada outro status vira uma coluna. O rótulo é a primeira grafia encontrada, na ordem do menu.
- Ordem: A fazer primeiro, (revisão 1) Em progresso em seguida, Feito por último, as demais em ordem alfabética da chave, entre Em progresso e Feito.
- (implementação) `montarQuadro(docs, tagsPorId, extras)`: `extras` são rótulos de colunas personalizadas já vistas na sessão. Elas continuam na tela mesmo vazias, até a página ser recarregada; sem isso, quem move a última nota de "Ideia" para "Fazendo" perderia a coluna "Ideia" e não poderia devolver cartões a ela. A tela guarda essas colunas em memória (nada é gravado).
- Nota com status `a-fazer`, `em-progresso` ou `feito` cai nas colunas fixas; em A fazer e Feito ela fica misturada com os itens. Item de checklist continua só em A fazer ou Feito: o `.md` não guarda "em progresso" para uma caixa (só existe `[ ]` e `[x]`), então soltar um item em Em progresso é recusado como em qualquer coluna personalizada.

(revisão 1) A coluna Feito fica escondida e só aparece buscando. `filtrarQuadro(quadro, consulta)` devolve o que a tela mostra:

- Sem consulta (vazia ou só espaços): todas as colunas, menos Feito, e `feitosOcultos` com quantos cartões há nela.
- Com consulta: todas as colunas, Feito inclusive, só com os cartões que combinam. A consulta ignora acento e caixa, e todas as palavras precisam aparecer no título, nas tags, na pasta, no arquivo, no texto, no documento de origem ou no nome da coluna do cartão. Buscar `feito` mostra tudo o que está feito; buscar `a fazer` mostra tudo o que falta. As colunas sem resultado continuam, vazias.

Movimento:

- `destinoPermitido(cartao, chaveColuna)`: nota vai para qualquer coluna; item só para `a fazer` ou `feito`. Mesma coluna: não é movimento.
- `moverCartao(cartao, coluna, texto)` devolve o texto novo ou `null` (o arquivo mudou):
  - nota: `alterarStatus(texto, coluna.rotulo)`; `null` se a linha de status sumiu.
  - item: só se a linha `cartao.linha` ainda é um item de checklist com o mesmo `texto` e no estado oposto ao destino; alterna com `alternarCaixa`. Senão, `null`.
- Mover uma nota para uma coluna existente grava o rótulo dessa coluna (as notas convergem para a mesma grafia).

## 6. Servidor e Nova nota

`POST /api/nova` aceita o campo opcional `status`:

- Deve ser texto; espaços repetidos viram um só e as pontas são aparadas. Vazio: não escreve nada. Mais de 40 caracteres: 400 com `{ codigo: "status" }`. Tipo errado: 400 com `{ codigo: "corpo" }`.
- Frontmatter: `---`, depois `tags: [a, b]` se houver tags, depois `status: X` se houver status, depois `---`. Sem tags nem status, sem frontmatter. O `montarNota` do JS (prévia) e o `montar_nota` do Python produzem o mesmo arquivo, testados com os mesmos casos (`tests/casos_nota.json` ganha o campo `status`).
- Sem `status`, o resultado é idêntico ao da peça 1.

Painel Nova nota: campo de texto "Status (opcional)" entre as tags e o texto, com as colunas existentes como sugestão (`<datalist>`). Digitar um valor novo cria a coluna. A prévia mostra a linha `status:`.

## 7. Interface do quadro

Onde abre:

- Botão "▦ Quadro" na barra lateral, sempre visível (o quadro também lê sem servidor). A linha de botões passa a duas: "Grafo de tags" e "Quadro" na primeira; "+" (só com escrita) e "Escuro" na segunda.
- O quadro ocupa a área do documento e esconde o documento, a linha de estado, a barra Editar e o rodapé, como o grafo. Abrir o quadro fecha o grafo e o inverso. Abrir um documento fecha o quadro. Clicar no botão de novo fecha.
- Com escrita, o Ctrl+K ganha a ação "Abrir o quadro".

Layout:

- (revisão 1) Cabeçalho com "Quadro", a contagem (com busca vira "N encontrados"), o campo **Buscar** (`type="search"`, nome acessível "Buscar no quadro") e, sem busca, o aviso "N cartões feitos ocultos. Busque para ver." quando há cartões na coluna Feito. A busca é apagada toda vez que o quadro abre. Além disso, a linha de avisos e, sem escrita, "Somente leitura: abra pelo start para mover cartões".
- (revisão 1) A coluna Feito só é desenhada enquanto há busca. Durante um arraste que pode terminar nela, aparece como zona de soltura tracejada ("Solte aqui para concluir"), sem os cartões, e some quando o arraste acaba. O seletor "Mover para…" continua listando Feito. Quando o cartão movido some de vista (foi para a Feito escondida), o foco fica no próprio quadro e o aviso "Movido para Feito." anuncia o movimento.
- Colunas lado a lado. A rolagem horizontal fica dentro do quadro; a página não ganha barra horizontal. Cada coluna tem título, contagem e rolagem vertical própria. Coluna vazia mostra "Nenhum cartão" e continua recebendo cartões.
- Nota: título (link para o documento), até 3 tags e a pasta em fonte mono pequena, com o canto de prancheta do painel. Item: glifo ☐ ou ☑, o texto e, no rodapé, o documento de origem em mono (link).
- Reutiliza os tokens do `style.css`. Sem animação.

Mover:

- Mouse: cartão `draggable`; a coluna que aceita o cartão ganha borda tracejada ao passar por cima. Uma coluna que não aceita (item de checklist em coluna personalizada) não destaca e o aviso diz "Itens de checklist só ficam em A fazer ou Feito."
- Teclado e toque: cada cartão tem um `<select>` "Mover «título» para…" com todas as colunas. A coluna atual e, para itens, as colunas personalizadas ficam desabilitadas. O seletor aparece com o mouse em cima ou com foco e fica sempre visível em telas de toque (`(hover: none)`); continua acessível por Tab quando escondido.
- Só existe com escrita disponível; sem ela, os cartões são apenas links.
- Depois de gravar, o cartão esmaece durante a gravação; o quadro se redesenha com os dados novos e uma linha `role="status"` anuncia "Movido para Fazendo." O foco volta ao seletor do cartão movido.
- O redesenho preserva a rolagem horizontal do quadro e a vertical de cada coluna.

Acessibilidade:

- `role="region"` com nome "Quadro"; cada coluna é um grupo nomeado pelo seu título; cartões são itens de lista.
- Seletor, links e botões com no mínimo 44 px, foco visível, contraste de texto de pelo menos 4,5:1.
- Coluna que recebe o arrastar se destaca por borda tracejada, não só por cor.
- Avisos de erro com `role="alert"`.

## 8. Atualização automática e escrita

- `atualizar()` (peça 1) passa a chamar `AGBoard.reload()`. `emLeitura()` e `voltouEscrita()` também, para ligar e desligar arrastar e seletor.
- (implementação) Soltar um cartão só o move se o cartão vier no próprio arraste (`dataTransfer`) e o estado de arraste é limpo na soltura: o quadro se redesenha e o cartão sai da página antes de o navegador avisar o fim do arraste, e um estado antigo moveria o cartão errado na soltura seguinte.
- `alterar(arquivo, transformação)`: uma gravação por vez, numa fila. Lê o texto do documento em `AG_CONTENT` e o `mtime` conhecido, chama a transformação, e se ela devolve texto grava por `/api/salvar`; com sucesso, atualiza o `mtime` e roda `atualizar()`. Devolve `{ ok }` ou `{ motivo: "mudou" | "conflito" | "erro", mensagem }`. `gravarCaixa` passa a usar `alterar`.
- Cópia de segurança em `dados/historico/`, conflito por `mtime` e gravação atômica são os da peça 1, sem mudança.

## 9. Erros

| Situação | Comportamento |
|---|---|
| Arquivo mudou por fora (409, ou o cartão não bate mais com a linha) | Aviso "O arquivo mudou por fora. O cartão não foi movido."; o quadro se atualiza sozinho e o cartão volta ao lugar. |
| Falha ao gravar (disco, permissão, cópia) | Aviso com a mensagem do servidor; cartão no lugar. |
| Servidor parado | Vira só leitura como na peça 1; o aviso de saída aparece uma vez. (implementação) Também no cabeçalho do quadro, porque a barra de avisos do documento fica escondida com o quadro aberto. |
| Item solto em coluna personalizada | Aviso "Itens de checklist só ficam em A fazer ou Feito."; nada é gravado. |
| Nova nota com status inválido | 400; erro no campo Status (`role="alert"`). |
| (implementação) Título que vira nome reservado do Windows (`con`, `nul`, `com1`…) | 400 com `{ codigo: "titulo" }`; erro no campo Título; nada é criado. |
| (implementação) Arquivo aberto em outro programa (Windows: `PermissionError` na troca) | Aviso "aberto em outro programa ou protegido contra escrita"; o original fica intacto e o temporário é apagado. |

## 10. Testes

- Node (`tests/kanban.test.js`): `lerStatus` (com e sem frontmatter, CRLF, aspas, vazio, `status:` no corpo); `alterarStatus` (só essa linha muda, sem linha devolve `null`); `chaveColuna` (`A fazer`, `a-fazer`, `À FAZER`); `montarQuadro` (colunas fixas vazias, ordem, primeira grafia, `[ ]` em A fazer e `[x]` em Feito, nota e itens do mesmo documento, item em bloco de código ignorado, `linha` igual ao `data-linha` do `markdown.js`); `destinoPermitido`; `moverCartao` (nota, item nos dois sentidos, item cuja linha mudou ou cujo texto mudou devolve `null`). `write.test.js` ganha os casos de `frontmatter`/`montarNota` com status.
- Python (`tests/test_agwrite.py`): `nova` com e sem status, ordem `tags:` e `status:`, status só, status longo (400), status de tipo errado (400), casos compartilhados com o JS.
- Navegador (Playwright, `tests/kanban_navegador.py`, servidor temporário e cópia da pasta): colunas e cartões a partir de notas com status criadas na cópia; mover nota pelo seletor e por arrastar (o `status:` muda no disco, cópia em `dados/historico/`); mover item nos dois sentidos (a caixa muda no disco, só ela); soltar item em coluna personalizada não grava; arquivo alterado por fora redesenha o quadro; conflito devolve o cartão; `file://` mostra o quadro sem seletor nem arrastar; Nova nota com status novo cria a coluna; movimento só por teclado; o quadro não aumenta a rolagem horizontal da página.
- (revisão 1) Node: `filtrarQuadro` (sem consulta esconde Feito e conta os ocultos; com consulta filtra todas as colunas por título, tag, pasta, texto, documento de origem e nome da coluna; ignora acento; todas as palavras; sem resultado), a coluna fixa Em progresso e sua chave normalizada. Navegador: Feito escondida por padrão, aparece buscando e some ao apagar; item concluído sai de vista e o aviso o conta; zona de soltura no arraste; soltar item em Em progresso é recusado; nota para Em progresso grava `status: Em progresso`; busca por tag, pelo nome da coluna e sem resultado.
- (implementação) As ajudas comuns dos testes de navegador (cópia temporária, servidor em porta livre, conferências) foram para `tests/_navegador.py`. O arraste é testado de verdade, com o mouse, inclusive até uma coluna fora da tela (o quadro rola nas bordas durante o arraste). O `drag_and_drop` do Playwright não serve para isso porque rola no meio do arraste.
- (implementação) Cada linha da tabela de erros (seção 9) tem teste de navegador: falha ao gravar (resposta 500 simulada), cartão que não bate mais com a linha, conflito 409, item solto em coluna personalizada, servidor parado com o quadro aberto, status inválido e nome reservado do Windows.
- (implementação) `tests/celular_navegador.py` (390 px): menu recolhível, nenhum documento passa dos 390 px, quadro logo abaixo dos botões. `tests/webkit_navegador.py`: fumaça no WebKitGTK (escrita, Nova nota com status, Editar, checklist, quadro pelo seletor, largura em janela estreita).
- Os testes da peça 1 continuam passando.

Nenhum teste toca os arquivos reais do projeto.

## 11. Documentação (parte do critério de pronto)

- `INICIO.md` ("Como usar"): o botão Quadro, o que é um cartão, como mover, o campo `status:` e o campo Status da Nova nota.
- `LEIA-ME.md`: as regras do quadro (colunas, itens só em A fazer e Feito, ordem), o formato do `status:` no frontmatter, o que mudou na Nova nota, os limites (sem ordem manual, sem arrastar no toque, sem filtro, sem criar cartão pelo quadro).
- `TAGS-E-BUSCA.md`: o campo Status ao lado das tags na Nova nota.
- Rodapé do `index.html` e mensagem de partida do `serve.py`, se o texto mudar.

A peça só está pronta com testes passando e esses arquivos atualizados na mesma entrega.

## 12. Decisões e premissas

- (revisão 1) Escolhas ao acrescentar Em progresso e a Feito escondida: Em progresso é fixa como A fazer e Feito, mesmo vazia; itens de checklist não entram em Em progresso (exigiria uma marca nova no `.md`, como `- [~]`, que outros leitores de markdown mostram como texto puro); a busca inclui o nome da coluna, para `feito` mostrar os feitos; a zona de soltura durante o arraste evita que concluir um cartão dependa de buscar antes.
- Cartões são os dois tipos, misturados nas colunas A fazer e Feito (escolha do usuário). Colunas livres, definidas pelo `status:` das notas; itens de checklist só em A fazer e Feito (escolha do usuário).
- Nota sem `status:` fica fora do quadro. Para entrar: digitar o `status:` no Editar ou usar o campo Status da Nova nota.
- Colunas identificadas por chave normalizada (sem acento, caixa e hífen); rótulo é a primeira grafia encontrada. Rótulos de A fazer e Feito são fixos.
- Ordem das colunas (fixas nas pontas, o resto alfabético) e dos cartões (ordem do menu) são escolhas desta peça; a ordem manual fica para depois.
- (implementação) Rolagem automática própria do quadro durante o arraste: o navegador escolhe a lista de cartões da coluna sob o mouse (que rola na vertical) e deixa o quadro parado, então sem isso não se chega a uma coluna alta fora da tela.
- (implementação) O seletor "Mover para…" fica sobreposto ao rodapé do cartão no desktop (aparece com o mouse ou o foco) e em fluxo em telas de toque; o nome do documento de origem ganha reticências em vez de ficar cortado. A coluna tem `min-width: 0`, para um código longo não alargá-la.
- (implementação) Celular: `minmax(0, 1fr)` na grade da página (o `1fr` sozinho crescia até o conteúdo mais largo), tabelas rolam dentro delas e URLs soltas no texto quebram (`overflow-wrap`, mais `word-break: break-word` para o WebKit).
- (implementação) `serve.py` abre a porta antes do sync inicial: o `start.bat` abre o navegador sem esperar o servidor.
- (implementação) Depois de um conflito, o quadro se atualiza na hora e mostra o cartão onde o arquivo diz, em vez de esperar a consulta periódica.
- Limite de 40 caracteres no status é uma escolha desta peça, para o título da coluna caber.
- Uso sempre pelo `start.bat` / `start.sh`, como na peça 1: mover cartões depende do servidor. Só ler o quadro não depende.
- O projeto continua sem git: o histórico de versões é o `dados/historico/` da peça 1.
- Este spec fica em `docs/specs/`, pasta que o `sync.py` ignora (`IGNORE_DIRS`), para não entrar no menu. O desenho da peça 1 está em `2026-09-19-fundacao-de-escrita-design.md`, na mesma pasta.
