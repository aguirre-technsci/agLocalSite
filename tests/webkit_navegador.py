"""Teste de fumaça no WebKit (o motor do Safari), via WebKitGTK + Selenium: a escrita, o quadro e o layout do celular.

O Playwright baixa o WebKit de um CDN que nem sempre está liberado; o WebKitGTK vem do gerenciador de pacotes.
Precisa de (Ubuntu/Debian): apt install webkit2gtk-driver xvfb libwebkit2gtk-4.1-0 && pip install selenium
Uso: python3 tests/webkit_navegador.py   (sobe um Xvfb sozinho se não houver DISPLAY)

Roda numa CÓPIA da pasta do projeto, com um serve.py próprio em porta livre: os arquivos reais não são tocados.
Cobre o que dá para dirigir de fora: o arraste HTML5 não é simulável por este driver, então o movimento de
cartões é testado pelo seletor "Mover para…".
"""

import os as _os, sys as _sys
if not _os.path.isdir(_os.path.join(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))), "01-Visao-e-Negocio")):
    print("PULADO: este teste usa os documentos do projeto de origem (pasta 01-Visao-e-Negocio/), que não vêm neste zip.")
    _sys.exit(77)

import os
import shutil
import subprocess
import sys
import time

from _navegador import TELAS, confere, copiar, escrever, fim, ler, porta_livre, subir

MINIBROWSER = "/usr/lib/x86_64-linux-gnu/webkit2gtk-4.1/MiniBrowser"

try:
    from selenium import webdriver
    from selenium.webdriver import ActionChains, Keys
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.webkitgtk.options import Options
except ImportError:
    sys.exit("Falta o selenium: pip install selenium")
if not os.path.exists(MINIBROWSER) or not shutil.which("WebKitWebDriver"):
    sys.exit("Falta o WebKitGTK: apt install webkit2gtk-driver xvfb libwebkit2gtk-4.1-0")


def esperar(d, cond, msg, tempo=8):
    try:
        WebDriverWait(d, tempo, poll_frequency=0.1).until(cond)
        return True
    except Exception:
        return False


def css(d, seletor):
    return d.find_element(By.CSS_SELECTOR, seletor)


def visivel(d, seletor):
    return d.execute_script("const e = document.querySelector(arguments[0]); return !!e && !e.hidden && getComputedStyle(e).display !== 'none' && e.getClientRects().length > 0;", seletor)


def colunas_do_quadro(d):
    # por JavaScript: o .text do Selenium recusa elementos cortados pela rolagem horizontal do quadro
    return d.execute_script("return [...document.querySelectorAll('.kb-col h3')].map((h) => h.textContent)")


def mover_por_seletor(d, cartao_css, valor):
    """Escolhe a coluna no seletor do cartão. Define o valor e dispara o 'change', que é o que o navegador faz: o menu
    nativo do select não é dirigível por este driver (e o seletor só aparece com o mouse em cima)."""
    seletor = css(d, cartao_css).find_element(By.CSS_SELECTOR, "select")
    d.execute_script("arguments[0].value = arguments[1]; arguments[0].dispatchEvent(new Event('change', { bubbles: true }));", seletor, valor)


def atalho(d, letra, *extra):
    a = ActionChains(d).key_down(Keys.CONTROL).send_keys(letra).key_up(Keys.CONTROL)
    a.perform()


