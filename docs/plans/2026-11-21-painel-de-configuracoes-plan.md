# Painel de configurações e paletas: plano de implementação

> **Para quem executa:** REQUIRED SUB-SKILL: use superpowers:executing-plans (ou subagent-driven-development) e implemente tarefa por tarefa. Os passos usam caixas `- [ ]`.

**Objetivo:** pôr no site um painel "⚙ Configurar" que edita as opções seguras do `config.json` e troca a paleta de cores, sem a pessoa abrir arquivo nenhum.

**Arquitetura:** o servidor ganha três rotas (`GET /api/config`, `POST /api/config`, `POST /api/config/desfazer`) sobre um módulo puro de validação e mesclagem (`configedit.py`); o `sync.py` gera `tema-dados.js` a partir do `config.json`; o site ganha `tema.js` (lógica), `paletas.css` e um diálogo (`painel-model.js` puro, `painel-view.js`).

**Stack:** Python (só biblioteca padrão), JavaScript sem build, testes com `unittest` e `node --test`.

**Spec:** `docs/specs/2026-11-21-painel-de-configuracoes-design.md` (ler junto; as seções citadas abaixo são as dela).

**Execução:** as 9 tarefas foram executadas em 2026-11-21; os desvios do plano estão em "Decisões tomadas na implementação" na spec.

## Restrições globais

- Python só com a biblioteca padrão; sintaxe compatível com 3.7 (conferir com `ast.parse(src, feature_version=(3, 7))`).
- JavaScript sem build nem dependência nova; módulos com a guarda `module.exports` de `markdown.js`; scripts carregados por `<script>` na ordem do `index.html`.
- `site/css/style.css` **não** é editado.
- Chaves somente leitura: `raiz`, `prefixo_url`, `porta`. Limites: texto 120, rodapé 2000, `ignorar` 200 itens, nome 100, `rotulos` 200, `home_prioridade` 50, corpo das rotas de configuração 64 KB, `MAX_COPIAS` 20.
- Paletas: `padrao`, `oceano`, `floresta`, `grafite`, `ameixa`. Modos: `claro`, `escuro`, `sistema`.
- Textos da interface e mensagens de erro em português, curtos, sem caminho absoluto (como o `Erro` atual).
- O `setUp` dos testes que apontam `sync.CONFIG_PATH` e `sync.CONTENT_JS_PATH` passa a apontar também `sync.TEMA_DADOS_JS_PATH`.
- A pasta não é repositório git no ambiente do plano: cada tarefa termina com uma **sugestão** de commit, que o usuário executa.

## Foco da revisão

Entradas que a spec implica e nenhuma tarefa exercitaria sozinha; cada uma tem seu teste na tarefa dona:

1. Salvar sem alterar nada (`valores` vazio): não grava, não cria cópia, mantém a versão. (Tarefa 3)
2. Título ou rótulo com `<script>`, aspas, emoji ou espaços nas pontas: gravado literal; na tela, só como texto. (Tarefas 3 e 8)
3. `config.json` ausente (projeto novo): o painel abre com os padrões e salvar cria o arquivo. (Tarefa 3)
4. Duas abas salvando com a mesma `base_versao`: a segunda recebe 409. (Tarefa 3)
5. Paleta ou modo desconhecido já escrito no arquivo (versão antiga, edição à mão): a página usa o padrão e o terminal avisa. (Tarefas 1 e 6)

---

### Tarefa 1: tema, limites e leitor estrito no `sync.py`

**Arquivos:**
- Modificar: `sync.py` (perto de `TEXTOS_CHAVES`; `dados_site()`; `avisos_config()`; `escrever_arquivos()`)
- Modificar: `tests/test_agwrite.py` (`setUp` da `Base`, nova constante de caminho)
- Teste: `tests/test_tema_dados.py`

