# Painel de configurações e paletas do agLocalSite: design

Data: 2026-11-21. Status: entregue (v1), com a conferência visual das paletas pendente (`docs/checklist-visual.md`). Depende da peça 1 (fundação de escrita), já entregue. Aprovado por partes em conversa (painel e campos; API e segurança; paletas e modo; erros e testes).

## 1. Objetivo

O agLocalSite é um projeto aberto que cada pessoa usa para a própria ideia. Hoje o nome, os rótulos e o visual só mudam editando o `config.json` à mão, o que afasta quem não conhece JSON. Esta peça põe dentro do site um painel "⚙ Configurar" que edita as opções seguras do `config.json` e troca a paleta de cores, sem a pessoa abrir arquivo nenhum.

Critério de sucesso: uma pessoa que nunca viu o projeto abre o site, clica em "⚙ Configurar", troca o título e a paleta, salva e vê o resultado na hora, sem F5 e sem editar arquivo. O `config.json` continua sendo a fonte da verdade e continua válido para quem prefere editá-lo à mão.

## 2. Escopo

Dentro:

- Botão "⚙ Configurar" na barra do menu lateral, visível só com a escrita ativa, que abre um diálogo com 4 grupos de campos (seção 7).
- Três rotas novas no servidor, com as salvaguardas da peça 1 (seção 6).
- Cinco paletas prontas (Padrão, Oceano, Floresta, Grafite, Ameixa), cada uma em modo claro e escuro, e um modo inicial por projeto (claro, escuro ou seguir o sistema).
- Arquivos novos no site: `paletas.css` (cores), `painel.css` (estilo do diálogo, porque o `style.css` não é editado), `tema.js` (lógica do modo e da paleta), `painel-model.js` e `painel-view.js`, mais um arquivo gerado pelo sync, `tema-dados.js`.
- Histórico do `config.json` (até 20 cópias) e ação "Desfazer".
- Testes automatizados e documentação atualizada (seções 10 e 11).

Fora, e por quê:

- Editar `raiz`, `prefixo_url` e `porta` pelo painel. A `raiz` define quanto do disco o servidor lê e serve; se a página pudesse mudá-la, uma falha futura de XSS viraria leitura do disco inteiro. As três aparecem no painel como somente leitura.
- Cor de destaque livre, escolha de fonte e envio de logo. A cor livre exige checagem de contraste nos dois modos; entra depois, se pessoas de fora pedirem.
- Idioma da interface (pt-BR/en). Hoje só os rótulos de `textos` são trocáveis; o resto é português fixo. Fica para depois da validação com usuários.
- Vários projetos nomeados com seletor no site, e exportar como site estático.
- Aplicar nova `porta` ou nova `raiz` sem reiniciar o `start`.
- Escolher a aparência por pessoa dentro do projeto além do botão Claro/Escuro que já existe.

## 3. Como é hoje

- `config.json` (opcional) tem as chaves `raiz`, `titulo`, `subtitulo`, `etiqueta`, `titulo_aba`, `prefixo_url`, `porta`, `ignorar`, `rotulos`, `home_prioridade` e `textos` (8 rótulos conhecidos: `grafo`, `quadro`, `mais`, `menu`, `tema_claro`, `tema_escuro`, `home`, `rodape`).
- `sync.py`: `config()` lê o arquivo (UTF-8 com ou sem BOM) e devolve `{}` com um aviso no terminal se o JSON estiver quebrado; `dados_site()` monta o `AG_CONFIG` que vai para o `content.js`; `textos()`, `prefixo_url()`, `caminho_raiz()` e `avisos_config()` validam; `escrever_arquivos()` grava `content.js` e `graph-data.js`.
- `agwrite.py`: `LOCK` protege gravação e sync; `Erro(status, codigo, msg, **extra)` já aceita campos extras no corpo; `_gravar` faz gravação atômica (arquivo temporário e `os.replace`, com novas tentativas contra travas do OneDrive) e preserva CRLF; `_sincronizar()` refaz os arquivos gerados; `carimbo()` já inclui `config.json` (editar só o `config.json` refaz o `content.js` pela consulta de 2 segundos). `_copia(rel, caminho)` guarda cópias, mas só de `.md`, em `dados/historico/<caminho sem .md>/`.
- `serve.py`: `checar()` exige Host e Origin da própria máquina e `Content-Type` JSON nos POST; `corpo()` limita o pedido a `MAX_CORPO` (2 MB); `api()` roteia `/api/...` e devolve `Erro` como JSON.
- Tema: variáveis CSS em `:root` (claro) e `:root[data-theme="dark"]` (escuro) no `style.css`; a escolha do botão Claro/Escuro fica no `localStorage` (`ag-theme`); um script no `<head>` do `index.html` aplica o escuro antes da primeira pintura; `AGView.applyTheme()` faz o grafo reler as cores. O CSS usa também `--accent2`.
- Interface: o botão `+` (`#ag-plus`) nasce escondido e acompanha o estado de escrita (`voltouEscrita()` e `emLeitura()` em `editor-ui.js`). `agTexto(chave, padrao)` em `markdown.js` resolve os rótulos de `textos`.

