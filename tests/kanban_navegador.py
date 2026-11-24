"""Teste de navegador do quadro Kanban: colunas, mover por seletor e por arrastar, itens de checklist, mudança
por fora, conflito, Nova nota com status, somente leitura e acessibilidade.

Precisa de: pip install playwright && playwright install chromium (só para este teste).
Uso: python3 tests/kanban_navegador.py

Roda numa CÓPIA da pasta do projeto, com um serve.py próprio em porta livre: os arquivos reais não são tocados.
As capturas de tela ficam em /tmp/ag-telas (mude com AG_TELAS=pasta).
"""

import os as _os, sys as _sys
if not _os.path.isdir(_os.path.join(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))), "01-Visao-e-Negocio")):
    print("PULADO: este teste usa os documentos do projeto de origem (pasta 01-Visao-e-Negocio/), que não vêm neste zip.")
    _sys.exit(77)

import json
import os
import shutil

from playwright.sync_api import expect, sync_playwright

from _navegador import (RAIZ, TELAS, abrir, confere, contraste, copiar, escrever, escrita_ligada, fim, ler,
                        porta_livre, subir)

IDEIA = "01-Visao-e-Negocio/ideia-a.md"
TAREFA = "01-Visao-e-Negocio/tarefa-b.md"
REVISAR = "06-Financeiro/revisar.md"


def cartao(page, chave):
    return page.locator(f'.kb-cartao[data-chave="{chave}"]')


def colunas(page):
    return page.locator(".kb-col h3").all_inner_texts()


def na_coluna(page, rotulo):
    return page.locator(f'.kb-col:has(h3:text-is("{rotulo}")) .kb-cartao').evaluate_all("e => e.map(x => x.dataset.chave)")


def arrastar(page, chave, rotulo):
    """Arraste REAL, com o mouse: segura o cartão, leva o mouse até a borda do quadro (ele rola sozinho durante o
    arraste) até uma parte da coluna de destino aparecer, e solta nela. Funciona com o quadro rolado e com a coluna
    de destino fora da tela; o drag_and_drop do Playwright erra o alvo nesses casos porque rola no meio do arraste."""
    li = cartao(page, chave)
    li.scroll_into_view_if_needed()
    box = li.bounding_box()
    page.mouse.move(box["x"] + box["width"] / 2, box["y"] + 25)  # parte de cima do cartão, longe do seletor
    page.mouse.down()
    for i in range(1, 8):  # começa o arraste
        page.mouse.move(box["x"] + box["width"] / 2 + i * 10, box["y"] + 25 + i * 5)
    quadro = page.locator(".kb-colunas").bounding_box()
    col = page.locator(f'.kb-col:has(h3:text-is("{rotulo}"))')
    e, d = quadro["x"], quadro["x"] + quadro["width"]
    for _ in range(300):
        c = col.bounding_box()
        visivel = min(c["x"] + c["width"], d) - max(c["x"], e)  # parte da coluna de destino que já aparece
        if visivel >= 120:
            break
        page.mouse.move(d - 8 if c["x"] > e else e + 8, quadro["y"] + 300)  # perto da borda, para o quadro rolar
        page.wait_for_timeout(40)
    c = col.bounding_box()
    page.mouse.move((max(c["x"], e) + min(c["x"] + c["width"], d)) / 2, quadro["y"] + 300, steps=5)
    page.mouse.up()


def abrir_quadro(page):
    if not page.locator("#kb-view").is_visible():
        page.click("#kb-btn")
    expect(page.locator("#kb-view")).to_be_visible()


