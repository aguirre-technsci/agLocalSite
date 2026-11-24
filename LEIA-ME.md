# agLocalSite

Visualizador e editor local de `.md`. Por padrão ele lê **só a pasta onde está** (a `agLocalSite/` e o que houver dentro dela, como `docs/`) e nada fora dela.

Para ver os `.md` de **outro projeto**, copie a pasta `agLocalSite/` para dentro dele e aponte a raiz para a pasta que a contém, com `"raiz": ".."` no `config.json`:

```
meu-projeto/            <- com "raiz": ".." tudo é lido a partir daqui
├── README.md           -> grupo "Home" no menu
├── docs/ , notas/ ...  -> cada pasta com .md vira um grupo do menu
└── agLocalSite/        <- esta pasta (nunca aparece no menu)
```

## Usar

1. Deixe `agLocalSite/` onde está (lê só ela mesma) ou, para ler um projeto, copie-a para dentro dele e ponha `"raiz": ".."` no `config.json`.
2. **Windows:** duplo-clique em `agLocalSite/start.bat`. **Mac/Linux:** `agLocalSite/start.sh`. Pelo PowerShell: `python agLocalSite\serve.py` (de qualquer pasta).
3. O navegador abre em `http://localhost:8000/` (que leva ao site, em `/_ag/` por padrão; veja `prefixo_url`). Porta ocupada: ele tenta a seguinte. Outra porta: `start.bat 8001`.

Precisa só de Python 3 (biblioteca padrão). Sem instalar nada.

## O que ele faz

- **Menu** com todas as pastas e `.md` da raiz (veja a chave `raiz`), **busca** e **grafo 3D de tags** (tags do frontmatter, da pasta e do texto).
- **Editar** o documento aberto (Ctrl+S salva, Esc cancela), **marcar checklist** com um clique, **Nova nota** (Ctrl+K), **Quadro Kanban** (notas com `status:` e itens `- [ ]`) e **post-its** soltos na página.
- **Atualização automática**: mudou um `.md` em outro editor, a página percebe em poucos segundos.
- **Painel ⚙ Configurar** (com o `start` aberto): troca título, textos dos botões, paleta de cores, pastas ignoradas e rótulos do menu sem abrir arquivo nenhum (seção abaixo).
- Tema claro/escuro e 5 paletas de cor, funciona no celular, links entre documentos com `` `pasta/arquivo.md` ``.
- Tudo grava no próprio `.md` (a fonte da verdade). Cópia da versão anterior em `agLocalSite/dados/historico/` (20 por arquivo). Post-its em `agLocalSite/dados/postits/`. **A raiz nunca recebe arquivos do site: tudo o que o site grava fica em `agLocalSite/dados/` (que também nunca aparece no menu nem é servida).**
- Sem o servidor (abrindo `site/index.html` direto) o site só lê.

Atalhos, Quadro e post-its funcionam como no projeto de origem (GasFlow). O desenho de cada peça está em `agLocalSite/docs/specs/`.

## Configurar (opcional): `agLocalSite/config.json`

Tudo o que aparece na tela e o endereço do site se ajustam por aqui, sem mexer no código. **Chave ausente ou vazia usa o padrão.** Depois de salvar o arquivo, recarregue a página (F5): com o `start` aberto o servidor percebe a mudança sozinho. `porta` e `raiz` exigem fechar e abrir o `start` de novo.

| Chave | Efeito | Padrão |
|---|---|---|
| `raiz` | A pasta que o site lê, **relativa à `agLocalSite/`**. `"."` = só a própria `agLocalSite/`; `".."` = a pasta que a contém; `"../AgIAWeb"` = uma pasta ao lado; também aceita caminho absoluto. Pasta que não existe: o terminal avisa e ele lê só a própria `agLocalSite/`. Vale a partir do próximo `start`. | `.` |
| `titulo` | Título grande do cabeçalho. | Nome da pasta do projeto |
| `subtitulo` | Linha abaixo do título. | `Navegue pelas pastas ao lado.` |
| `etiqueta` | Texto pequeno acima do título. | `agLocalSite` (com `raiz` diferente de `"."`: `NOME-DA-PASTA / agLocalSite`) |
| `titulo_aba` | Título da aba do navegador. | `<titulo> — agLocalSite` |
| `prefixo_url` | Onde o site mora: `http://localhost:8000/<prefixo_url>/`. Um só trecho (letras, números, `_`, `-`; até 32; não pode ser `api`). Se uma pasta da raiz tiver esse nome, ela fica escondida (o terminal avisa). | `_ag` |
| `porta` | Porta inicial. Ocupada, tenta a seguinte. | `8000` |
| `ignorar` | Nomes de pasta a ignorar em qualquer nível, além dos padrões. | `[]` |
| `rotulos` | `{"02-Produtos": "02 · Produtos"}`: nome do grupo no menu. Sem isso, o rótulo sai do nome da pasta. | `{}` |
| `home_prioridade` | Nomes (sem `.md`) dos arquivos soltos na raiz que vêm primeiro. | `["inicio","home","index","readme"]` |
| `textos` | Rótulos da interface (tabela abaixo). Só estas chaves; outra dá aviso no terminal. | `{}` |
| `tema` | `{"paleta": "oceano", "modo": "sistema"}`. Paletas: `padrao`, `oceano`, `floresta`, `grafite`, `ameixa`. Modos: `claro`, `escuro`, `sistema` (segue o do computador). A escolha de cada visitante no botão Claro/Escuro vale mais que o `modo`. Valor desconhecido: usa o padrão e o terminal avisa. | `{"paleta": "padrao", "modo": "claro"}` |