## 4. Arquitetura

Servidor (Python, sem dependências):

- `configedit.py` (novo, puro, sem leitura nem gravação de arquivo): `validar(valores)` e `mesclar(atual, patch)`, as regras das seções 5.1 e 5.2.
- `sync.py`: lista `PALETAS`, `MODOS` e `LIMITES`; função `tema()` (valida paleta e modo, caindo no padrão); `tema` passa a fazer parte de `dados_site()`; `escrever_arquivos()` também grava `site/js/tema-dados.js`; leitor estrito do `config.json` (`ler_config_estrito()`, que levanta erro com linha e coluna em vez de devolver `{}`).
- `agwrite.py`: `config_estado()`, `config_salvar(valores, base_versao)` e `config_desfazer()`; cópias do `config.json` em `dados/config-historico/<data_hora>.json` (pasta própria, para não colidir com notas), `MAX_COPIAS` cópias.
- `serve.py`: três rotas novas em `api()`.

Site (JavaScript e CSS):

- `site/css/paletas.css` (novo, carregado depois do `style.css`, que não é editado) e `site/css/painel.css` (novo, estilo do diálogo).
- `site/js/tema.js` (novo, no `<head>`): resolve o modo inicial e aplica `data-palette` e `data-theme`; exporta para teste em Node.
- `site/js/tema-dados.js` (gerado, no `<head>`, antes do `tema.js`): `const AG_TEMA = {...}`.
- `site/js/painel-model.js` (novo, puro, testável em Node): monta o envio só com os campos alterados, traduz os estados do rodapé, valida com os limites vindos do servidor.
- `site/js/painel-view.js` (novo): o diálogo, a prévia ao vivo e as chamadas à API.
- `index.html`: botão `#cfg-btn`, links dos novos arquivos; o script inline do `<head>` é substituído pelos dois arquivos de tema.
- `app.js`: a aplicação do `AG_CONFIG` ao DOM passa a ser uma função (`aplicarConfig(cfg)`), chamada no carregamento e depois de salvar no painel.

Unidades e fronteiras: o modelo do painel não conhece DOM nem rede; a visão só conversa com a API e com o modelo; o servidor valida tudo de novo, sem confiar no cliente.

## 5. Dados

### 5.1 Chaves editáveis e contrato de valores

Todas opcionais; ausente significa padrão.

