"""Navegação: um fetch do .md por clique; link #secao rola sem trocar o documento (F5 mantém o documento). Cópia temporária, porta livre."""
import os, shutil, socket, subprocess, sys, tempfile, time
from playwright.sync_api import sync_playwright
RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
tmp = tempfile.mkdtemp(); dest = os.path.join(tmp, "p")
shutil.copytree(RAIZ, dest, ignore=shutil.ignore_patterns("__pycache__", "dados"))
os.makedirs(os.path.join(dest, "notas"), exist_ok=True)
open(os.path.join(dest, "notas", "a.md"), "w", encoding="utf-8").write("# Nota A\n\n[ir](#fim)\n\n" + "linha\n\n" * 80 + "## Fim\n\ntexto\n")
with socket.socket() as s:
    s.bind(("127.0.0.1", 0)); porta = s.getsockname()[1]
srv = subprocess.Popen([sys.executable, "serve.py", str(porta)], cwd=dest, env={**os.environ, "BROWSER": "true"}, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
falhas = 0
def confere(c, m):
    global falhas
    print(("  ok    " if c else "  FALHA ") + m); falhas += 0 if c else 1
try:
    time.sleep(1.5)
    with sync_playwright() as p:
        br = p.chromium.launch(); pg = br.new_page(viewport={"width": 1280, "height": 800})
        reqs = []; pg.on("request", lambda r: reqs.append(r.url) if r.url.endswith("notas/a.md") else None)
        pg.goto(f"http://localhost:{porta}/"); pg.wait_for_timeout(1200)
        pg.evaluate("document.querySelectorAll('.group,.subgroup').forEach(g=>g.classList.add('open'))")
        reqs.clear(); pg.click("[data-id=notas-a]"); pg.wait_for_timeout(1200)
        confere(len(reqs) == 1, f"clique em documento: {len(reqs)} fetch do .md (esperado 1)")
        y0 = pg.evaluate("scrollY"); pg.click("#content a[href='#fim']"); pg.wait_for_timeout(500)
        confere(pg.evaluate("scrollY") > y0 + 200, "link #fim rolou até o título")
        confere(pg.evaluate("location.hash") == "#notas-a", f"hash continua do documento ({pg.evaluate('location.hash')})")
        pg.reload(); pg.wait_for_timeout(1200)
        confere(pg.evaluate("document.querySelector('#content h1')?.innerText") == "Nota A", "F5 reabre o mesmo documento")
        br.close()
finally:
    srv.terminate(); shutil.rmtree(tmp, ignore_errors=True)
print("falhas:", falhas); sys.exit(1 if falhas else 0)
