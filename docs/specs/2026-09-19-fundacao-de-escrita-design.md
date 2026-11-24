# Fundação de escrita do workspace agLocalSite: design

Data: 2026-09-19. Status: implementado. Peça 1 de 4 (ver "Escopo"). Onde o código saiu diferente do desenho original, o texto traz "(implementação)".

## 1. Objetivo

Antes desta peça o site só lia. Guardar ou mudar algo exigia criar o `.md` com frontmatter à mão, rodar `sync.py` e dar F5. Esta peça faz o site criar, editar e atualizar documentos sozinho, com o `.md` continuando a fonte da verdade. Quem preferir o fluxo antigo (editor de texto, `sync.py`, F5) segue podendo usá-lo.

Critério de sucesso: criar uma nota, editar um documento e marcar um item de checklist sem sair do site, sem `sync.py` e sem F5, e ver a mudança de um arquivo editado por fora aparecer na página em poucos segundos.

## 2. Escopo

Dentro:

- Servidor com escrita (`serve.py` mais um módulo novo, `agwrite.py`).
- Atualização automática do menu, das tags e do grafo.
- Barra Ctrl+K (buscar documento, "Nova nota", "Editar este documento").
- Painel "Nova nota".
- Modo "Editar" com prévia.
- Checklists `- [ ]` que gravam no arquivo.
- Ajuste de contraste dos links de citação (era 4,26:1 sobre o fundo do código, mínimo 4,5:1; ficou 4,88:1).
- Documentação atualizada (seção 10).

Fora, e por quê:

- Quadro Kanban (peça 2) e mural de post-its (peça 3): usam a rota de salvar desta peça. O mural tem uma decisão em aberto própria (onde guardar posição e cor dos post-its), a ser decidida no brainstorm da peça 3.
- Backlinks e índice da página (peça 4). (implementação) O menu recolhível do celular, que estava na peça 4, foi entregue junto com a peça 2.
- Criar pasta nova pelo site: continua feito à mão, como descrito no `LEIA-ME.md`.
- Apagar, mover ou renomear documento pelo site.
- Editar sem servidor: abrindo `index.html` por duplo-clique o site segue só de leitura.

## 3. Como era

- `serve.py` (11 linhas): `ThreadingHTTPServer` em `127.0.0.1` com `Cache-Control: no-store`.
- `sync.py`: `main()` montava os grupos, escrevia `site/js/content.js` (`const AG_CONTENT`) e, via `graphdata.build`, `site/js/graph-data.js` (`const AG_GRAPH`). O `id` de cada documento é o caminho sem extensão, em minúsculas, com `-`.
- `site/js/app.js`: montava o menu uma vez (`buildTree`), abria documentos por `#id` e lia o `.md` ao vivo com `fetch` (o texto embutido é o fallback).
- `site/js/graph-view.js`: lia `AG_GRAPH` e `AG_CONTENT` ao iniciar.
- `site/js/markdown.js`: desenhava as caixas de checklist com `disabled`.
- `start.sh` e `start.bat` rodam o sync e sobem o `serve.py`.

## 4. Arquitetura

Módulos novos:

- `agwrite.py` (raiz do projeto): regras de gravação, sem HTTP. Valida caminho, cria backup, grava de forma atômica, cria nota, calcula o carimbo de versão e roda o sync. Só usa a biblioteca padrão.
- `site/js/write.js`: funções puras e cliente da API. Roda no navegador e no Node, como `search.js`. Contém `slugTitulo`, `frontmatter`, `montarNota`, `alternarCaixa`, `filtrarPaleta` e as chamadas `fetch` às rotas.
- `site/js/editor-ui.js`: interface (barra Ctrl+K, painel Nova nota, modo Editar, ativação das checklists, consulta periódica).

Arquivos alterados:

- `serve.py`: continua o servidor estático e ganha as rotas `/api/*`, delegando tudo ao `agwrite.py`. Recusa toda requisição `/api/*` cujo `Host` não seja `localhost` ou `127.0.0.1` na porta em uso.
- `sync.py`: `main()` foi dividido em `montar_dados()` (devolve grupos e grafo) e `escrever_arquivos()`. A saída no terminal e os arquivos gerados ficam iguais. O `agwrite.py` chama as duas partes. (implementação) Ganhou também `pastas_topo()` e `arquivos_md()`, que dizem o que o sync varre e servem de lista de permissão para o `agwrite.py`.
- `site/js/app.js`: `buildTree` pode ser chamada de novo, preservando pastas abertas e documento ativo. Ganha os ganchos para a interface de escrita (`showDoc`, `repaintCurrent`, `currentDoc`).
- `site/js/graph-view.js`: novo método `AGView.reload()` que relê os dados.
- `site/js/markdown.js`: cada caixa de checklist sai com `data-linha="N"`, o índice da linha no arquivo original (contando as linhas do frontmatter removido).
- `site/index.html` e `site/css/style.css`: carregam os dois arquivos novos, estilos da interface e o verde dos links de citação mais escuro no tema claro.

