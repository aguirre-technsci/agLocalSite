"""CSP e imagens no navegador: nenhuma violação de CSP nas telas principais (servidor e file://), handler inline bloqueado,
imagem local carrega, um único <h1>. Cópia temporária, porta livre. Uso: python3 tests/seguranca_navegador.py"""
import base64, os, shutil, socket, subprocess, sys, tempfile, time
from playwright.sync_api import sync_playwright
RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
tmp = tempfile.mkdtemp(); dest = os.path.join(tmp, "p")
shutil.copytree(RAIZ, dest, ignore=shutil.ignore_patterns("__pycache__", "dados"))
os.makedirs(os.path.join(dest, "docs", "plans", "img"), exist_ok=True)
PNG = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==")
open(os.path.join(dest, "docs", "plans", "img", "p.png"), "wb").write(PNG)
open(os.path.join(dest, "docs", "plans", "x.md"), "w", encoding="utf-8").write("---\ntags: [a]\n---\n# Plano X\n\n![local](img/p.png) e ![fora](https://exemplo.invalid/t.png)\n\n- [ ] item\n")
subprocess.run([sys.executable, "sync.py"], cwd=dest, stdout=subprocess.DEVNULL, check=True)
with socket.socket() as s:
    s.bind(("127.0.0.1", 0)); porta = s.getsockname()[1]
srv = subprocess.Popen([sys.executable, "serve.py", str(porta)], cwd=dest, env={**os.environ, "BROWSER": "true"}, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
falhas = 0
def confere(c, m):
    global falhas
    print(("  ok    " if c else "  FALHA ") + m); falhas += 0 if c else 1
SPY = "window.__csp=[];document.addEventListener('securitypolicyviolation',e=>window.__csp.push(e.violatedDirective+' '+e.blockedURI));"
try:
    time.sleep(1.5)
    with sync_playwright() as p:
        br = p.chromium.launch(); pg = br.new_page(viewport={"width": 1280, "height": 800})
        pg.add_init_script(SPY); reqs = []; pg.on("request", lambda r: reqs.append(r.url))
        pg.goto(f"http://localhost:{porta}/"); pg.wait_for_timeout(1200)
        pg.evaluate("document.querySelectorAll('.group,.subgroup').forEach(g=>g.classList.add('open'))"); pg.click("[data-id=docs-plans-x]"); pg.wait_for_timeout(1200)
        confere(pg.evaluate("document.querySelectorAll('h1').length") == 1, "um único <h1> na página")
        confere(pg.evaluate("document.querySelector('#content img')?.naturalWidth") == 1, "imagem local carregou (naturalWidth 1)")
        confere(pg.evaluate("document.querySelectorAll('#content img').length") == 1, "imagem externa não virou <img>")
        confere(not any("exemplo.invalid" in r for r in reqs), "nenhuma requisição saiu para o host externo")
        for sel in ("#graph-btn", "#kb-btn", "#cfg-btn"):
            pg.click(sel); pg.wait_for_timeout(700)
        pg.click("#graph-btn") if False else None
        pg.goto(f"http://localhost:{porta}/#docs-plans-x"); pg.wait_for_timeout(1000)
        pg.click(".ag-btn >> text=Editar"); pg.wait_for_timeout(600)
        pg.evaluate("document.body.insertAdjacentHTML('beforeend','<img src=x onerror=\"window.__xss=1\">')"); pg.wait_for_timeout(400)
        confere(pg.evaluate("window.__xss") is None, "handler inline (onerror) bloqueado pela CSP")
        v = pg.evaluate("window.__csp.filter(x=>!x.includes('inline'))")
        confere(v == [], f"nenhuma violação de CSP nas telas (servidor) além do teste inline: {v}")
        fp = br.new_page(); fp.add_init_script(SPY); errs = []; fp.on("pageerror", lambda e: errs.append(str(e)))
        fp.goto("file://" + os.path.join(dest, "site", "index.html")); fp.wait_for_timeout(1500)
        confere(fp.evaluate("document.querySelectorAll('.item-btn').length") >= 1, "file://: menu carregou com a CSP")
        confere(fp.evaluate("window.__csp") == [] and not errs, f"file://: sem violação nem erro ({fp.evaluate('window.__csp')}, {errs})")
        br.close()
finally:
    srv.terminate(); shutil.rmtree(tmp, ignore_errors=True)
print("falhas:", falhas); sys.exit(1 if falhas else 0)
