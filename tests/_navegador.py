"""Ajudas dos testes de navegador (escrita_navegador.py, kanban_navegador.py): cópia temporária do projeto,
servidor próprio em porta livre, leitura/escrita de arquivos da cópia e conferências com contagem de falhas."""
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time

from playwright.sync_api import expect

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TELAS = os.environ.get("AG_TELAS", "/tmp/ag-telas")
falhas = []


def confere(cond, msg):
    print(("  ok    " if cond else "  FALHA ") + msg)
    if not cond:
        falhas.append(msg)


def porta_livre():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def copiar():
    tmp = tempfile.mkdtemp()
    dest = os.path.join(tmp, "projeto")
    shutil.copytree(RAIZ, dest, ignore=shutil.ignore_patterns(".historico", "__pycache__", "node_modules"))
    return tmp, dest


def subir(dest, porta):
    p = subprocess.Popen([sys.executable, "serve.py", str(porta)], cwd=dest, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(50):
        try:
            socket.create_connection(("127.0.0.1", porta), timeout=0.2).close()
            return p
        except OSError:
            time.sleep(0.1)
    raise RuntimeError("servidor não subiu")


def ler(dest, rel):
    with open(os.path.join(dest, rel), encoding="utf-8", newline="") as f:
        return f.read()


def escrever(dest, rel, texto):
    with open(os.path.join(dest, rel), "w", encoding="utf-8", newline="") as f:
        f.write(texto)


def abrir(page, base, hash_=""):
    page.goto(base + "site/index.html" + hash_)
    page.wait_for_selector(".item-btn", state="attached")  # no celular a lista de documentos começa recolhida
    if hash_:  # espera o documento do endereço terminar de carregar (a página troca de documento sem recarregar)
        page.wait_for_function(
            "id => document.querySelector('.item-btn.active')?.dataset.id === id"
            " && !document.getElementById('content').textContent.startsWith('Carregando')", arg=hash_[1:])


def escrita_ligada(page):
    expect(page.locator("#ag-plus")).to_be_visible(timeout=5000)


def contraste(page, seletor, fundo_seletor):
    return page.evaluate("""([sel, fsel]) => {
      const lum = (c) => { const [r,g,b] = c.match(/\\d+(\\.\\d+)?/g).slice(0,3).map(Number).map(v => { v/=255; return v<=0.03928 ? v/12.92 : ((v+0.055)/1.055)**2.4; }); return 0.2126*r+0.7152*g+0.0722*b; };
      const fg = getComputedStyle(document.querySelector(sel)).color;
      const bg = getComputedStyle(document.querySelector(fsel)).backgroundColor;
      const [a, b] = [lum(fg), lum(bg)].sort((x, y) => y - x);
      return (a + 0.05) / (b + 0.05);
    }""", [seletor, fundo_seletor])


def fim():
    """Imprime o resultado e sai com 0 (tudo certo) ou 1 (houve falhas)."""
    print("\n%s" % ("FALHAS: %d" % len(falhas) if falhas else "tudo certo"))
    sys.exit(1 if falhas else 0)