Chaves de `textos` (cada uma opcional; até 120 caracteres, o rodapé até 2000):

| Chave | O que muda | Padrão |
|---|---|---|
| `grafo` | Botão do grafo de tags. | `◎ Grafo de tags` |
| `quadro` | Botão do Quadro Kanban. | `▦ Quadro` |
| `mais` | Botão da barra de comandos. | `+` |
| `menu` | Botão do menu no celular. | `☰ Menu` |
| `tema_claro` / `tema_escuro` | O botão de tema mostra o que **vai** ativar: `tema_claro` quando está no escuro. | `☀ Claro` / `☾ Escuro` |
| `home` | Nome do grupo dos `.md` soltos na raiz. | `Home` |
| `rodape` | Texto do rodapé (texto puro). **`""` esconde o rodapé.** | Explicação dos atalhos |

Exemplo:

```json
{
  "titulo": "Docs da Equipe",
  "etiqueta": "ACME / wiki",
  "titulo_aba": "Wiki ACME",
  "subtitulo": "Tudo sobre o produto.",
  "prefixo_url": "wiki",
  "textos": { "grafo": "◎ Mapa de tags", "quadro": "▦ Tarefas", "home": "Início", "rodape": "" }
}
```

Já ficam de fora: pastas que começam com ponto (`.git`, `.venv`), `agLocalSite`, `node_modules`, `__pycache__`, `venv`, `env`, `dist`, `build`, `target`, `out`, `coverage`, `vendor`, `bin`, `obj`, `Pods`. O menu mostra até 1500 `.md` (com aviso se passar).

Para mudar além disso (cores, fontes, layout), edite `site/css/style.css` e `site/index.html`: é a parte visual, e é toda sua.

## Painel de configurações (⚙ Configurar)

Com o `start` aberto aparece o botão **⚙ Configurar** no menu lateral (sem o servidor ele não existe: o site fica só de leitura). Ele edita o `config.json` por você:

- **Identidade:** título, etiqueta, subtítulo e título da aba. Campo vazio usa o padrão, que aparece como dica no campo.
- **Aparência:** modo inicial (claro, escuro ou seguir o sistema) e a paleta. Escolher aplica a prévia na página na hora; só vale ao **Salvar**. **Fechar** (ou Esc) desfaz a prévia.
- **Textos da interface:** os rótulos dos botões e o nome do grupo "Home", cada um com **padrão** para voltar ao original. O rodapé tem 3 estados: padrão, ocultar ou personalizado.
- **Pastas:** `ignorar`, o nome de cada grupo do menu e a ordem dos arquivos soltos no Home.
- **Só no `config.json`** (aparecem como leitura): `raiz`, `prefixo_url` e `porta`. Elas definem o que o servidor lê e serve, então o painel não as altera: edite o arquivo e feche e abra o `start`.

Salvar grava e atualiza a página sem F5. **Desfazer** volta à versão anterior do `config.json` (até 20 cópias em `agLocalSite/dados/config-historico/`) e funciona até com o arquivo quebrado. **Restaurar padrões** limpa as opções editáveis (pede confirmação) e mantém `raiz`, `prefixo_url`, `porta` e qualquer opção que o painel não conheça.

Cuidados que o painel toma: se o `config.json` estiver com JSON inválido, ele mostra a linha e a coluna do erro e **não grava** (nunca sobrescreve um arquivo que não consegue ler); se o arquivo mudou no disco depois de o painel abrir, oferece recarregar ou salvar mesmo assim; todo texto aparece na página como texto, nunca como HTML. A primeira gravação pelo painel reformata o arquivo (recuo de 2 espaços, mesma ordem das opções).

## Segurança

O servidor só atende `127.0.0.1` e recusa `Host` e `Origin` de fora. Arquivos e pastas ocultos (`.env`, `.git`) a pasta `dados/` e, quando a `agLocalSite/` está dentro da raiz, ela inteira não são servidos pela raiz. A raiz inteira do projeto é visível no navegador local, então não exponha a porta na rede.

## Editar por fora do site

Edite os `.md` onde quiser e rode `agLocalSite/sync.bat` (ou `sync.sh`, ou `python agLocalSite/sync.py`). Com o `start` aberto isso é automático. O `site/js/content.js`, o `graph-data.js` e o `tema-dados.js` são gerados: não edite à mão (se usar git, convém ignorá-los junto com `__pycache__/` e `dados/`).

## Testes

