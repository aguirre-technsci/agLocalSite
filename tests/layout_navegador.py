"""Layout do .shell com o servidor ligado (camada de post-its presente): main ao lado da sidebar no desktop, empilhado no celular.
Roda numa cópia temporária, em porta livre. Uso: python3 tests/layout_navegador.py"""
import os, shutil, socket, subprocess, sys, tempfile, time
from playwright.sync_api import sync_playwright

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
tmp = tempfile.mkdtemp()
dest = os.path.join(tmp, "p")
shutil.copytree(RAIZ, dest, ignore=shutil.ignore_patterns("__pycache__", "dados"))
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
        br = p.chromium.launch()
        for w in (1440, 1024, 861):
            pg = br.new_page(viewport={"width": w, "height": 800}); pg.goto(f"http://localhost:{porta}/"); pg.wait_for_selector(".pi-camada", state="attached", timeout=10000); pg.wait_for_timeout(300)
            m = pg.evaluate("(()=>{const b=document.querySelector('main').getBoundingClientRect();return [b.x,b.y,b.width]})()")
            confere(m[0] >= 299 and m[1] == 0 and m[2] > 600, f"{w}px: main ao lado da sidebar, largura útil ({m})")
            pg.close()
        pg = br.new_page(viewport={"width": 375, "height": 700}); pg.goto(f"http://localhost:{porta}/"); pg.wait_for_selector(".pi-camada", state="attached", timeout=10000); pg.wait_for_timeout(300)
        c = pg.evaluate("(()=>{const b=document.querySelector('.pi-camada').getBoundingClientRect();return [b.x,b.width,innerWidth]})()")
        confere(c[0] < 5 and c[1] > 300, f"375px: camada de post-its cobre a largura da tela ({c})")
        br.close()
finally:
    srv.terminate(); shutil.rmtree(tmp, ignore_errors=True)
print("falhas:", falhas); sys.exit(1 if falhas else 0)