**Interfaces:**
- Produz: `PALETAS: tuple` de pares `(nome, rótulo)`, na ordem da restrição global, com rótulos `Padrão, Oceano, Floresta, Grafite, Ameixa`; `MODOS: tuple`; `LIMITES: dict` com as chaves `texto, rodape, itens_ignorar, nome, rotulos, home` (reusa `MAX_TEXTO` e `MAX_RODAPE`); `TEMA_DADOS_JS_PATH`; `tema() -> dict` (`{"paleta": str, "modo": str}`); `class ConfigIlegivel(Exception)` com `.msg`, `.linha`, `.coluna`; `ler_config_estrito() -> dict`; `dados_site()["tema"]`.

- [ ] **Passo 1: testes que falham** (`tests/test_tema_dados.py`, sobre a `Base`)
  - `test_tema_padrao`: sem config, `tema() == {"paleta": "padrao", "modo": "claro"}`.
  - `test_tema_valido`: `{"tema": {"paleta": "oceano", "modo": "sistema"}}` volta igual.
  - `test_tema_invalido_cai_no_padrao_com_aviso`: paleta `neon` e modo `roxo` viram `padrao`/`claro`; `avisos_config()` cita `"tema.paleta"` e `"tema.modo"`; `"tema": "x"` cita `"tema" precisa ser um objeto`.
  - `test_tema_dados_gerado`: depois de `sync.escrever_arquivos(*sync.montar_dados())`, o arquivo tem o cabeçalho `GERADO` e `const AG_TEMA = {"paleta": "oceano", "modo": "sistema", "paletas": ["padrao", "oceano", "floresta", "grafite", "ameixa"]};` (um config com oceano/sistema).
  - `test_dados_site_tem_tema`: `dados_site()["tema"] == tema()`.
  - `test_leitor_estrito`: arquivo ausente devolve `{}`; BOM é aceito; JSON quebrado levanta `ConfigIlegivel` com `linha` e `coluna` inteiros; um JSON que não é objeto (`[]`) também levanta.
- [ ] **Passo 2:** `python3 -m unittest tests.test_tema_dados -v`; esperado: FALHA (nomes inexistentes).
- [ ] **Passo 3: implementar** as interfaces acima em `sync.py`. `escrever_arquivos` grava `TEMA_DADOS_JS_PATH` com `json.dumps(..., ensure_ascii=False)` de `{**tema(), "paletas": [nomes]}`. `avisos_config()` ganha os avisos de tema no estilo dos de `textos`. Em `tests/test_agwrite.py`, a `Base.setUp` aponta `sync.TEMA_DADOS_JS_PATH` para `<ag>/site/js/tema-dados.js` (e restaura no `tearDown`, como faz com os outros).
- [ ] **Passo 4:** `python3 -m unittest discover -s tests`; esperado: tudo passa (117 existentes + novos).
- [ ] **Passo 5: sugestão de commit:** `feat(sync): tema, limites e leitor estrito do config.json`

---

### Tarefa 2: validação e mesclagem puras (`configedit.py`)

**Arquivos:**
- Criar: `configedit.py`
- Teste: `tests/test_configedit.py`

**Interfaces:**
- Consome: `sync.PALETAS`, `sync.MODOS`, `sync.LIMITES`, `sync.TEXTOS_CHAVES`.
- Produz: `CHAVES_EDITAVEIS: tuple`; `SOMENTE_LEITURA = ("raiz", "prefixo_url", "porta")`; `class ErroValidacao(Exception)` com `.campo` (texto, ex.: `"textos.grafo"`) e `.msg`; `validar(valores: dict) -> dict` (patch normalizado); `mesclar(atual: dict, patch: dict) -> dict`.