| Chave | Tipo | Regra |
|---|---|---|
| `titulo`, `subtitulo`, `etiqueta`, `titulo_aba` | texto | até 120 caracteres; vazio ou `null` remove (volta ao padrão) |
| `textos.<chave>` | texto | só as 8 chaves conhecidas; até 120 caracteres (`rodape` até 2000); vazio ou `null` remove, exceto `rodape` |
| `textos.rodape` | texto ou `null` | `null` remove (rodapé padrão); `""` oculta o rodapé; texto o substitui (texto puro) |
| `tema.paleta` | enum | um nome de `PALETAS` |
| `tema.modo` | enum | `claro`, `escuro` ou `sistema`; ausente equivale a `claro` |
| `ignorar` | lista de nomes | até 200 itens, cada um de 1 a 100 caracteres, sem `/` nem `\`, sem repetição |
| `rotulos` | mapa nome da pasta → rótulo | até 200 entradas; chave de 1 a 100 caracteres sem `/` nem `\`; rótulo até 120 |
| `home_prioridade` | lista de nomes | até 50 itens, cada um de 1 a 100 caracteres, sem `/`, `\` nem `.md` no fim |

Somente leitura (recusadas se enviadas): `raiz`, `prefixo_url`, `porta`. Qualquer outra chave desconhecida também é recusada, para o erro de um painel mal escrito aparecer e não ficar escondido.

### 5.2 Semântica da mesclagem

- O envio é parcial: só as chaves alteradas.
- Chave de topo com `null` remove a chave inteira.
- Em `textos` e `tema` (objetos), o envio é mesclado com o que já existe; subchave `null` remove só ela; objeto que ficar vazio é removido.
- Em `ignorar`, `rotulos` e `home_prioridade`, o valor enviado substitui o anterior por inteiro.
- Chaves que o painel não conhece (por exemplo, uma opção criada à mão por outra versão do projeto) e as três somente leitura são preservadas como estão, na mesma ordem.
- Texto de uma linha é gravado com `strip()`; a leitura continua colapsando espaços, como `dados_site()` faz hoje.

### 5.3 Versão do arquivo

`base_versao` é o mtime do `config.json` no mesmo formato de `_mtime()` que `salvar` usa nos `.md`. Arquivo ausente tem versão fixa `"ausente"`, e a primeira gravação o cria.

### 5.4 Paletas

`PALETAS` em `sync.py`: `padrao` (Padrão), `oceano` (Oceano), `floresta` (Floresta), `grafite` (Grafite), `ameixa` (Ameixa). Os valores de cor são definidos na implementação e passam pela régua de contraste da seção 10 e pelo checklist visual.

### 5.5 `tema-dados.js` e modo

```
// GERADO por sync.py. Não edite.
const AG_TEMA = {"paleta": "oceano", "modo": "sistema", "paletas": ["padrao", "oceano", "floresta", "grafite", "ameixa"]};
```

Ordem de decisão do modo ao abrir a página: (1) a escolha pessoal de quem visita, o valor `ag-theme` do `localStorage`, gravado só quando a pessoa clica em Claro/Escuro; (2) `AG_TEMA.modo` (`sistema` usa `prefers-color-scheme`); (3) claro. `localStorage` bloqueado é tratado como ausente.

## 6. Servidor

Valem as salvaguardas de `checar()`: Host e Origin só da própria máquina, `Content-Type` JSON. O limite de corpo das rotas de configuração é 64 KB. O caminho gravado é sempre o `CONFIG_PATH` fixo; o cliente nunca informa caminho.

### 6.1 `GET /api/config`

Resposta: `valores` (o que está no arquivo, só as chaves editáveis), `padroes`, `somente_leitura` (`raiz` resolvida, `prefixo_url`, `porta`, caminho do arquivo), `pastas` (pastas de topo encontradas com o rótulo atual), `paletas` (nome e rótulo), `limites` (os números da seção 5.1, para o cliente usar os mesmos), `versao`, `historico` (quantas versões anteriores o Desfazer tem) e `site` (o resultado de `dados_site()`). Se o arquivo estiver com JSON quebrado: `legivel: false` e `problema` com mensagem, linha e coluna.

### 6.2 `POST /api/config`

Corpo: `{"valores": {...}, "base_versao": "..."}`. Em `LOCK`:

1. Lê o arquivo com o leitor estrito. JSON quebrado: recusa (`config_ilegivel`) e não altera o arquivo.
2. Se `base_versao` não bate com a versão atual: 409 `conflito`, com a versão e os valores atuais.
3. Valida e mescla (seção 5). Erro de validação: 400 com `campo`.
4. Se o arquivo já existe, guarda a versão anterior em `dados/config-historico/` e poda para `MAX_COPIAS`. Falha ao guardar a cópia: erro, nada gravado.
5. Grava com `_gravar` (atômico), preservando CRLF se o arquivo original usava.
6. Chama `_sincronizar()` para `content.js` e `tema-dados.js` já refletirem a mudança antes da resposta.
7. Devolve o mesmo corpo do `GET`.

### 6.3 `POST /api/config/desfazer`

Em `LOCK`: restaura a cópia mais recente de `dados/config-historico/`, guardando antes o estado atual como cópia (então desfazer duas vezes volta ao ponto de partida), sincroniza e devolve o estado. Funciona também com o `config.json` quebrado: o arquivo quebrado vira uma cópia e a anterior volta, que é a forma de recuperar um arquivo que o usuário estragou à mão. Sem cópias: 409 `sem_historico`.

### 6.4 Restaurar padrões

Não tem rota: o cliente envia `POST /api/config` com todas as chaves editáveis em `null`.

### 6.5 Segurança, resumo

- Lista fechada de chaves, tipos, tamanhos e valores; nada vindo do cliente vira caminho, CSS ou HTML.
- Textos vão para a tela com `textContent`; a paleta só entra como atributo se estiver em `PALETAS`; o `tema.js` repete essa checagem no cliente.
- Esconder o botão sem escrita ativa é conforto; quem protege é a API.
- Cobre DNS rebinding e página de outro site pelas mesmas checagens de Host e Origin das outras rotas.

## 7. Interface

**Entrada.** `#cfg-btn` "⚙ Configurar" em `.side-tools`, escondido por padrão e visível junto com o `+`.