Testes de navegador que rodam neste zip (precisam de `pip install playwright && playwright install chromium`): `layout_navegador.py`, `navegacao_navegador.py` e `seguranca_navegador.py`. Os de `escrita`, `kanban`, `webkit` e `celular` usam os documentos do projeto de origem (`01-Visao-e-Negocio/`) e saem com código 77 ("PULADO") quando essa pasta não existe.

```
python3 -m unittest discover -s agLocalSite/tests
node --test agLocalSite/tests/*.test.js
```

Rodam em cópia temporária e não tocam seus arquivos. Os `*_navegador.py` (Playwright/WebKit) vêm do projeto de origem e **ainda não foram portados** para o endereço `/_ag/`; ajuste `site/index.html` para `_ag/` neles antes de usar.

## OneDrive

Arquivos e pastas que estão **só na nuvem** (Arquivos Sob Demanda) são pulados: o site nem lista nem abre esses itens, então o OneDrive não baixa nada por causa dele. O terminal avisa quantos ficaram de fora. Para incluí-los, marque no OneDrive "Manter sempre neste dispositivo". Com o padrão (`"raiz": "."`) ele só toca a própria `agLocalSite/`. Se você aponta a raiz para uma pasta que reúne vários projetos, tudo o que estiver nela é varrido a cada 2 segundos.

## Limitações conhecidas

O que **não tem correção** (é do desenho, ou depende de testar na sua máquina) fica catalogado aqui, com o contorno.

| # | Limitação | Por quê | Contorno |
|---|---|---|---|
| 1 | O menu mostra no máximo **1500** `.md`. Passou disso, as últimas pastas (ordem alfabética) somem. O aviso só aparece no terminal, não na página. | `content.js` carrega o texto de todos os documentos; sem teto, a página fica pesada. | `ignorar` no `config.json` para as pastas que não interessam, ou aponte `raiz` para uma pasta menor. |
| 2 | A raiz inteira é varrida **a cada 2 segundos** (só a lista e as datas dos `.md`, não o conteúdo). | É como a página percebe que um `.md` mudou por fora. Custa mais em árvore grande e em pasta do OneDrive. | Raiz menor (item 1) e `ignorar`. |
| 3 | Itens **só na nuvem** (OneDrive, "Arquivos Sob Demanda") não aparecem no menu. | Ler ou listar isso faz o OneDrive baixar; o site pula de propósito. O terminal diz quantos ficaram de fora. | No OneDrive, "Manter sempre neste dispositivo". |
| 4 | **Não verificado no Windows com OneDrive real:** a detecção de itens só-nuvem (atributos do Windows), a porta exclusiva (duas cópias não dividem mais a mesma porta) e a nova tentativa ao gravar quando o arquivo está preso. | Foram testados por simulação, em Linux. | Se algo local sumir do menu com o aviso do item 3, ou o salvar continuar falhando, anote o que o terminal mostrou. |
| 5 | **Não verificado visualmente:** CSS, grafo 3D, Quadro Kanban e post-its. A página inicia sem erro de JavaScript e o markdown foi testado, mas sem navegador real. | Os `*_navegador.py` (Playwright/WebKit) ainda não foram portados para `/_ag/`. | Abra o site e confira; veja a seção Testes. |
| 6 | Não apaga, move nem renomeia documento; criar pasta nova é à mão. | Desenho: o site nunca remove nada seu. | Faça por fora e rode `sync`. |
| 7 | Um `.md` fora de UTF-8 aparece com `?` nos caracteres inválidos. | A leitura troca o byte inválido para não derrubar o sync. | Salve o arquivo em UTF-8. |
| 8 | Renomear um `.md` à mão deixa o post-it dele para trás. | O post-it é ligado ao caminho do arquivo. | Mova também `agLocalSite/dados/postits/<caminho>.json`. |
| 9 | Markdown: só links `http`, `https`, `mailto`, `#` e caminho relativo; HTML cru no `.md` aparece como texto. Imagem só se for **local** (`![x](img/a.png)`, relativa à pasta do documento, extensão de imagem): vira `<img>`. Imagem de fora (`http`, `data:`) aparece como `[imagem: texto]`. Lista aninhada fica achatada e `#####` não é título. | Proteção: um `.md` de fora não pode executar nada nem avisar um servidor externo (imagem remota rastrearia quem abre o arquivo). A página também tem CSP (`script-src 'self'`). | Nenhum: é intencional. |
| 10 | O painel não edita `raiz`, `prefixo_url` nem `porta`. | Definem o que o servidor lê e serve (ou exigem reiniciar); se a página pudesse mudá-las, uma falha futura de XSS viraria leitura do disco. | Edite o `config.json` e feche e abra o `start`. |
| 11 | A primeira gravação pelo painel reformata o `config.json` (recuo de 2 espaços). | JSON não guarda comentários nem a formatação original. | Nada se perde além da formatação; **Desfazer** volta ao arquivo anterior. |
| 12 | As paletas foram conferidas por **contraste numérico** (todos os pares de texto em 4,7:1 ou mais nas 4 paletas novas), mas a aparência real na interface ainda não foi vista em navegador. | Não havia navegador no ambiente de desenvolvimento. | Passe o `docs/checklist-visual.md` e me diga o que destoar. |