- [ ] **Passo 1: testes que falham** (`tests/test_configedit.py`, `unittest.TestCase` sem arquivo nem rede)
  - `validar`: aceita patch parcial; aplica `strip()`; `""` em `titulo`/`subtitulo`/`etiqueta`/`titulo_aba` e em `textos.*` (menos `rodape`) vira `None`; `rodape` `""` fica `""`; `None` passa.
  - `validar` recusa, com `campo` certo: `raiz`, `prefixo_url`, `porta` (mensagem manda editar o `config.json`); chave desconhecida; tipo errado (número em `titulo`, lista em `textos`); texto de 121 caracteres (e `rodape` de 2001); `textos.inventado`; `tema.paleta == "neon"`; `tema.modo == "roxo"`; item de `ignorar` com `/` ou `\`, repetido, vazio ou com 101 caracteres; 201 itens; `rotulos` com chave com separador ou rótulo de 121; `home_prioridade` com `readme.md` ou 51 itens.
  - `mesclar` (seção 5.2): chave de topo `None` remove; `textos` e `tema` mesclam e `None` remove só a subchave; objeto que fica vazio some; `ignorar`, `rotulos` e `home_prioridade` substituem por inteiro; chave desconhecida e as 3 somente leitura ficam intactas, na mesma ordem; o argumento `atual` não é alterado.
- [ ] **Passo 2:** `python3 -m unittest tests.test_configedit -v`; esperado: FALHA (módulo inexistente).
- [ ] **Passo 3: implementar** `configedit.py` com as assinaturas acima; uma tabela de regras por chave em vez de `if` encadeado. `mesclar` devolve uma cópia nova (`dict` preserva a ordem).
- [ ] **Passo 4:** `python3 -m unittest tests.test_configedit -v`; esperado: PASSA.
- [ ] **Passo 5: sugestão de commit:** `feat: configedit com validação e mesclagem do config.json`

---

### Tarefa 3: estado, gravação, histórico e desfazer (`agwrite.py`)

**Arquivos:**
- Modificar: `agwrite.py` (novo bloco "configuração", depois dos post-its)
- Teste: `tests/test_config_salvar.py`

**Interfaces:**
- Consome: `sync.ler_config_estrito`, `sync.ConfigIlegivel`, `sync.dados_site`, `sync.tema`, `sync.pastas_topo`, `sync.LIMITES`, `sync.PALETAS`, `configedit.validar`, `configedit.mesclar`, `configedit.ErroValidacao`, `_gravar`, `_mtime`, `_sincronizar`, `LOCK`, `Erro`, `MAX_COPIAS`.
- Produz: `config_estado() -> dict` com `valores, padroes, somente_leitura, pastas, paletas, limites, versao, site, legivel` (e `problema` quando `legivel` é falso); `config_salvar(valores: dict, base_versao: str) -> dict`; `config_desfazer() -> dict` (os dois devolvem o mesmo corpo de `config_estado()`). Códigos de erro: 400 `validacao` (com `campo`), 400 `somente_leitura`, 409 `conflito` (com `versao` e `valores`), 409 `config_ilegivel`, 409 `sem_historico`, 500 `copia`, 500 `gravar`. Versão do arquivo: `str(_mtime(CONFIG_PATH))` ou `"ausente"`. Cópias em `<DADOS_DIR>/config-historico/<data_hora>.json`.

- [ ] **Passo 1: testes que falham** (`tests/test_config_salvar.py`, sobre a `Base`)
  - Estado: sem arquivo, `legivel` verdadeiro, `versao == "ausente"` e `valores == {}`; com arquivo, `valores` só traz chaves editáveis e `somente_leitura` traz `raiz` e `prefixo_url`. **(Foco 3)**
  - Salvar: cria o arquivo ausente sem histórico; preserva chaves desconhecidas, as 3 somente leitura e a ordem; preserva CRLF; lê arquivo com BOM; a resposta reflete o novo `valores`.
  - **(Foco 1)** `config_salvar({}, versao)` não grava, não cria cópia e mantém a versão.
  - **(Foco 2)** título `<b>"x"</b> ✓  ` é gravado e devolvido literal (só com `strip()`).
  - **(Foco 4)** dois `config_salvar` com a mesma `base_versao`: o segundo levanta `Erro` 409 `conflito`, com `versao` e `valores` atuais.
  - Arquivo quebrado: `config_salvar` levanta 409 `config_ilegivel` e o arquivo fica idêntico byte a byte; `config_estado()["legivel"]` é falso com `problema` trazendo linha e coluna.
  - Histórico: a cópia existe depois de salvar com arquivo prévio; 25 gravações deixam 20 cópias; `_copia` falhando (mock) deixa o arquivo original intacto e levanta `copia`; `os.replace` falhando (mock) deixa o original intacto.
  - Sincronia: depois de salvar, `content.js` e `tema-dados.js` já refletem o título e a paleta, e `carimbo()` mudou.
  - Desfazer: restaura a versão anterior; duas chamadas voltam ao ponto de partida; sem cópias levanta 409 `sem_historico`; funciona com o `config.json` quebrado (o quebrado vira cópia).
  - **(Foco 5)** com `tema.paleta == "neon"` no arquivo, `config_estado()["site"]["tema"]["paleta"] == "padrao"`.
  - Somente leitura: `config_salvar({"raiz": ".."}, v)` levanta 400 `somente_leitura` e não grava.
- [ ] **Passo 2:** `python3 -m unittest tests.test_config_salvar -v`; esperado: FALHA.
- [ ] **Passo 3: implementar** as três funções em `agwrite.py`, tudo em `LOCK`, na ordem da seção 6.2 da spec (ler estrito, conferir versão, validar e mesclar, copiar, gravar com `crlf` igual ao original, `_sincronizar()`, devolver o estado). Gravar com `json.dumps(dados, indent=2, ensure_ascii=False) + "\n"`. Traduzir `ErroValidacao` em `Erro(400, "validacao", msg, campo=campo)`. Sem mudança na mesclagem: `{}` não grava.
- [ ] **Passo 4:** `python3 -m unittest discover -s tests`; esperado: tudo passa.
- [ ] **Passo 5: sugestão de commit:** `feat(agwrite): estado, gravação, histórico e desfazer do config.json`

---

### Tarefa 4: rotas e segurança HTTP (`serve.py`)

**Arquivos:**
- Modificar: `serve.py` (`api()` e `corpo()`)
- Teste: `tests/test_config_http.py` (servidor temporário como o `Servido` de `tests/test_config.py`)

**Interfaces:**
- Consome: `agwrite.config_estado`, `agwrite.config_salvar`, `agwrite.config_desfazer`.
- Produz: `GET /api/config`; `POST /api/config` (`{"valores": {...}, "base_versao": "..."}`); `POST /api/config/desfazer`; `MAX_CORPO_CONFIG = 64 * 1024`; `corpo(self, limite=MAX_CORPO)`.

- [ ] **Passo 1: testes que falham**
  - `GET /api/config` com Host certo: 200 com as chaves do contrato; Host errado: 403.
  - `POST` sem Origin: 403; `Content-Type` errado: 415; corpo de 70 KB: 413 (mas um `.md` de 100 KB ainda passa em `/api/salvar`, pois o limite de 2 MB continua lá).
  - `POST /api/config` válido: 200 e o arquivo muda; `valores` com `raiz`: 400 `somente_leitura` e arquivo intacto; campo inválido: 400 com `campo`.
  - `POST /api/config/desfazer` volta a versão; `GET /api/config/desfazer` dá 404 (rota é só POST).
  - Fuzz curto sobre `valores` (tipos errados, listas enormes, textos com `\x00`, `\ud800`, chaves com `../`): nenhuma resposta 500 e nenhum arquivo novo fora de `config.json` e de `dados/`.
- [ ] **Passo 2:** `python3 -m unittest tests.test_config_http -v`; esperado: FALHA (rotas 404).
- [ ] **Passo 3: implementar** as rotas em `api()` seguindo o padrão das existentes; `corpo()` recebe o limite, e as rotas de configuração passam `MAX_CORPO_CONFIG`.
- [ ] **Passo 4:** `python3 -m unittest discover -s tests`; esperado: tudo passa.
- [ ] **Passo 5: sugestão de commit:** `feat(serve): rotas do painel de configuração`

---

### Tarefa 5: paletas em CSS e régua de contraste

**Arquivos:**
- Criar: `site/css/paletas.css`
- Modificar: `site/index.html` (um `<link>` para `paletas.css`, depois do `style.css`)
- Teste: `tests/test_paletas.py`

**Interfaces:**
- Consome: `sync.PALETAS`; `site/css/style.css` (só leitura, para a Padrão).
- Produz: para cada paleta diferente de `padrao`, os blocos `:root[data-palette="<nome>"]` e `:root[data-palette="<nome>"][data-theme="dark"]`, cada um definindo exatamente os tokens da seção 7 da spec (`--bg`, `--bg-grid`, `--panel`, `--ink`, `--muted`, `--line`, `--line-soft`, `--accent`, `--accent2`, `--accent-soft`, `--cite`, `--glass`, `--on-line` e os `--g-*` que a Padrão define).

- [ ] **Passo 1: testes que falham**
  - `test_cada_paleta_tem_os_dois_blocos`: para cada nome de `PALETAS` (menos `padrao`) existem os dois blocos; nenhum bloco de paleta fora de `PALETAS`.
  - `test_blocos_definem_so_os_tokens_da_paleta`: o conjunto de variáveis de cada bloco é exatamente o da lista acima; nenhum `--pi-*`, `--code-*`, `--hit-*` nem `--danger`.
  - `test_contraste_nao_piora_a_padrao`: para os pares `ink/bg`, `ink/panel`, `muted/bg`, `muted/panel`, `accent/panel`, `accent2/panel`, `cite/panel`, `on-line/line`, em cada paleta e modo, a razão (fórmula WCAG de luminância) é maior ou igual a `min(4.5, razão da Padrão no mesmo par e modo)`. Os valores `rgba` (`--glass`) ficam fora.
  - `test_padrao_fixa_os_numeros_de_hoje`: `accent/panel` da Padrão clara mede entre 3.0 e 3.3, e `ink/bg` da Padrão passa de 14, para o piso não derivar em silêncio.
- [ ] **Passo 2:** `python3 -m unittest tests.test_paletas -v`; esperado: FALHA (arquivo inexistente).
- [ ] **Passo 3: implementar** `paletas.css` com 4 paletas × 2 modos. Cada uma parte de um matiz-base (Oceano 195°, Floresta 140°, Grafite 215° com saturação baixa, Ameixa 300°), com o mesmo esqueleto de luminosidade da Padrão; ajustar a luminosidade de cada token até o teste de contraste passar. Adicionar o `<link>` no `index.html`.
- [ ] **Passo 4:** `python3 -m unittest tests.test_paletas -v`; esperado: PASSA. A aparência fica para o checklist visual da Tarefa 9.
- [ ] **Passo 5: sugestão de commit:** `feat(site): paletas Oceano, Floresta, Grafite e Ameixa`

---

### Tarefa 6: `tema.js`, ligação no `index.html` e `aplicarConfig`

**Arquivos:**
- Criar: `site/js/tema.js`
- Modificar: `site/index.html` (no `<head>`, `tema-dados.js` e `tema.js` no lugar do script inline)
- Modificar: `site/js/app.js` (extrair `aplicarConfig(cfg)`; o botão Claro/Escuro usa `AGTema`)
- Teste: `tests/tema.test.js`

**Interfaces:**
- Consome: `AG_TEMA` (de `tema-dados.js`), `localStorage` chave `ag-theme`, `matchMedia`.
- Produz: `AGTema.resolverModo(pessoal, projeto, sistemaEscuro) -> "dark" | "light"` (pessoal válido vence; senão `escuro` → dark, `sistema` → conforme `sistemaEscuro`, qualquer outro → light); `AGTema.paletaValida(nome, lista) -> string` (`"padrao"` se fora da lista); `AGTema.aplicar(raiz, {paleta, modo, pessoal, sistemaEscuro, paletas})` (define `raiz.dataset.theme` e `raiz.dataset.palette`, este removido quando for `padrao`); `aplicarConfig(cfg)` em `app.js`, que aplica `titulo`, `etiqueta`, `subtitulo`, `titulo_aba`, rótulos e rodapé do `cfg` ao DOM com `textContent`.

- [ ] **Passo 1: testes que falham** (`tests/tema.test.js`, `node:test`)
  - `resolverModo`: pessoal `dark` vence projeto `claro`; pessoal `light` vence projeto `escuro`; sem pessoal, `escuro` dá dark, `sistema` segue `sistemaEscuro`, ausente dá light; pessoal com lixo (`"blue"`) é ignorado.
  - `paletaValida("neon", [...])` devolve `"padrao"`; `"oceano"` passa; não-texto vira `"padrao"`.
  - `aplicar` com objeto simulado: `dataset.palette` ausente para `padrao`, presente para `oceano`; `dataset.theme` correto.
  - `localStorage` que lança erro é tratado como sem escolha pessoal (função auxiliar `lerPessoal(storage)` exportada).
- [ ] **Passo 2:** `node --test tests/tema.test.js`; esperado: FALHA.
- [ ] **Passo 3: implementar** `tema.js` com a guarda `module.exports`, e ao carregar no navegador aplicar o tema antes da primeira pintura. Trocar o script inline do `<head>` pelos dois `<script src>`. Em `app.js`, mover o bloco que lê `AG_CONFIG` para `aplicarConfig(cfg)` e chamá-lo no carregamento; o botão de tema grava `ag-theme` como hoje e chama `AGView.applyTheme()`.
- [ ] **Passo 4:** `node --test tests/*.test.js` e `python3 -m unittest discover -s tests`; esperado: tudo passa. `aplicarConfig` é conferido na verificação em jsdom da Tarefa 8.
- [ ] **Passo 5: sugestão de commit:** `feat(site): tema.js com paleta e modo inicial`

---

### Tarefa 7: modelo do painel (`painel-model.js`)

**Arquivos:**
- Criar: `site/js/painel-model.js`
- Teste: `tests/painel.test.js`

**Interfaces:**
- Produz (todas puras, exportadas por `module.exports` e como o global `AGPainelModel` no navegador): `montarEnvio(original, atual) -> object` (só as chaves alteradas; listas e mapas inteiros; `{}` se nada mudou); `envioPadroes(chavesEditaveis) -> object` (todas em `null`); `rodapeEstado(textos) -> "padrao" | "ocultar" | "personalizado"`; `rodapeValor(estado, texto) -> null | "" | string`; `validarCampo(chave, valor, limites) -> string | null` (mensagem em português ou `null`); `moverItem(lista, indice, delta) -> lista` (copia; não sai dos limites).

- [ ] **Passo 1: testes que falham** (`tests/painel.test.js`)
  - `montarEnvio`: sem mudança dá `{}`; mudar só `titulo` envia só `titulo`; mudar um texto envia `textos` só com a subchave; voltar um campo ao vazio envia `null`; lista alterada vai inteira.
  - `rodapeEstado`/`rodapeValor`: ausente é `padrao` ↔ `null`; `""` é `ocultar` ↔ `""`; texto é `personalizado` ↔ o texto.
  - `validarCampo`: texto de 121 caracteres dá mensagem; `ignorar` com `/` dá mensagem; dentro do limite dá `null`; os limites vêm do argumento (testar com `{texto: 5}`).
  - `moverItem`: sobe, desce, não passa dos extremos e não altera a lista original.
  - `envioPadroes` cobre exatamente as chaves editáveis recebidas.
- [ ] **Passo 2:** `node --test tests/painel.test.js`; esperado: FALHA.
- [ ] **Passo 3: implementar** `painel-model.js` com a guarda `module.exports`.
- [ ] **Passo 4:** `node --test tests/*.test.js`; esperado: tudo passa.
- [ ] **Passo 5: sugestão de commit:** `feat(site): modelo do painel de configuração`

---

### Tarefa 8: diálogo (`painel-view.js`, `painel.css`) e verificação ponta a ponta

**Arquivos:**
- Criar: `site/js/painel-view.js`, `site/css/painel.css`
- Modificar: `site/index.html` (`#cfg-btn` em `.side-tools`, escondido; `painel.css`; scripts na ordem `painel-model.js`, `painel-view.js`, antes do `app.js`); `site/js/editor-ui.js` (o botão acompanha `voltouEscrita()` e `emLeitura()`)
- Verificação (fora do repositório): `/tmp/jd/painel_e2e.js` com jsdom

**Interfaces:**
- Consome: `GET/POST /api/config`, `POST /api/config/desfazer`; `AGPainelModel` (Tarefa 7); `AGTema` e `aplicarConfig` (Tarefa 6); `AGView.applyTheme()`.
- Produz: `AGPainel.setEscrita(ativa: boolean)`; `AGPainel.abrir()`. O diálogo segue a seção 7 da spec: 4 grupos, somente leitura no rodapé, Salvar, Desfazer, Restaurar padrões, Cancelar; faixa de conflito e modo leitura com a linha e a coluna do erro (seção 8).

- [ ] **Passo 1: escrever o roteiro da verificação** em `/tmp/jd/painel_e2e.js` antes da implementação: servidor real numa pasta temporária; abrir a página; `#cfg-btn` visível só com escrita; abrir o diálogo; trocar título e paleta; Salvar; conferir (a) o DOM mudou sem recarregar, (b) o `config.json` no disco, (c) `dataset.palette`, (d) F5 mantém tudo; título com `<b>x</b>` aparece como texto; conflito (alterar o arquivo por fora e salvar) mostra a faixa; arquivo quebrado deixa Salvar desabilitado; Desfazer volta; "Restaurar padrões" limpa as chaves editáveis e mantém as 3 somente leitura. **(Foco 2)**
- [ ] **Passo 2:** rodar o roteiro; esperado: FALHA (botão ausente).
- [ ] **Passo 3: implementar** `painel-view.js` (`<dialog>` criado por JS, foco preso, Esc fecha, rótulos nos campos, prévia ao vivo com restauração no Cancelar, ao salvar com `modo` alterado remover `ag-theme` do navegador e reaplicar com `AGTema`), `painel.css` (variáveis do tema, sem cores fixas) e as ligações no `index.html` e no `editor-ui.js`.
- [ ] **Passo 4:** rodar o roteiro e `python3 -m unittest discover -s tests` e `node --test tests/*.test.js`; esperado: roteiro passa sem erro de JavaScript (ignorando só o que o jsdom não implementa, como `scrollTo`) e as suítes passam.
- [ ] **Passo 5: sugestão de commit:** `feat(site): painel de configuração com paletas`

---

### Tarefa 9: documentação, checklist visual e entrega

**Arquivos:**
- Modificar: `LEIA-ME.md` (seção "Painel de configurações"; tabela com `tema`; `tema-dados.js` na lista de arquivos gerados), `config.json` (exemplo com `"tema": {"paleta": "padrao", "modo": "claro"}`), `docs/specs/2026-11-21-painel-de-configuracoes-design.md` (status "entregue", seção 12 com o que ficou de fora)
- Criar: `docs/checklist-visual.md` (5 paletas × 2 modos: menu lateral, painel de configuração, grafo, quadro, post-its, bloco de código, com a coluna para marcar)

- [ ] **Passo 1:** escrever os textos acima. O `LEIA-ME.md` diz o que o painel edita, o que é somente leitura e por quê, e como desfazer.
- [ ] **Passo 2: verificação final:** `python3 -m unittest discover -s tests`; `node --test tests/*.test.js`; checagem de sintaxe 3.7 dos `.py`; `file start.bat sync.bat` ainda com CRLF; o roteiro jsdom da Tarefa 8 de novo.
- [ ] **Passo 3:** gerar o `agLocalSite.zip` (sem `__pycache__` nem `dados/`) e entregar com o resumo: feito, verificado por, não verificado (aparência em navegador real, Windows com OneDrive), pendências.
- [ ] **Passo 4: sugestão de commit:** `docs: painel de configuração, checklist visual e spec entregue`