**Diálogo** (`<dialog>`, foco preso, Esc fecha, todo campo com rótulo):

1. Identidade: título, etiqueta, subtítulo, título da aba. O padrão aparece como texto de apoio.
2. Aparência: modo inicial (claro, escuro, sistema) e paleta (lista dos 5 nomes; a amostra de cor é a própria prévia ao vivo na página, porque as cores das paletas só existem no `paletas.css` e copiá-las para a tela criaria uma segunda fonte). Escolher uma paleta ou um modo aplica a prévia na hora (`data-palette`, `data-theme`, `AGView.applyTheme()`); cancelar restaura o que estava salvo.
3. Textos: os 8 rótulos, cada um com "restaurar padrão". O rodapé tem três estados: padrão, ocultar, personalizado.
4. Pastas: `ignorar` (itens que se adicionam e removem), rótulo de cada pasta de topo encontrada, e `home_prioridade` como lista com subir, descer e remover.

**Somente leitura** no rodapé do diálogo: `raiz`, `prefixo_url`, `porta` e o caminho do `config.json`, com "edite o arquivo e reinicie o start".

**Ações:** Salvar (envia só o que mudou), Desfazer (desabilitado sem histórico), Restaurar padrões (com confirmação), Cancelar.

**Depois de salvar:** a visão aplica `site` da resposta com `aplicarConfig()` (título, etiqueta, subtítulo, rótulos, rodapé) e a paleta. Se o `modo` foi alterado, remove o `ag-theme` deste navegador (senão a escolha pessoal anulava a mudança) e reaplica a ordem da seção 5.5. Os outros navegadores mantêm a escolha deles.

**Paletas no CSS.** A Padrão continua sendo os blocos `:root` e `:root[data-theme="dark"]` atuais, sem atributo. Cada outra paleta é um par de blocos em `paletas.css`: `:root[data-palette="oceano"]` (claro) e `:root[data-palette="oceano"][data-theme="dark"]` (escuro). A paleta troca `--bg`, `--bg-grid`, `--panel`, `--ink`, `--muted`, `--line`, `--line-soft`, `--accent`, `--accent2`, `--accent-soft`, `--cite`, `--glass`, `--on-line` e os `--g-*` do grafo. Não troca os post-its (`--pi-*`), o bloco de código (`--code-*`), a marca da busca (`--hit-*`) nem `--danger`, que têm significado fixo.