Como o `site/js/content.js` e o `graph-data.js` declaram `const`, a página atualiza os dados alterando os objetos no lugar (`AG_CONTENT.splice(...)`, `AG_GRAPH.docs.splice(...)`), sem reatribuir.

## 5. API

Todas as respostas são JSON. Erros usam `{ "erro": "mensagem curta", "codigo": "..." }`. Nenhuma mensagem expõe caminho absoluto.

| Rota | Função |
|---|---|
| `GET /api/ping` | Diz que a escrita está disponível: `{ "escrita": true }`. |
| `GET /api/versao` | Carimbo atual. Se ele difere do último sincronizado, o servidor roda o sync antes de responder. |
| `GET /api/estado` | `{ carimbo, content, graph, mtimes }`: os mesmos dados dos dois arquivos gerados e o `mtime_ns` de cada `.md`. |
| `POST /api/salvar` | Corpo `{ file, texto, base_mtime }`. Sobrescreve um `.md` existente. |
| `POST /api/nova` | Corpo `{ pasta, titulo, tags, corpo }` (a peça 2 acrescentou `status`). Cria a nota. |

Carimbo: hash dos triplos (caminho, `mtime_ns`, tamanho) de todos os `.md` que o sync varre (16 caracteres hexadecimais).

(implementação) O `mtime_ns` viaja como texto em `mtimes`, em `base_mtime` e nas respostas: o valor passa de 2^53 e o JavaScript perderia dígitos.

`/api/salvar`:

- `file` precisa estar na lista dos `.md` que o sync varre, sem nenhuma parte do caminho iniciada por ponto. Isso cobre "existir, terminar em `.md`, ficar dentro da raiz e fora de `site/`, `tests/`, `docs/` e pastas ocultas". Qualquer outro valor (com `..`, absoluto, de tipo errado): 400 com `{ codigo: "caminho" }`.
- Se o `mtime_ns` atual difere de `base_mtime`, responde 409 com `{ codigo: "conflito", texto, mtime }` (o `texto` já vem com `\n`) e não grava.
- Antes de gravar, copia o arquivo atual para `dados/historico/<caminho sem .md>/<AAAA-MM-DD_HHMMSS_ffffff>.md` e mantém as 20 cópias mais recentes por arquivo. (implementação) Os microssegundos no nome evitam que duas gravações no mesmo segundo se sobrescrevam. Se a cópia falhar, não grava (500 `copia`).
- Grava em arquivo temporário na mesma pasta e troca com `os.replace`, mantendo as permissões do original. Se o arquivo original usava quebra de linha CRLF, o texto gravado usa CRLF. (implementação) `PermissionError` na troca, o que acontece no Windows com arquivo aberto em outro programa, responde 500 `gravar` com "aberto em outro programa ou protegido contra escrita", e o temporário é apagado.
- Roda o sync e responde `{ ok, mtime }`.

`/api/nova`:

- `pasta` é uma pasta existente que o sync varre (vazio significa a raiz, o grupo Home). Pasta inexistente, oculta ou ignorada: 400 `pasta`.
- O nome do arquivo sai de `titulo`: minúsculas, sem acento, `-` entre palavras, até 80 caracteres, mais `.md`. Se já existe, responde 409 com `{ codigo: "existe" }`. Título sem letra nem número: 400 `titulo`. (implementação) Também 400 `titulo` quando o nome vira `con`, `prn`, `aux`, `nul`, `com1`..`com9` ou `lpt1`..`lpt9`, que o Windows não aceita como arquivo.
- Tags são normalizadas pela mesma regra de `normalize_tag` (`graphdata.py`) e `normTag` (`search.js`).
- Conteúdo gravado: frontmatter `---\ntags: [a, b]\n---` só se houver tags, depois `# titulo`, linha em branco e o corpo. Se o corpo já começa com uma linha `# `, ela é mantida e nada é acrescentado.
- Responde `{ ok, file, id, mtime }`, com o `id` idêntico ao que o sync gerou.

