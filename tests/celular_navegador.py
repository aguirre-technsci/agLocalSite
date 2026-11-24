"""Teste de navegador do celular (390 px): menu recolhível, nenhum documento estoura a largura, quadro logo abaixo dos botões.

Precisa de: pip install playwright && playwright install chromium (só para este teste).
Uso: python3 tests/celular_navegador.py

Roda numa CÓPIA da pasta do projeto, com um serve.py próprio em porta livre: os arquivos reais não são tocados.
"""

import os as _os, sys as _sys
if not _os.path.isdir(_os.path.join(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))), "01-Visao-e-Negocio")):
    print("PULADO: este teste usa os documentos do projeto de origem (pasta 01-Visao-e-Negocio/), que não vêm neste zip.")
    _sys.exit(77)

import os
import shutil

from playwright.sync_api import expect, sync_playwright

from _navegador import TELAS, confere, copiar, escrita_ligada, fim, porta_livre, subir


def main():
    os.makedirs(TELAS, exist_ok=True)
    tmp, dest = copiar()
    porta = porta_livre()
    base = f"http://localhost:{porta}/"
    srv = subir(dest, porta)
    try:
        with sync_playwright() as p:
            b = p.chromium.launch()
            ctx = b.new_context(viewport={"width": 390, "height": 800}, has_touch=True, is_mobile=True)
            page = ctx.new_page()
            page.goto(base + "site/index.html")
            page.wait_for_selector(".item-btn", state="attached")
            escrita_ligada(page)

            print("1. Menu recolhível")
            confere(page.locator("#menu-btn").is_visible() and page.get_attribute("#menu-btn", "aria-expanded") == "false", "botão Menu visível e fechado")
            confere(not page.locator("#tree").is_visible(), "a lista de documentos começa recolhida")
            topo = page.evaluate("document.querySelector('#content h1').getBoundingClientRect().top")
            confere(topo < 500, f"o título do documento aparece na primeira tela (topo em {topo:.0f} px de 800)")
            page.screenshot(path=f"{TELAS}/c1-celular-inicio.png")
            page.click("#menu-btn")
            confere(page.locator("#tree").is_visible() and page.get_attribute("#menu-btn", "aria-expanded") == "true", "tocar em Menu abre a lista")
            page.locator(".group-label", has_text="Visão e Negócio").click()
            page.locator(".item-btn", has_text="Modelo de Negócio").click()
            expect(page.locator("#content h1")).to_have_text("Modelo de Negócio", timeout=5000)
            confere(not page.locator("#tree").is_visible(), "escolher um documento recolhe o menu")
            confere(page.evaluate("scrollY") == 0, "e abre o documento no topo")

            print("2. Nenhum documento estoura a largura")
            ids = page.evaluate("[...document.querySelectorAll('.item-btn')].map(b => b.dataset.id)")
            ruins = []
            for i in ids:
                page.goto(base + "site/index.html#" + i)
                page.wait_for_function("id => document.querySelector('.item-btn.active')?.dataset.id === id && !document.getElementById('content').textContent.startsWith('Carregando')", arg=i)
                w = page.evaluate("document.documentElement.scrollWidth")  # contra 390 fixo: a janela móvel cresce para caber o conteúdo
                if w > 390:
                    ruins.append((i, w))
            confere(not ruins, f"nenhum dos {len(ids)} documentos passa da largura da tela" + (f": {ruins[:3]}" if ruins else ""))
            confere(page.evaluate("innerWidth") == 390, "a página segue com 390 px, sem zoom para caber")

            print("3. Quadro logo abaixo dos botões")
            page.goto(base + "site/index.html#inicio")
            page.wait_for_selector(".item-btn", state="attached")
            page.click("#menu-btn")
            page.click("#kb-btn")
            expect(page.locator("#kb-view")).to_be_visible()
            confere(not page.locator("#tree").is_visible(), "abrir o quadro recolhe o menu")
            topo = page.evaluate("document.querySelector('#kb-view').getBoundingClientRect().top")
            confere(abs(topo) < 60, f"o quadro começa no topo da tela (em {topo:.0f} px)")
            confere(page.evaluate("document.documentElement.scrollWidth") <= 390, "o quadro não estoura a largura")
            page.screenshot(path=f"{TELAS}/c2-celular-quadro.png")
            page.click("#kb-btn")
            expect(page.locator("#kb-view")).to_be_hidden()
            b.close()
    finally:
        srv.terminate()
        shutil.rmtree(tmp, ignore_errors=True)
    fim()


main()