## 8. Erros

| Situação | Comportamento |
|---|---|
| Campo inválido | Mensagem ao lado do campo, usando o `campo` que o servidor devolve em `Erro(..., campo=...)`; o cliente já checa os mesmos limites antes de enviar |
| 409 `conflito` | Faixa no topo do diálogo: recarregar os valores (perde as edições do painel) ou salvar mesmo assim (reenvia as mesmas alterações com a versão nova como base) |
| `config.json` quebrado | O diálogo abre em leitura com a linha e a coluna do erro; Salvar fica desabilitado até o arquivo ser corrigido |
| Falha ao gravar ou ao guardar a cópia | Mensagem curta; nada muda no arquivo |
| Servidor parou | `#cfg-btn` some junto com o `+` |
| Desfazer sem histórico | Botão desabilitado (o servidor também recusa com `sem_historico`) |

## 9. O que não muda

- Nenhuma rota existente muda de contrato. `salvar`, `nova` e post-its seguem iguais.
- O `config.json` editado à mão continua valendo; a primeira gravação pelo painel reformata o arquivo (recuo de 2 espaços, mesma ordem das chaves). JSON não tem comentários, então nada se perde.
- A paleta Padrão não muda nenhum pixel; o botão Claro/Escuro continua sendo escolha pessoal.
- O `style.css` não é editado nesta peça.
- Fora do modo de escrita (sem servidor), o site continua só de leitura, sem painel.

## 10. Testes

**Python** (`tests/test_config_api.py`, com o servidor temporário que os testes atuais usam; o `setUp` dos testes passa a apontar também o novo `TEMA_DADOS_JS_PATH`):

- Contrato: cada chave válida e inválida (tipo, tamanho, caracteres de caminho, enum); `null` remove; `rodape` com `""` e `null`; `raiz`, `prefixo_url`, `porta` e chaves desconhecidas recusadas; mesclagem de `textos` e `tema`; substituição de listas; chaves desconhecidas e ordem preservadas.
- Gravação: falha de `os.replace` deixa o original intacto; histórico poda em 20; desfazer restaura e pode ser desfeito; conflito 409; arquivo quebrado recusado sem alteração; CRLF preservado; BOM tolerado; arquivo ausente criado.
- Segurança HTTP: Host errado 403, Origin errado 403, `Content-Type` errado 415, corpo acima de 64 KB 413; fuzz curto sobre `valores` com tipos e valores hostis, exigindo zero exceção não tratada e nada escrito fora do `config.json` e de `dados/`.
- Sincronia: depois do POST, `content.js` e `tema-dados.js` já refletem a mudança; o carimbo muda.
- Paletas: `PALETAS` bate com os blocos de `paletas.css` nos dois modos, e vice-versa; contraste (abaixo).
- `tema-dados.js`: gerado com paleta e modo certos; valor fora da lista cai no padrão e gera aviso em `avisos_config()`.

**Régua de contraste.** Pares de texto que o CSS já usa: `ink/bg`, `ink/panel`, `muted/bg`, `muted/panel`, `accent/panel`, `accent2/panel`, `cite/panel`, `on-line/line`. O teste calcula a razão de cada par em cada paleta e modo e exige, por par, razão maior ou igual ao menor entre 4,5:1 e a razão da paleta Padrão no mesmo par. Ou seja: nenhuma paleta fica pior que a Padrão, e todas chegam a 4,5:1 onde a Padrão chega. Achado de partida: na Padrão clara, o par `accent`/`panel` mede 3,13:1, e o `accent` é cor de texto de 13 px em pelo menos duas regras do `style.css` (linhas 132 e 431), abaixo de 4,5:1; isso já existe e não é corrigido aqui (as paletas novas podem fazer melhor). O fundo exato de cada uso se confere na implementação. O teste da Padrão fixa os números de hoje para não piorarem.