def main():
    os.makedirs(TELAS, exist_ok=True)
    tmp, dest = copiar()
    porta = porta_livre()
    base = f"http://localhost:{porta}/"
    escrever(dest, IDEIA, "---\ntags: [dados, ons]\nstatus: Ideia\n---\n# Ideia A\n\n- [ ] item da nota\n")
    escrever(dest, TAREFA, "---\ntags: [clientes]\nstatus: Fazendo\n---\n# Tarefa B\n")
    escrever(dest, REVISAR, "---\nstatus: Em revisão\n---\n# Revisar orçamento\n")
    srv = subir(dest, porta)  # o servidor sincroniza ao subir: content.js da cópia já traz as três notas
    try:
        with sync_playwright() as p:
            b = p.chromium.launch()
            ctx = b.new_context(viewport={"width": 1280, "height": 900})
            page = ctx.new_page()
            erros = []
            page.on("pageerror", lambda e: erros.append(str(e)))
            page.on("dialog", lambda d: d.accept())

            print("1. Sem servidor o quadro só lê")
            leitura = b.new_page(viewport={"width": 1280, "height": 900})
            leitura.goto("file://" + os.path.join(dest, "site", "index.html"))
            leitura.wait_for_selector(".item-btn")
            leitura.click("#kb-btn")
            expect(leitura.locator("#kb-view")).to_be_visible()
            confere(colunas(leitura) == ["A fazer", "Em progresso", "Em revisão", "Fazendo", "Ideia"], "file://: colunas certas, com Feito escondida")
            leitura.fill(".kb-busca", "orientador")
            confere(colunas(leitura)[-1] == "Feito", "file://: buscando, a coluna Feito aparece")
            confere(leitura.locator(".kb-mover").count() == 0 and leitura.locator('.kb-cartao[draggable="true"]').count() == 0,
                    "file://: sem seletor e sem arrastar")
            confere("Somente leitura" in leitura.inner_text("#kb-view"), "file://: avisa que é somente leitura")
            leitura.close()

            print("2. Colunas e cartões")
            abrir(page, base)
            escrita_ligada(page)
            page.click("#kb-btn")
            expect(page.locator("#kb-view")).to_be_visible()
            confere(colunas(page) == ["A fazer", "Em progresso", "Em revisão", "Fazendo", "Ideia"], "colunas: A fazer, Em progresso, as outras em ordem alfabética; Feito escondida")
            confere(na_coluna(page, "Em progresso") == [] and page.locator(".kb-dica:not([hidden]), .kb-leitura:not([hidden])").count() == 0, "Em progresso existe vazia e não há aviso de feitos ocultos (nenhum feito ainda)")
            confere(page.get_attribute("#kb-btn", "aria-pressed") == "true", "botão Quadro fica pressionado")
            confere(not page.locator("#content").is_visible(), "o documento some enquanto o quadro está aberto")
            nota = cartao(page, "n:" + IDEIA)
            confere(nota.locator(".kb-titulo").inner_text() == "Ideia A" and nota.locator(".kb-tag").count() == 2
                    and "01-Visao-e-Negocio" in nota.locator(".kb-origem").inner_text(), "cartão de nota: título, tags e pasta")
            item = page.locator(".kb-cartao.kb-item").first
            confere("Bem-vindo" in item.locator(".kb-origem").inner_text(), "cartão de item: documento de origem")
            confere(page.evaluate("document.documentElement.scrollWidth <= document.documentElement.clientWidth"), "o quadro não cria rolagem horizontal na página")
            confere(page.locator('.kb-col[role="group"]').count() == 5 and page.locator(".kb-col[aria-labelledby]").count() == 5, "cada coluna é um grupo com nome")
            confere(page.get_attribute(".kb-busca", "aria-label") == "Buscar no quadro", "o campo de busca tem nome acessível")
            n_itens = page.locator(".kb-item").count()
            confere(n_itens == 62 and na_coluna(page, "Ideia") == ["n:" + IDEIA], f"{n_itens} itens de checklist (61 dos documentos + 1 da nota) e a nota em Ideia")
            page.screenshot(path=f"{TELAS}/k1-quadro.png")

            print("3. Mover nota pelo seletor")
            antes = ler(dest, IDEIA)
            sel = nota.locator("select")
            confere(sel.evaluate("e => e.options[0].text") == "Mover para…" and sel.evaluate("e => [...e.options].find(o => o.value === 'ideia').disabled"), "seletor: a coluna atual fica desabilitada")
            sel.focus()
            sel.select_option("fazendo")
            expect(page.locator("#kb-view [role=status]")).to_have_text("Movido para Fazendo.", timeout=5000)
            depois = ler(dest, IDEIA)
            dif = [(a, c) for a, c in zip(antes.split("\n"), depois.split("\n")) if a != c]
            confere(dif == [("status: Ideia", "status: Fazendo")] and len(antes.split("\n")) == len(depois.split("\n")), "o .md muda só na linha do status")
            hist = os.path.join(dest, ".historico", "01-Visao-e-Negocio", "ideia-a")
            confere(os.path.isdir(hist) and len(os.listdir(hist)) == 1, "cópia da versão anterior em .historico/")
            confere("n:" + IDEIA in na_coluna(page, "Fazendo"), "o cartão passa para a coluna Fazendo")
            confere(page.evaluate("document.activeElement.tagName + ':' + !!document.activeElement.closest('[data-chave=\"n:%s\"]')" % IDEIA) == "SELECT:true", "o foco volta ao seletor do cartão movido")
            confere("Ideia" in colunas(page) and na_coluna(page, "Ideia") == [], "a coluna esvaziada continua, para poder devolver o cartão")
            cartao(page, "n:" + IDEIA).locator("select").select_option("ideia")
            expect(page.locator("#kb-view [role=status]")).to_have_text("Movido para Ideia.", timeout=5000)
            confere("status: Ideia" in ler(dest, IDEIA), "devolver o cartão à coluna vazia funciona")

            print("4. Mover nota arrastando")
            arrastar(page, "n:" + TAREFA, "Em revisão")
            expect(page.locator("#kb-view [role=status]")).to_have_text("Movido para Em revisão.", timeout=5000)
            confere("status: Em revisão" in ler(dest, TAREFA), "arrastar grava o status com o rótulo da coluna de destino")
            confere("n:" + TAREFA in na_coluna(page, "Em revisão"), "o cartão aparece na coluna nova")

            print("5. Itens de checklist")
            chave = "i:INICIO.md:" + str(next(i for i, l in enumerate(ler(dest, "INICIO.md").split("\n")) if "Orientador" in l))
            antes = ler(dest, "INICIO.md")
            cartao(page, chave).locator("select").select_option("feito")
            expect(page.locator("#kb-view [role=status]")).to_have_text("Movido para Feito.", timeout=5000)
            depois = ler(dest, "INICIO.md")
            dif = [(a, c) for a, c in zip(antes.split("\n"), depois.split("\n")) if a != c]
            confere(len(dif) == 1 and dif[0][1] == dif[0][0].replace("- [ ]", "- [x]"), "item para Feito: só a caixa muda no .md")
            confere(cartao(page, chave).count() == 0 and "1 cartão feito oculto" in page.inner_text("#kb-view"), "o item some do quadro e o aviso conta 1 cartão feito oculto")
            page.fill(".kb-busca", "Orientador do PPgCTI")  # buscando, a coluna Feito aparece
            page.wait_for_selector('.kb-col:has(h3:text-is("Feito"))')
            confere(chave in na_coluna(page, "Feito") and "1 encontrado" in page.inner_text("#kb-view"), "buscando, o item aparece na coluna Feito")
            opcoes = cartao(page, chave).locator("select").evaluate("e => [...e.options].filter(o => o.disabled).map(o => o.text)")
            confere(opcoes == ["Em progresso", "Em revisão", "Fazendo", "Ideia", "Feito (atual)"], "item: Em progresso e colunas personalizadas desabilitadas no seletor")
            arrastar(page, chave, "A fazer")
            expect(page.locator("#kb-view [role=status]")).to_have_text("Movido para A fazer.", timeout=5000)
            confere(ler(dest, "INICIO.md") == antes, "item arrastado de volta para A fazer: o .md volta ao original")
            page.fill(".kb-busca", "")
            confere(page.locator('.kb-col h3:text-is("Feito")').count() == 0, "apagando a busca, a coluna Feito some de novo")
            arrastar(page, chave, "Fazendo")
            expect(page.locator("#kb-view")).to_contain_text("Itens de checklist só ficam em A fazer ou Feito.")
            page.wait_for_timeout(500)
            confere(ler(dest, "INICIO.md") == antes and chave in na_coluna(page, "A fazer"), "item solto em coluna personalizada: recusado, nada gravado")
            confere(page.locator(".kb-col.kb-alvo").count() == 0, "a coluna que recusa não se destaca")
            arrastar(page, chave, "Em progresso")
            expect(page.locator("#kb-view")).to_contain_text("Itens de checklist só ficam em A fazer ou Feito.")
            confere(ler(dest, "INICIO.md") == antes, "item solto em Em progresso: recusado (o .md não guarda esse estado)")
            arrastar(page, chave, "Feito")  # Feito está escondida: aparece como zona de soltura durante o arraste
            page.wait_for_timeout(500)
            confere(ler(dest, "INICIO.md").count("- [x]") == antes.count("- [x]") + 1, "arraste de item para a zona Feito (escondida) grava a caixa")
            confere(page.locator(".kb-zona").count() == 0 and "1 cartão feito oculto" in page.inner_text("#kb-view"), "a zona some depois da soltura e o aviso conta o feito")
            page.fill(".kb-busca", "Orientador do PPgCTI")
            arrastar(page, chave, "A fazer")
            page.wait_for_timeout(500)
            confere(ler(dest, "INICIO.md") == antes, "e de volta para A fazer")
            page.fill(".kb-busca", "")
            # dois movimentos seguidos
            c2 = [f"i:INICIO.md:{i}" for i, l in enumerate(antes.split("\n")) if l.startswith("- [ ]")][:2]
            cartao(page, c2[0]).locator("select").select_option("feito")
            cartao(page, c2[1]).locator("select").select_option("feito")
            page.wait_for_timeout(1500)
            confere(ler(dest, "INICIO.md").count("- [x]") == antes.count("- [x]") + 2, "dois movimentos seguidos gravam os dois")
            page.screenshot(path=f"{TELAS}/k2-movido.png")

            print("5b. Em progresso e busca")
            cartao(page, "n:" + IDEIA).locator("select").select_option("em progresso")
            expect(page.locator("#kb-view [role=status]")).to_have_text("Movido para Em progresso.", timeout=5000)
            confere("status: Em progresso" in ler(dest, IDEIA) and "n:" + IDEIA in na_coluna(page, "Em progresso"), "nota para Em progresso: grava status: Em progresso e aparece na coluna fixa")
            confere(page.locator('.kb-col h3:text-is("Ideia")').count() == 1 and na_coluna(page, "Ideia") == [], "a coluna Ideia, esvaziada, continua")
            page.fill(".kb-busca", "clientes")
            confere(na_coluna(page, "Em revisão") == ["n:" + TAREFA], "a busca filtra por tag: só a Tarefa B, que está em Em revisão")
            confere(all(len(na_coluna(page, r)) == 0 for r in ("A fazer", "Em progresso")) and "1 encontrado" in page.inner_text("#kb-view"), "as outras colunas ficam vazias e a contagem diz 1 encontrado")
            page.fill(".kb-busca", "à fazer")
            confere(len(na_coluna(page, "A fazer")) > 50, "a busca pelo nome da coluna ignora acento (mostra tudo de A fazer)")
            page.fill(".kb-busca", "feito")
            page.wait_for_selector('.kb-col:has(h3:text-is("Feito"))')
            confere(len(na_coluna(page, "Feito")) == 2, "buscar 'feito' mostra a coluna Feito com os 2 itens que foram concluídos antes")
            page.fill(".kb-busca", "zzzz-nada")
            confere("0 encontrados" in page.inner_text("#kb-view") and page.locator(".kb-col").count() == 6, "sem resultado: todas as colunas continuam, vazias")
            page.fill(".kb-busca", "")
            page.screenshot(path=f"{TELAS}/k2b-progresso.png")

            print("6. Mudança por fora redesenha o quadro")
            escrever(dest, REVISAR, "---\nstatus: Fazendo\n---\n# Revisar orçamento\n")
            page.wait_for_function("(c) => document.querySelector(`.kb-col:has(h3) [data-chave='${c}']`)?.closest('.kb-col').querySelector('h3').textContent === 'Fazendo'",
                                   arg="n:" + REVISAR, timeout=7000)
            confere(True, "nota editada por fora muda de coluna sozinha")
            escrever(dest, "06-Financeiro/nova-por-fora.md", "---\nstatus: Bloqueado\n---\n# Bloqueada\n")
            page.wait_for_selector('.kb-col h3:text-is("Bloqueado")', timeout=7000)
            confere(True, "status novo, criado por fora, vira coluna")

            print("7. Conflito")
            versao = page.evaluate("fetch('/api/versao').then(r => r.json())")
            page.route("**/api/versao", lambda r: r.fulfill(status=200, content_type="application/json", body=json.dumps(versao)))
            escrever(dest, TAREFA, "---\nstatus: Em progresso\n---\n# Mudou sem a página saber\n")
            os.utime(os.path.join(dest, TAREFA), ns=(2_000_000_000_000_000_000,) * 2)
            cartao(page, "n:" + TAREFA).locator("select").select_option("bloqueado")
            expect(page.locator("#kb-view [role=alert]")).to_contain_text("mudou por fora", timeout=5000)
            confere(ler(dest, TAREFA) == "---\nstatus: Em progresso\n---\n# Mudou sem a página saber\n", "conflito: nada foi gravado")
            page.wait_for_selector(f'.kb-col:has(h3:text-is("Em progresso")) [data-chave="n:{TAREFA}"]', timeout=5000)
            confere("n:" + TAREFA not in na_coluna(page, "Bloqueado"), "conflito: o cartão não vai para a coluna pedida; o quadro mostra o que o arquivo diz")
            page.unroute("**/api/versao")
            page.wait_for_function("(c) => document.querySelector(`[data-chave='${c}']`)?.closest('.kb-col').querySelector('h3').textContent === 'Em progresso'",
                                   arg="n:" + TAREFA, timeout=7000)
            confere(True, "conflito: o quadro se atualiza e mostra o cartão onde o arquivo diz")

            print("8. Nova nota com status, barra Ctrl+K")
            page.keyboard.press("Control+k")
            page.keyboard.type("quadro")
            expect(page.locator(".ag-op")).to_have_count(1)
            page.keyboard.press("Escape")
            page.click("#ag-plus")
            page.keyboard.type("nova")
            page.keyboard.press("Enter")
            expect(page.locator(".ag-nova")).to_be_visible()
            opcoes = page.locator("#ag-status-lista option").evaluate_all("e => e.map(x => x.value)")
            confere(opcoes[:2] == ["A fazer", "Em progresso"] and opcoes[-1] == "Feito" and "Bloqueado" in opcoes, "Status: as colunas existentes vêm como sugestão")
            page.fill(".ag-nova label:has-text('Título') input", "Cartão criado pelo painel")
            page.fill(".ag-nova label:has-text('Status') input", "Revisão final")
            confere("status: Revisão final" in page.inner_text(".ag-previa"), "Status: a prévia mostra a linha status")
            page.locator(".ag-nova textarea").focus()
            page.keyboard.press("Control+Enter")
            expect(page.locator(".ag-fundo")).to_have_count(0, timeout=5000)
            confere("status: Revisão final" in ler(dest, "cartao-criado-pelo-painel.md"), "a nota nasce com status no frontmatter")
            expect(page.locator("#content h1")).to_have_text("Cartão criado pelo painel", timeout=5000)
            confere(not page.locator("#kb-view").is_visible(), "abrir um documento fecha o quadro")
            page.keyboard.press("Control+k")
            page.keyboard.type("abrir o quadro")
            page.keyboard.press("Enter")
            expect(page.locator("#kb-view")).to_be_visible()
            confere("Revisão final" in colunas(page), "a coluna nova aparece no quadro")
            page.click("#graph-btn")
            confere(not page.locator("#kb-view").is_visible() and page.evaluate("document.body.classList.contains('graph-open')"), "abrir o grafo fecha o quadro")
            page.click("#graph-btn")
            abrir_quadro(page)

            print("9. Tabela de erros do spec")
            alerta = page.locator("#kb-view [role=alert]")
            # falha ao gravar (disco, permissão, cópia): mensagem do servidor, cartão no lugar
            page.route("**/api/salvar", lambda r: r.fulfill(status=500, content_type="application/json",
                                                             body=json.dumps({"erro": "Não foi possível gravar o arquivo.", "codigo": "gravar"})))
            antes = ler(dest, IDEIA)
            cartao(page, "n:" + IDEIA).locator("select").select_option("bloqueado")
            expect(alerta).to_have_text("Não foi possível gravar o arquivo. O cartão não foi movido.", timeout=5000)
            confere(ler(dest, IDEIA) == antes and "n:" + IDEIA in na_coluna(page, "Em progresso"), "falha ao gravar: mensagem do servidor e o cartão fica no lugar")
            page.unroute("**/api/salvar")
            # o cartão não bate mais com a linha do arquivo: cancela sem nem tentar gravar
            page.evaluate("window.__salvos = 0; const f = window.fetch; window.fetch = (u, o) => { if (String(u).includes('salvar')) window.__salvos++; return f(u, o); }")
            linha51 = next(i for i, l in enumerate(ler(dest, "INICIO.md").split("\n")) if l.startswith("- [ ]"))  # um item ainda em A fazer
            page.evaluate("() => { const d = docList().find((x) => x.file === 'INICIO.md'); d.fallback = 'linha nova no topo\\n' + d.fallback; }")
            antes_inicio = ler(dest, "INICIO.md")
            cartao(page, f"i:INICIO.md:{linha51}").locator("select").select_option("feito")
            expect(alerta).to_have_text("O arquivo mudou por fora. O cartão não foi movido.", timeout=5000)
            confere(page.evaluate("window.__salvos") == 0 and ler(dest, "INICIO.md") == antes_inicio, "cartão que não bate com a linha: nada é gravado")
            page.wait_for_function("(c) => document.querySelector(`[data-chave='${c}']`)?.closest('.kb-col').querySelector('h3').textContent === 'A fazer'", arg=f"i:INICIO.md:{linha51}", timeout=5000)
            confere(True, "e o quadro se atualiza com o que o arquivo diz")
            # status inválido na Nova nota: erro no campo Status
            page.keyboard.press("Control+k")
            page.keyboard.type("nova")
            page.keyboard.press("Enter")
            expect(page.locator(".ag-nova")).to_be_visible()
            page.evaluate("document.querySelector('.ag-nova input[list]').removeAttribute('maxlength')")  # o campo já limita; força o erro do servidor
            page.fill(".ag-nova label:has-text('Título') input", "Status longo demais")
            page.fill(".ag-nova label:has-text('Status') input", "x" * 45)
            page.keyboard.press("Control+Enter")
            expect(page.locator("#ag-erro-status")).to_contain_text("até 40 caracteres", timeout=5000)
            confere(page.get_attribute("#ag-erro-status", "role") == "alert" and page.locator(".ag-nova").is_visible()
                    and not os.path.exists(os.path.join(dest, "status-longo-demais.md")), "status inválido: erro no campo Status (role=alert), nada criado, o painel continua aberto")
            page.keyboard.press("Escape")
            # nome que o Windows não aceita
            page.keyboard.press("Control+k")
            page.keyboard.type("nova")
            page.keyboard.press("Enter")
            page.fill(".ag-nova label:has-text('Título') input", "NUL")
            page.keyboard.press("Control+Enter")
            expect(page.locator("#ag-erro-titulo")).to_contain_text("Windows", timeout=5000)
            confere(not os.path.exists(os.path.join(dest, "nul.md")), "nome reservado do Windows: erro no campo título, nada criado")
            page.keyboard.press("Escape")

            print("10. Teclado, servidor parado, acessibilidade")
            page.locator(".kb-cartao .kb-titulo").first.focus()
            page.keyboard.press("Tab")
            confere(page.evaluate("document.activeElement.tagName") == "SELECT", "Tab do título chega ao seletor do cartão (mesmo escondido)")
            page.evaluate("document.activeElement.blur()")
            alturas = page.eval_on_selector_all(".kb-mover, .kb-titulo, .kb-origem", "e => e.map(x => x.getBoundingClientRect().height)")
            confere(min(alturas) >= 44, f"seletor e links com pelo menos 44 px (mín. {min(alturas):.0f})")
            for tema in ("claro", "escuro"):
                if tema == "escuro":
                    page.click("#theme-btn")
                for sel in (".kb-origem", ".kb-tag", ".kb-n", ".kb-texto", ".kb-titulo"):
                    c = contraste(page, sel, ".kb-cartao") if sel not in (".kb-n",) else contraste(page, sel, ".kb-col")
                    confere(c >= 4.5, f"tema {tema}: {sel} com contraste {c:.2f}:1")
                page.screenshot(path=f"{TELAS}/k3-quadro-{tema}.png")
            page.click("#theme-btn")
            srv.terminate(); srv.wait()
            expect(page.locator(".kb-mover").first).to_have_count(0, timeout=7000)
            confere(page.locator(".kb-mover").count() == 0 and "Somente leitura" in page.inner_text("#kb-view"), "servidor parado: seletor some e avisa somente leitura")
            expect(alerta).to_have_text("O servidor não responde. O site voltou ao modo leitura e tenta de novo sozinho.")
            confere(True, "servidor parado: o aviso de saída aparece também com o quadro aberto")
            srv = subir(dest, porta)
            expect(page.locator(".kb-mover").first).to_be_visible(timeout=9000) if False else page.wait_for_selector(".kb-mover", state="attached", timeout=9000)
            confere(page.locator(".kb-leitura").is_hidden() and alerta.inner_text() == "", "servidor de volta: os controles voltam e o aviso some")
            ctx_reduzido = b.new_context(viewport={"width": 390, "height": 800}, has_touch=True, is_mobile=True)
            pc = ctx_reduzido.new_page()
            pc.goto(base + "site/index.html")
            pc.wait_for_selector(".item-btn", state="attached")  # no celular a lista de documentos começa recolhida
            pc.evaluate("document.querySelector('#kb-btn').click()")
            pc.wait_for_selector(".kb-mover", state="attached")  # o seletor só existe depois que a escrita é detectada
            confere(pc.evaluate("getComputedStyle(document.querySelector('.kb-mover')).opacity") == "1", "toque: o seletor fica sempre visível")
            pc.screenshot(path=f"{TELAS}/k4-quadro-celular.png")
            ctx_reduzido.close()
            confere(not erros, "nenhum erro de JavaScript na página" + ("" if not erros else ": " + erros[0]))
            b.close()
    finally:
        srv.terminate()
        shutil.rmtree(tmp, ignore_errors=True)
    fim()


main()