def main():
    xvfb = None
    if not os.environ.get("DISPLAY"):
        xvfb = subprocess.Popen(["Xvfb", ":97", "-screen", "0", "1280x900x24"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        os.environ["DISPLAY"] = ":97"
        time.sleep(1.5)
    os.makedirs(TELAS, exist_ok=True)
    tmp, dest = copiar()
    porta = porta_livre()
    base = f"http://localhost:{porta}/"
    escrever(dest, "01-Visao-e-Negocio/ideia-a.md", "---\ntags: [dados]\nstatus: Ideia\n---\n# Ideia A\n\n- [ ] item da nota\n")
    srv = subir(dest, porta)
    o = Options()
    o.binary_location = MINIBROWSER
    o.add_argument("--automation")
    d = webdriver.WebKitGTK(options=o)
    try:
        d.set_window_size(1280, 900)
        print("motor:", d.execute_script("return navigator.userAgent").split(") ")[1])

        print("1. Escrita ligada")
        d.get(base + "site/index.html#inicio")
        confere(esperar(d, lambda x: visivel(x, "#ag-plus"), ""), "o servidor com escrita é detectado (botão + aparece)")
        confere(esperar(d, lambda x: x.execute_script("return !!document.querySelector('#content h1')"), ""), "o documento abre")
        confere(d.execute_script("return document.documentElement.scrollWidth <= innerWidth"), "sem rolagem horizontal em 1280 px")

        print("2. Barra Ctrl+K e Nova nota com status")
        css(d, "#content h1").click()
        atalho(d, "k")
        confere(esperar(d, lambda x: visivel(x, ".ag-paleta"), ""), "Ctrl+K abre a barra de comandos")
        ActionChains(d).send_keys("nova").perform()
        ActionChains(d).send_keys(Keys.ENTER).perform()
        confere(esperar(d, lambda x: visivel(x, ".ag-nova"), ""), "a ação 'Nova nota' abre o painel")
        campos = d.find_elements(By.CSS_SELECTOR, ".ag-nova input[type=text]")
        titulo = [c for c in campos if not c.get_attribute("list") and not c.get_attribute("aria-label")][0]
        titulo.send_keys("Nota pelo WebKit")
        css(d, ".ag-nova input[list]").send_keys("Fazendo")
        confere(esperar(d, lambda x: "status: Fazendo" in css(x, ".ag-previa").text, ""), "a prévia mostra o status")
        css(d, ".ag-nova textarea").send_keys("Texto da nota.")
        ActionChains(d).key_down(Keys.CONTROL).send_keys(Keys.ENTER).key_up(Keys.CONTROL).perform()
        confere(esperar(d, lambda x: os.path.exists(os.path.join(dest, "nota-pelo-webkit.md")), ""), "a nota foi criada no disco")
        confere(ler(dest, "nota-pelo-webkit.md") == "---\nstatus: Fazendo\n---\n# Nota pelo WebKit\n\nTexto da nota.\n", "com o frontmatter certo")
        confere(esperar(d, lambda x: x.execute_script("return document.querySelector('#content h1')?.textContent === 'Nota pelo WebKit'"), ""), "e abre sem F5")
        d.save_screenshot(f"{TELAS}/w1-webkit-nota.png")

        print("3. Editar e checklist")
        d.get(base + "site/index.html#inicio")
        esperar(d, lambda x: visivel(x, "#ag-bar"), "")
        botao = [b for b in d.find_elements(By.CSS_SELECTOR, "#ag-bar button") if b.text == "Editar"][0]
        botao.click()
        confere(esperar(d, lambda x: visivel(x, ".ag-texto"), ""), "Editar mostra a caixa de texto")
        ta = css(d, ".ag-texto")
        d.execute_script("arguments[0].focus(); arguments[0].setSelectionRange(arguments[0].value.length, arguments[0].value.length);", ta)
        ta.send_keys("\nLinha do WebKit.\n")
        atalho(d, "s")
        confere(esperar(d, lambda x: "\nLinha do WebKit." in ler(dest, "INICIO.md"), ""), "Ctrl+S grava no disco")
        esperar(d, lambda x: not visivel(x, ".ag-texto"), "")
        antes = ler(dest, "INICIO.md")
        caixa = d.find_elements(By.CSS_SELECTOR, "#content input[type=checkbox]")[1]
        confere(esperar(d, lambda x: caixa.is_enabled(), ""), "as caixas do checklist ficam ativas")
        caixa.click()
        confere(esperar(d, lambda x: ler(dest, "INICIO.md") != antes, ""), "clicar numa caixa grava no arquivo")
        dif = [(a, c) for a, c in zip(antes.split("\n"), ler(dest, "INICIO.md").split("\n")) if a != c]
        confere(len(dif) == 1 and dif[0][1].startswith("- [x]"), "só a linha da caixa mudou")

        print("4. Quadro")
        css(d, "#kb-btn").click()
        confere(esperar(d, lambda x: visivel(x, "#kb-view .kb-cartao"), ""), "o quadro abre")
        colunas = colunas_do_quadro(d)
        confere(colunas == ["A fazer", "Em progresso", "Fazendo", "Ideia"], f"colunas certas, com Feito escondida: {colunas}")
        busca = css(d, ".kb-busca")
        d.execute_script("arguments[0].scrollIntoView({block: 'center'}); arguments[0].focus();", busca)
        ActionChains(d).send_keys("feito").perform()
        confere(esperar(d, lambda x: colunas_do_quadro(x)[-1] == "Feito", ""), "buscando, a coluna Feito aparece")
        ActionChains(d).send_keys(Keys.BACKSPACE * 5).perform()  # como quem apaga digitando: dispara o evento input
        confere(esperar(d, lambda x: "Feito" not in colunas_do_quadro(x), ""), "e some quando a busca é apagada")
        confere(d.execute_script("return document.documentElement.scrollWidth <= innerWidth"), "o quadro não cria rolagem horizontal")
        larguras = d.execute_script("return [...document.querySelectorAll('.kb-col')].map((c) => Math.round(c.getBoundingClientRect().width))")
        confere(set(larguras) == {280}, f"colunas com 280 px cada ({set(larguras)})")
        d.save_screenshot(f"{TELAS}/w2-webkit-quadro.png")
        mover_por_seletor(d, '.kb-cartao[data-chave="n:01-Visao-e-Negocio/ideia-a.md"]', "fazendo")
        confere(esperar(d, lambda x: "status: Fazendo" in ler(dest, "01-Visao-e-Negocio/ideia-a.md"), ""), "o seletor Mover para… troca o status no .md")
        confere(esperar(d, lambda x: "Movido para Fazendo." in css(x, "#kb-view [role=status]").text, ""), "e anuncia o movimento")
        feitos = ler(dest, "INICIO.md").count("- [x]")
        mover_por_seletor(d, ".kb-cartao.kb-item", "feito")
        confere(esperar(d, lambda x: ler(dest, "INICIO.md").count("- [x]") == feitos + 1, ""), "mover um item para Feito troca a caixa")
        # arraste HTML5: o driver não o simula; ao menos os elementos estão prontos para ele
        confere(d.execute_script("return document.querySelectorAll('.kb-cartao[draggable=true]').length > 0"), "os cartões são arrastáveis")

        print("5. Celular (janela de 390 px): nenhum documento estoura a largura")
        d.set_window_size(390, 800)
        d.get(base + "site/index.html")
        esperar(d, lambda x: x.execute_script("return !!document.querySelector('.item-btn')"), "")
        ids = d.execute_script("return [...document.querySelectorAll('.item-btn')].map((b) => b.dataset.id)")
        ruins = []
        for i in ids:
            d.get(base + "site/index.html#" + i)
            esperar(d, lambda x: x.execute_script("return document.querySelector('.item-btn.active')?.dataset.id === arguments[0] && !document.getElementById('content').textContent.startsWith('Carregando')", i), "", 5)
            larg = d.execute_script("return [document.documentElement.scrollWidth, innerWidth]")
            if larg[0] > larg[1]:
                ruins.append((i, larg[0]))
        confere(not ruins, f"nenhum dos {len(ids)} documentos passa da largura da tela" + (f": {ruins[:3]}" if ruins else ""))
        confere(not visivel(d, "#tree") and visivel(d, "#menu-btn"), "menu recolhível: a lista começa recolhida e o botão Menu aparece")
        d.save_screenshot(f"{TELAS}/w3-webkit-celular.png")
    finally:
        d.quit()
        srv.terminate()
        shutil.rmtree(tmp, ignore_errors=True)
        if xvfb:
            xvfb.terminate()
    fim()


main()