**Node** (`tests/painel.test.js`, lógica pura): envio só com os campos alterados; rodapé padrão, ocultar e personalizado em `null`, `""` e texto; limites vindos do servidor; ordem de decisão do modo (pessoal, projeto, claro, e `sistema` por `matchMedia`); `localStorage` ausente ou bloqueado; paleta fora da lista ignorada.

**Ponta a ponta em jsdom**, como na verificação do `prefixo_url`: servidor real, abrir o painel, trocar título e paleta, salvar, conferir tela, arquivo e F5; conflito; arquivo quebrado.

**Fora do alcance dos testes** (dito de antemão): a aparência real num navegador e o Windows com OneDrive. Checklist visual para quem aprova, em cada uma das 5 paletas nos 2 modos: menu lateral, painel de configuração, grafo, quadro, post-its e bloco de código.

**Critérios de aceite:**

1. Uma pessoa troca nome e paleta pelo painel e vê o resultado ao salvar, sem F5.
2. Depois de gravar, o `config.json` mantém as chaves desconhecidas e as 3 somente leitura intactas.
3. Nenhuma rota consegue alterar `raiz`, `prefixo_url` ou `porta`.
4. As 5 paletas nos 2 modos passam na régua de contraste.
5. A suíte inteira passa, mais a verificação em jsdom, e o checklist visual é passado por uma pessoa.

## 11. Documentação (parte do critério de pronto)

- `LEIA-ME.md`: seção "Painel de configurações" (o que edita, o que é somente leitura e por quê, desfazer, as paletas); a tabela do `config.json` ganha `tema`; nota de que `tema-dados.js` é o terceiro arquivo gerado, para o `.gitignore`.
- `config.json` de exemplo: acrescentar `"tema": {"paleta": "padrao", "modo": "claro"}`.
- Esta spec, com a seção 12 atualizada ao entregar.

## 12. Decisões e premissas

- `raiz`, `prefixo_url` e `porta` ficam só no arquivo (segurança, seção 2). Decisão do usuário: aprovado.
- Com o `config.json` quebrado, o painel recusa gravar e mostra o erro; não recria o arquivo. Decisão do usuário: aprovado.
- Só paletas prontas na v1; cor livre fica para depois. Decisão do usuário: aprovado.
- "Seguir o sistema" faz parte do modo inicial. Aprovado.
- Salvar com `modo` alterado limpa a escolha pessoal do navegador atual, para a mudança aparecer.
- A lógica de tema fica em `tema.js` (escrito à mão e testável) e só os dados vão no arquivo gerado `tema-dados.js`; o script inline do `<head>` é substituído.
- O histórico do `config.json` usa pasta própria (`dados/config-historico/`), para nunca colidir com o histórico de uma nota chamada `config`.
- O `Erro` existente já aceita campos extras, então `campo` não exige mudança nele.
- A régua de contraste usa a paleta Padrão como piso, porque a Padrão atual não cumpre 4,5:1 em todos os pares (seção 10).
- Não verificado: a aparência real das paletas num navegador e o Windows com OneDrive. O contraste das 4 paletas novas foi medido (mínimo de 4,71:1 nos pares da régua; a Padrão clara tem `accent`/`panel` em 3,13:1 e segue assim).

### Decisões tomadas na implementação

- `GET /api/config` ganhou `historico` (quantas versões anteriores o Desfazer tem), para a tela desabilitar o botão sem tentar.
- A amostra de cor das paletas é a própria prévia ao vivo, e não miniaturas (seção 7).
- `configedit.py` ficou separado do `agwrite.py` (lógica pura, sem arquivo); `painel.css` existe porque o `style.css` não é editado; `AG_TEMA` leva a lista `paletas`.
- `agTexto` passou a ler uma variável substituível (`agDefinirTextos`), e o app guarda os textos originais do `index.html` antes de aplicar qualquer configuração, para "restaurar padrão" valer sem recarregar.
- Dois problemas achados por teste e corrigidos: um título com "\ud800" (caractere solto que o JSON aceita) passava na validação e estourava ao gravar em UTF-8, depois da cópia de segurança; e um JSON com milhares de `[` aninhados derrubava qualquer rota POST com erro 500 (agora 400).
