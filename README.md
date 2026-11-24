# agLocalSite

Visualizador e editor local de arquivos `.md`. Você aponta para uma pasta, ele monta um site navegável com menu, busca, grafo 3D de tags, Quadro Kanban e post-its, e grava as edições direto nos seus `.md`.

Só precisa de **Python 3** (biblioteca padrão). Sem `pip install`, sem build, sem internet: a biblioteca do grafo 3D já vem dentro do projeto.

## Início rápido

```bash
git clone https://github.com/<seu-usuario>/agLocalSite.git
cd agLocalSite
```

| Sistema | Como iniciar |
|---|---|
| Windows | duplo-clique em `start.bat` |
| Mac / Linux | `./start.sh` |
| Qualquer um | `python serve.py` |

O navegador abre em `http://localhost:8000/`, que leva ao site em `/_ag/`. Porta ocupada: ele tenta a seguinte. Para escolher outra: `start.bat 8001` ou `./start.sh 8001`.

Por padrão ele lê **só a própria pasta** `agLocalSite/` (incluindo `docs/`) e nada fora dela.

## Usar em outro projeto

Copie a pasta `agLocalSite/` para dentro do projeto cujos `.md` você quer ver e aponte a raiz para a pasta que a contém, no `config.json`:

```json
{ "raiz": ".." }
```

```
meu-projeto/            <- com "raiz": ".." tudo é lido a partir daqui
├── README.md           -> grupo "Home" no menu
├── docs/, notas/ ...   -> cada pasta com .md vira um grupo do menu
└── agLocalSite/        <- esta pasta (nunca aparece no menu)
```

`raiz` também aceita caminho relativo (`"../OutraPasta"`) ou absoluto. Mudanças em `raiz` e `porta` valem a partir do próximo `start`.

## O que ele faz

- **Menu, busca e grafo 3D de tags** (tags do frontmatter, da pasta e do texto).
- **Edição no navegador:** `Ctrl+S` salva, `Esc` cancela, `Ctrl+K` abre a barra de comandos (nova nota, buscar, editar). Checklists (`- [ ]`) marcam com um clique.
- **Quadro Kanban** a partir das notas com `status:` e itens de checklist.
- **Post-its** soltos na página.
- **Atualização automática:** se um `.md` mudar em outro editor, a página percebe em poucos segundos.
- **Painel Configurar:** troca título, textos dos botões, paleta, pastas ignoradas e rótulos do menu sem abrir o `config.json`.
- Tema claro/escuro, 5 paletas (`padrao`, `oceano`, `floresta`, `grafite`, `ameixa`) e layout para celular.
- Links entre documentos com `` `pasta/arquivo.md` ``.

**A fonte da verdade é o seu `.md`.** Tudo o que o site grava além disso fica em `agLocalSite/dados/` (histórico de até 20 versões por arquivo, post-its, histórico do `config.json`). A raiz nunca recebe arquivos do site. Abrindo `site/index.html` direto, sem o servidor, o site funciona só como leitor.

## Configuração (opcional)

Tudo em `config.json`. Chave ausente ou vazia usa o padrão. Depois de salvar, recarregue a página (F5).

| Chave | Efeito | Padrão |
|---|---|---|
| `raiz` | Pasta que o site lê, relativa a `agLocalSite/`. | `.` |
| `titulo` | Título grande do cabeçalho. | nome da pasta do projeto |
| `subtitulo` | Linha abaixo do título. | `Navegue pelas pastas ao lado.` |
| `etiqueta` | Texto pequeno acima do título. | `agLocalSite` |
| `titulo_aba` | Título da aba do navegador. | `<titulo> — agLocalSite` |
| `prefixo_url` | Endereço do site: `http://localhost:8000/<prefixo_url>/`. | `_ag` |
| `porta` | Porta inicial. | `8000` |
| `ignorar` | Pastas a ignorar em qualquer nível, além das padrão. | `[]` |
| `rotulos` | Nome de cada grupo no menu, ex.: `{"02-Produtos": "02 · Produtos"}`. | `{}` |
| `home_prioridade` | Arquivos soltos na raiz que vêm primeiro (sem `.md`). | `["inicio","home","index","readme"]` |
| `textos` | Rótulos da interface (`grafo`, `quadro`, `mais`, `menu`, `tema_claro`, `tema_escuro`, `home`, `rodape`). | `{}` |
| `tema` | `{"paleta": "oceano", "modo": "sistema"}`; modos: `claro`, `escuro`, `sistema`. | `{"paleta":"padrao","modo":"claro"}` |