Limites: corpo da requisição até 2 MB (413), em UTF-8 e JSON de objeto (senão 400 `json`); sem `Content-Length`, 400 `corpo`. `POST` exige `Content-Type: application/json` (415) e um cabeçalho `Origin` igual ao endereço do servidor (403 `origem`; `Host` estranho: 403 `host`). Rota desconhecida: 404. Erro inesperado: 500 `interno`, com o detalhe só no terminal. Um único `Lock` protege gravação e sync, porque o servidor atende em threads.

(implementação) O `serve.py` abre a porta antes do sync inicial, porque o `start.bat` abre o navegador sem esperar o servidor. As consultas a `/api/versao`, que a página faz a cada 2 s, não aparecem no log do terminal.

## 6. Interface

Consultar `/api/ping` ao carregar. Sem resposta, nenhum controle de escrita aparece e o site é o de antes. Com resposta, a página busca `/api/estado` uma vez para pegar os `mtimes` e os dados em dia.

Barra Ctrl+K:

- Abre com Ctrl+K (Cmd+K no Mac) ou pelo botão "+" ao lado de "Grafo de tags".
- Filtra os documentos por título e caminho, sem acento nem caixa (a busca completa continua no grafo). Mostra também as ações "Nova nota" e "Editar este documento" (a peça 2 acrescentou "Abrir o quadro"). Setas navegam, Enter executa, Esc fecha.
- Padrão ARIA de combobox com lista; o foco volta ao elemento de origem ao fechar.

Nova nota (painel modal):

- Campos: pasta (existentes mais Home; vem marcada a pasta do documento aberto), título, tags e corpo (a peça 2 acrescentou o status opcional).
- Tags como chips. Digitar sugere as tags existentes com contagem; Enter cria uma tag nova.
- Se o título está vazio e o corpo colado começa com `# `, o título é preenchido a partir dessa linha.
- Prévia do frontmatter e do nome do arquivo, ao vivo, em texto pequeno. A prévia usa `slugTitulo` e `montarNota` do `write.js`; quem grava é sempre o servidor, e os dois lados são testados com os mesmos casos (`tests/casos_nota.json`), para a prévia nunca divergir do arquivo criado.
- Ctrl+Enter grava e abre a nota. Erro `existe` aparece no campo título.

Editar:

- Botão "Editar" acima do documento, visível só com escrita. Troca o texto por uma textarea com o arquivo cru (frontmatter incluído) e prévia ao lado a partir de 1100 px de largura, empilhada abaixo disso.
- Ctrl+S salva, Esc cancela. Com alteração pendente, sair (outro documento, fechar a aba) pergunta antes de descartar.

Checklists:

- Com escrita disponível, as caixas com `data-linha` ficam ativas (e ganham nome acessível, o texto do item). Clicar alterna `[ ]` e `[x]` só na linha indicada, usando `alternarCaixa(texto, linha)`, e salva por `/api/salvar`. Se a linha no arquivo não é mais um item de checklist, cancela e trata como conflito. (implementação) As gravações entram numa fila (`alterar` no `editor-ui.js`): cliques seguidos esperam a anterior e partem do texto já atualizado.

Conflito:

- Faixa no topo do documento: "o arquivo mudou por fora", com "ver a nova versão" e "sobrescrever com a minha" (reenvia com o `mtime` retornado). (implementação) "Ver a nova versão" pergunta antes de descartar o que foi digitado.

Acessibilidade e visual:

- Reutiliza os tokens do `style.css` (`--panel`, `--line`, fonte mono nos metadados).
- Painel com `role="dialog"`, `aria-modal`, foco preso e Esc. (implementação) O resto da página fica `inert` enquanto o painel está aberto.
- Mensagens de erro com `role="alert"`.
- Botões com no mínimo 44 px, foco visível, contraste de texto de pelo menos 4,5:1, animação só ao abrir o painel e desligada com `prefers-reduced-motion`.

## 7. Atualização automática

- Com a aba visível, a página consulta `/api/versao` a cada 2 segundos.
- Se o carimbo mudou, busca `/api/estado`, altera `AG_CONTENT` e `AG_GRAPH` no lugar, refaz o menu (mantendo pastas abertas e documento ativo) e chama `AGView.reload()` se o grafo estiver aberto.
- Se o documento aberto mudou (o `mtime` dele é diferente do que a página conhecia) e o usuário não o está editando, ele é redesenhado sem sair do lugar da rolagem. Se está editando, o texto da textarea não é tocado e a faixa de conflito aparece.
- Se `/api/versao` para de responder, a página volta ao modo leitura, avisa uma vez e continua tentando em silêncio. Quando o servidor volta, a escrita volta e o aviso some.

