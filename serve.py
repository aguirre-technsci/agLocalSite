# Servidor local sem cache. A raiz do projeto (a pasta que contém agLocalSite/) é servida em /;
# o site fica em /_ag/ (ou no prefixo_url do config.json); "../arquivo.md" na página aponta sempre para a raiz.
# Além dos arquivos, atende /api/* (escrita no workspace); as regras ficam em agwrite.py.
import json
import os
import sys
import threading
import traceback
import webbrowser
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import unquote, urlsplit

import agwrite
import sync

MAX_CORPO = 2 * 1024 * 1024  # 2 MB
MAX_CORPO_CONFIG = 64 * 1024     # as rotas de configuração recebem só um objeto pequeno


class Servidor(ThreadingHTTPServer):
    # No Windows, SO_REUSEADDR deixa dois servidores ligarem na MESMA porta (e escreverem nos mesmos .md sem LOCK comum).
    # Desligado lá, a porta ocupada dá OSError e o laço abaixo tenta a seguinte. Em Linux/Mac ele segue ligado (evita TIME_WAIT).
    allow_reuse_address = os.name != "nt"
    request_queue_size = 128   # o padrão (5) recusa conexões quando várias chegam juntas (várias abas, consulta a cada 2 s)


class Handler(SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def log_message(self, fmt, *args):
        if "/api/versao" not in self.requestline:  # a página consulta a cada 2 s; não enche o terminal
            super().log_message(fmt, *args)

    def do_GET(self):
        if self.path.startswith("/api/"):
            self.api()
        else:
            self.estatico(super().do_GET)

    def do_HEAD(self):
        self.estatico(super().do_HEAD)

    def estatico(self, servir):
        """Arquivo da raiz do projeto (ou do site, em /_ag/). Mesma barreira de Host da API; pastas ocultas, a agLocalSite/ (se está dentro da raiz) e a dados/ ficam de fora."""
        try:
            self.checar()
        except agwrite.Erro as e:
            return self.send_error(e.status, e.msg)
        caminho = unquote(urlsplit(self.path).path)
        pre = "/" + sync.prefixo_url()   # onde o site mora (config.json > prefixo_url; padrão /_ag)
        if caminho == "/":
            self.send_response(302)
            self.send_header("Location", pre + "/")
            self.end_headers()
            return
        partes = [p for p in caminho.split("/") if p]
        if caminho != pre and not caminho.startswith(pre + "/") and partes and sync.protegido(partes):
            return self.send_error(404)
        servir()

    def translate_path(self, path):
        caminho = unquote(urlsplit(path).path)
        pre = "/" + sync.prefixo_url()
        if caminho == pre or caminho.startswith(pre + "/"):
            self.directory, path = sync.SITE_DIR, caminho[len(pre):] or "/"
        else:
            self.directory = sync.ROOT
        return super().translate_path(path)

    def do_POST(self):
        if self.path.startswith("/api/"):
            self.api()
        else:
            self.send_error(405)

    def responder(self, status, dados):
        corpo = json.dumps(dados, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(corpo)))
        self.end_headers()
        self.wfile.write(corpo)

    def api(self):
        try:
            self.checar()
            rota, post = self.path.split("?")[0], self.command == "POST"
            if not post and rota == "/api/ping":
                r = {"escrita": True}
            elif not post and rota == "/api/versao":
                r = agwrite.versao()
            elif not post and rota == "/api/estado":
                r = agwrite.estado()
            elif post and rota == "/api/salvar":
                c = self.corpo()
                r = agwrite.salvar(c.get("file"), c.get("texto"), c.get("base_mtime"))
            elif post and rota == "/api/nova":
                c = self.corpo()
                r = agwrite.nova(c.get("pasta", ""), c.get("titulo", ""), c.get("tags", []), c.get("corpo", ""), c.get("status", ""))
            elif post and rota == "/api/postit":
                c = self.corpo()
                r = agwrite.postit_salvar(c.get("file"), c.get("postit"))
            elif not post and rota == "/api/config":
                r = agwrite.config_estado()
            elif post and rota == "/api/config":
                c = self.corpo(MAX_CORPO_CONFIG)
                r = agwrite.config_salvar(c.get("valores"), c.get("base_versao"))
            elif post and rota == "/api/config/desfazer":
                self.corpo(MAX_CORPO_CONFIG)
                r = agwrite.config_desfazer()
            elif post and rota == "/api/postit/apagar":
                c = self.corpo()
                r = agwrite.postit_apagar(c.get("file"), c.get("id"))
            else:
                raise agwrite.Erro(404, "rota", "Rota desconhecida.")
            self.responder(200, r)
        except agwrite.Erro as e:
            self.responder(e.status, e.corpo())
        except Exception:
            traceback.print_exc()  # o detalhe fica no terminal; a página só recebe a mensagem curta
            self.responder(500, {"erro": "Erro interno do servidor.", "codigo": "interno"})

    def checar(self):
        """Só a própria máquina, pelo endereço do servidor. Barra página de outro site (POST) e DNS rebinding (Host)."""
        hosts = {f"localhost:{self.server.server_port}", f"127.0.0.1:{self.server.server_port}"}
        if self.headers.get("Host") not in hosts:
            raise agwrite.Erro(403, "host", "Endereço não permitido.")
        if self.command == "POST":
            if self.headers.get("Origin") not in {f"http://{h}" for h in hosts}:
                raise agwrite.Erro(403, "origem", "Origem não permitida.")
            if not (self.headers.get("Content-Type") or "").startswith("application/json"):
                raise agwrite.Erro(415, "tipo", "O pedido precisa ser application/json.")

    def corpo(self, limite=MAX_CORPO):
        try:
            n = int(self.headers.get("Content-Length", ""))
        except ValueError:
            raise agwrite.Erro(400, "corpo", "Pedido sem tamanho.")
        if n > limite:
            raise agwrite.Erro(413, "grande", "O pedido passa de 2 MB." if limite == MAX_CORPO else f"O pedido passa de {limite // 1024} KB.")
        try:
            c = json.loads(self.rfile.read(max(n, 0)).decode("utf-8"))
        except (ValueError, RecursionError):  # UnicodeDecodeError também é ValueError; milhares de [ aninhados estouram a pilha
            raise agwrite.Erro(400, "json", "O pedido não é um JSON válido.")
        if not isinstance(c, dict):
            raise agwrite.Erro(400, "json", "O pedido não é um JSON válido.")
        return c


if __name__ == "__main__":
    porta = int(sys.argv[1]) if len(sys.argv) > 1 else int(sync.config().get("porta", 8000))
    servidor = None
    for p in range(porta, porta + 20):  # porta ocupada: tenta a seguinte
        try:
            servidor = Servidor(("127.0.0.1", p), Handler)
            break
        except OSError:
            continue
    if servidor is None:
        sys.exit(f"Nenhuma porta livre entre {porta} e {porta + 19}.")
    for a in sync.avisos_config():
        print("AVISO:", a, flush=True)
    agwrite.versao()  # sincroniza uma vez: content.js e graph-data.js nascem em dia
    url = f"http://localhost:{servidor.server_port}/"
    print(f"agLocalSite — raiz do projeto: {sync.ROOT}", flush=True)
    print(f"Escrita ativa em {url}  (site em {url}{sync.prefixo_url()}/ ; Ctrl+C para parar)", flush=True)
    threading.Timer(0.5, webbrowser.open, [url]).start()
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        print("\nServidor encerrado.", flush=True)
    finally:
        servidor.server_close()
