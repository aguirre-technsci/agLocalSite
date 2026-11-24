"""Teste de navegador: clica em cada citação de documento e confere que abriu o documento certo.

Precisa de: pip install playwright && playwright install chromium (só para este teste).
Uso: python3 tests/links_navegador.py

Roda duas vezes: lendo os .md ao vivo (servidor local) e com o texto embutido (file://).
O esperado vem de uma leitura independente dos .md (mesma regra da LEIA-ME.md), não do site.
"""
import os
import re
import sys
import threading
from collections import Counter
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

from playwright.sync_api import sync_playwright

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IGNORE = {"site", "tests", "docs", ".git", "__pycache__", "node_modules"}


def read(rel):
    with open(os.path.join(ROOT, rel), encoding="utf-8") as f:
        return f.read()


def list_docs():
    out = []
    for dp, dn, fn in os.walk(ROOT):
        dn[:] = [d for d in dn if d not in IGNORE and not d.startswith(".")]
        out += [os.path.relpath(os.path.join(dp, f), ROOT).replace(os.sep, "/") for f in fn if f.lower().endswith(".md")]
    return sorted(out)


def resolve(ref, docs):
    low = ref.lower()
    hit = [d for d in docs if d.lower() == low]
    if hit:
        return hit[0]
    if "/" in ref:
        return None
    same = [d for d in docs if d.rsplit("/", 1)[-1].lower() == low]
    return same[0] if len(same) == 1 else None


def first_title(text):
    text = re.sub(r"\A\ufeff?---\r?\n.*?\r?\n---\r?\n", "", text, flags=re.S)
    m = re.search(r"^#\s+(.+)$", text, flags=re.M)
    return re.sub(r"[*`]", "", m.group(1)).strip() if m else None


def expected(docs):
    """{documento: [(texto citado, documento de destino), ...]} só com o que resolve."""
    exp = {}
    for d in docs:
        body = re.sub(r"^```.*?^```", "", read(d), flags=re.S | re.M)
        pairs = []
        for ref in re.findall(r"`([^`\n]+)`", body):
            if ref.lower().endswith(".md") and resolve(ref, docs):
                pairs.append((ref, resolve(ref, docs)))
        if pairs:
            exp[d] = pairs
    return exp


def doc_id(page, file):
    return page.evaluate("f => AG_CONTENT.flatMap(g => g.items).find(i => i.file === f).id", file)


def wait_open(page, id_):
    page.wait_for_function(
        "id => document.querySelector('.item-btn.active')?.dataset.id === id"
        " && !document.getElementById('content').textContent.startsWith('Carregando')", arg=id_)


def run(page, base, docs, exp):
    falhas, cliques = [], 0
    for src, pairs in exp.items():
        page.goto(base + "#" + doc_id_from_file(page, base, src))
        sid = doc_id(page, src)
        wait_open(page, sid)
        shown = page.eval_on_selector_all("#content a.doc-link", "e => e.map(x => x.textContent)")
        if Counter(shown) != Counter(r for r, _ in pairs):
            falhas.append(f"{src}: links na tela {sorted(shown)} != esperados {sorted(r for r, _ in pairs)}")
            continue
        for i, (ref, dest) in enumerate(pairs):
            if i:
                page.goto(base + "#" + sid)
                wait_open(page, sid)
            page.locator("#content a.doc-link").nth(i).click()
            did = doc_id(page, dest)
            wait_open(page, did)
            cliques += 1
            h1 = page.inner_text("#content h1")
            aberto = page.evaluate("() => { const b = document.querySelector('.item-btn.active');"
                                   " return !!b.closest('.group.open') && (!b.closest('.subgroup') || !!b.closest('.subgroup.open')); }")
            topo = dest == src or page.evaluate("window.scrollY") == 0  # citação do próprio documento não navega
            if h1 != first_title(read(dest)) or not aberto or not topo:
                falhas.append(f"{src} -> {ref}: h1={h1!r} pasta_aberta={aberto} no_topo={topo}")
    return cliques, falhas


def doc_id_from_file(page, base, file):
    # antes da primeira carga não há AG_CONTENT: abre a página sem hash e consulta
    if page.url.split("#")[0] != base:
        page.goto(base)
        page.wait_for_selector(".item-btn")
    return doc_id(page, file)


def main():
    docs = list_docs()
    exp = expected(docs)
    total = sum(len(v) for v in exp.values())
    class Quieto(SimpleHTTPRequestHandler):
        def log_message(self, *a):
            pass

    handler = partial(Quieto, directory=ROOT)
    srv = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    modos = {
        "ao vivo (http)": f"http://127.0.0.1:{srv.server_address[1]}/site/index.html",
        "embutido (file://)": "file://" + os.path.join(ROOT, "site", "index.html"),
    }
    ruim = False
    with sync_playwright() as p:
        b = p.chromium.launch()
        for nome, base in modos.items():
            page = b.new_page(viewport={"width": 1280, "height": 800})
            cliques, falhas = run(page, base, docs, exp)
            print(f"{nome}: {cliques}/{total} citações clicadas, {len(falhas)} falhas")
            for f in falhas:
                print("  ", f)
            ruim = ruim or bool(falhas) or cliques != total
            if total == 0:
                print("  FALHA: nenhuma citação de documento encontrada; o teste não verificou nada")
                ruim = True
            page.close()
        b.close()
    srv.shutdown()
    sys.exit(1 if ruim else 0)


main()