## 8. Erros

| Situação | Comportamento |
|---|---|
| Falha ao gravar (disco, permissão) | Erro visível; o texto digitado permanece. |
| Arquivo aberto em outro programa (Windows) | Aviso "aberto em outro programa ou protegido contra escrita"; o original fica intacto. |
| Conflito | Faixa com as duas saídas (seção 6). |
| Nome repetido em Nova nota | Erro no campo título. |
| Título que vira nome reservado do Windows | Erro no campo título; nada é criado. |
| Caminho inválido | 400, nada gravado. |
| Corpo maior que 2 MB | 413, nada gravado. |
| Host ou Origin inesperado | 403, nada gravado. |
| Falha no backup | Não grava. |

## 9. Testes

- Python (`unittest`, em `tests/test_agwrite.py`, no molde de `test_graphdata.py`): caminhos com `..`, absolutos, fora da raiz, não `.md` e em pastas ocultas ou ignoradas (inclui `docs/`); backup criado e poda em 20; conflito por `mtime`; frontmatter e slug com acento; título repetido; nomes reservados do Windows; gravação sem arquivo pela metade e com `PermissionError`; CRLF preservado; `Host`, `Origin` e `Content-Type` recusados por um servidor de verdade em porta livre; `id` retornado igual ao do sync.
- Node (`tests/write.test.js`): `slugTitulo`, `montarNota` (com e sem tags, com e sem `# ` no corpo), `alternarCaixa` (linha certa, linha que deixou de ser checklist, frontmatter deslocando o índice), `filtrarPaleta`. O teste de `markdown.js` ganha o `data-linha`.
- Navegador (Playwright, `tests/escrita_navegador.py`, no molde de `links_navegador.py`, com servidor temporário e cópia da pasta): criar nota e vê-la no menu sem F5; editar e salvar; marcar checklist e conferir o arquivo no disco; alterar um arquivo por fora e ver a página atualizar; forçar conflito; servidor parado volta ao modo leitura. As ajudas comuns estão em `tests/_navegador.py`. (implementação) Há também `tests/webkit_navegador.py`, que repete o essencial no WebKit.

Nenhum teste toca os arquivos reais do projeto.

## 10. Documentação (parte do critério de pronto)

- `INICIO.md` ("Bem-vindo ao workspace", na Home): a seção "Como editar" virou "Como usar" (Ctrl+K, Nova nota, Editar, checklists, atualização automática, o que fazer com o servidor parado). O caminho antigo (editar o `.md`, `sync.py`, F5) continua descrito como alternativa. O estado atual do checklist ganha uma linha dizendo que as caixas agora se marcam no site.
- `LEIA-ME.md`: fluxo novo, pasta `dados/historico/` (o que guarda, quando é criada, poda em 20), limites da versão (escrita só com `start`, sem criar pasta, sem apagar ou renomear).
- `TAGS-E-BUSCA.md`: a barra Ctrl+K e a escolha de tags na Nova nota.
- Rodapé do `index.html` e mensagem de partida do `serve.py` ("Escrita ativa em http://localhost:PORT/site/"): atualizados.
- `dados/historico/` fica de fora do menu e do grafo (o sync já ignora pastas iniciadas por ponto).

A peça só está pronta com testes passando e esses arquivos atualizados na mesma entrega. A regra vale também para as peças 2, 3 e 4.

## 11. Decisões e premissas

- Uso sempre pelo `start.bat` / `start.sh`, confirmado pelo usuário. Por isso a escrita depende do servidor.
- O `.md` é a fonte da verdade; `content.js` e `graph-data.js` continuam sendo gravados, então o site segue funcionando sem servidor (só leitura).
- O projeto não é repositório git. O histórico de versões dos arquivos fica em `dados/historico/`.
- Este spec fica em `docs/specs/`, pasta que o `sync.py` ignora (`IGNORE_DIRS`), para não entrar no menu. (Antes ficava fora do projeto, porque o `sync.py` transformaria uma pasta de topo qualquer em grupo do menu.)
- Escolhas desta peça, confirmadas na revisão: consulta a cada 2 segundos só com a aba visível; 20 versões por arquivo; sem criar pasta nem apagar, mover ou renomear pelo site; nome do arquivo em minúsculas, sem acento e com hífen (alguns arquivos de `99-etc/` usam outro padrão, com maiúsculas e underscore); corpo colado que começa com `# ` mantém o título.