Exemplo:

```json
{
  "titulo": "Docs da Equipe",
  "etiqueta": "ACME / wiki",
  "subtitulo": "Tudo sobre o produto.",
  "prefixo_url": "wiki",
  "textos": { "grafo": "◎ Mapa de tags", "quadro": "▦ Tarefas", "rodape": "" }
}
```

O painel **⚙ Configurar** edita quase tudo isso por você (só aparece com o servidor aberto). Ele não altera `raiz`, `prefixo_url` nem `porta`, de propósito. Se o `config.json` estiver com JSON inválido, ele mostra a linha do erro e não grava; **Desfazer** volta à versão anterior.

Ficam de fora do menu: pastas que começam com ponto, `agLocalSite`, `node_modules`, `__pycache__`, `venv`, `env`, `dist`, `build`, `target`, `out`, `coverage`, `vendor`, `bin`, `obj` e `Pods`. O menu mostra até 1500 `.md`.

## Editar por fora do site

Edite os `.md` no editor que quiser. Com o servidor aberto, a atualização é automática. Sem ele, rode `sync.bat`, `./sync.sh` ou `python sync.py`.

`site/js/content.js`, `graph-data.js` e `tema-dados.js` são **gerados**: não edite à mão e, no git, ignore-os junto com `__pycache__/` e `dados/`:

```gitignore
__pycache__/
dados/
site/js/content.js
site/js/graph-data.js
site/js/tema-dados.js
```

## Segurança

- O servidor atende apenas `127.0.0.1` e recusa `Host` e `Origin` de fora.
- Arquivos e pastas ocultos (`.env`, `.git`), a pasta `dados/` e a própria `agLocalSite/` (quando está dentro da raiz) não são servidos.
- A página tem CSP (`script-src 'self'`); HTML cru dentro de um `.md` aparece como texto, e imagem remota não é carregada.
- **A raiz inteira fica visível no navegador local. Não exponha a porta na rede.**

## Testes

```bash
python3 -m unittest discover -s tests
node --test tests/*.test.js
```

Rodam em cópia temporária e não tocam seus arquivos. Na última execução: 212 testes Python OK; testes Node sem falhas.

Os `tests/*_navegador.py` (Playwright) exigem `pip install playwright && playwright install chromium`. `layout`, `navegacao` e `seguranca` rodam neste repositório; `escrita`, `kanban`, `webkit` e `celular` usam documentos do projeto de origem e saem com código 77 ("PULADO") quando eles não existem. Os de navegador ainda não foram portados para o endereço `/_ag/`: ajuste `site/index.html` para `_ag/` neles antes de usar.

## Limitações conhecidas

- Não apaga, move nem renomeia documentos, e criar pasta nova é à mão. Faça por fora e rode `sync`.
- Renomear um `.md` à mão deixa o post-it dele para trás: mova também `dados/postits/<caminho>.json`.
- `.md` fora de UTF-8 aparece com `?` nos caracteres inválidos.
- Markdown: links só `http`, `https`, `mailto`, `#` e caminho relativo; imagem só se for local; lista aninhada fica achatada e `#####` não é título.

A lista completa, com o motivo e o contorno de cada item, está no `LEIA-ME.md`.

## Estrutura

```
agLocalSite/
├── serve.py            servidor local (estático + /api/*)
├── sync.py             gera os arquivos de dados do site a partir dos .md
├── agwrite.py          regras de escrita (salvar, histórico, nova nota)
├── configedit.py       leitura e gravação segura do config.json
├── graphdata.py        dados do grafo de tags
├── config.json         configuração
├── site/               interface (HTML, CSS, JS; sem build)
├── tests/              testes Python e Node
└── docs/               specs, plano e checklist visual
```

O desenho de cada peça (escrita, Kanban, post-its, painel) está em `docs/specs/`.

## Licença

Defina a licença do projeto antes de publicar (ainda não há arquivo `LICENSE`). A biblioteca [3d-force-graph](https://github.com/vasturiano/3d-force-graph) 1.80.0, incluída em `site/js/vendor/`, é MIT, com o texto em `site/js/vendor/LICENSE-3d-force-graph.txt`.
