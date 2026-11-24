"""Tudo que aparece na tela é configurável (config.json): títulos, rótulos, rodapé, 'Home' e o endereço do site. Cópia temporária."""
import http.client
import json
import os
import sys
import threading
import unittest
from http.server import ThreadingHTTPServer
from unittest import mock

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)
sys.path.insert(0, os.path.join(RAIZ, "tests"))
import serve
import sync
import test_agwrite as ta   # módulo, não as classes: senão o unittest roda os testes de lá de novo aqui

escrever = ta.escrever


def config(self, dados):
    escrever(self.ag, "config.json", json.dumps(dados))


class Textos(ta.Base):
    def test_padroes_sem_config(self):
        d = sync.dados_site()
        pasta = os.path.basename(self.tmp)
        self.assertEqual(d["titulo"], pasta)
        self.assertEqual(d["etiqueta"], pasta.upper() + " / agLocalSite")
        self.assertEqual(d["titulo_aba"], pasta + " — agLocalSite")
        self.assertEqual((d["subtitulo"], d["textos"]), ("", {}))
        self.assertEqual(sync.prefixo_url(), "_ag")
        self.assertEqual(sync.avisos_config(), [])

    def test_valores_do_config(self):
        config(self, {"titulo": "Meu Projeto", "subtitulo": "Notas do time", "etiqueta": "EQUIPE / docs", "titulo_aba": "Docs",
                      "textos": {"grafo": "◎ Mapa", "quadro": "▦ Tarefas", "tema_claro": "Claro", "rodape": ""}})
        d = sync.dados_site()
        self.assertEqual((d["titulo"], d["subtitulo"], d["etiqueta"], d["titulo_aba"]), ("Meu Projeto", "Notas do time", "EQUIPE / docs", "Docs"))
        self.assertEqual(d["textos"], {"grafo": "◎ Mapa", "quadro": "▦ Tarefas", "tema_claro": "Claro", "rodape": ""})

    def test_titulo_aba_acompanha_o_titulo(self):
        config(self, {"titulo": "Meu Projeto"})
        self.assertEqual(sync.dados_site()["titulo_aba"], "Meu Projeto — agLocalSite")

    def test_textos_filtra_chave_desconhecida_tipo_errado_e_tamanho(self):
        config(self, {"textos": {"grafo": "ok", "inventada": "x", "menu": 5, "home": "H" * 500, "rodape": "R" * 5000}})
        t = sync.dados_site()["textos"]
        self.assertEqual(sorted(t), ["grafo", "home", "rodape"])
        self.assertEqual((len(t["home"]), len(t["rodape"])), (sync.MAX_TEXTO, sync.MAX_RODAPE))
        av = " ".join(sync.avisos_config())
        self.assertIn("textos.inventada", av)
        self.assertIn("textos.menu", av)

    def test_textos_que_nao_e_objeto(self):
        config(self, {"textos": "grafo"})
        self.assertEqual(sync.dados_site()["textos"], {})
        self.assertIn('"textos" precisa ser um objeto', " ".join(sync.avisos_config()))

    def test_config_com_tipos_errados_nao_quebra(self):
        config(self, {"titulo": 5, "subtitulo": ["x"], "etiqueta": None, "titulo_aba": {}, "prefixo_url": 7})
        d = sync.dados_site()
        self.assertEqual((d["titulo"], d["subtitulo"]), (os.path.basename(self.tmp), ""))

    def test_rotulo_do_grupo_home(self):
        self.assertEqual(sync.montar_dados()[0][0]["label"], "Home")
        config(self, {"textos": {"home": "Início"}})
        self.assertEqual(sync.montar_dados()[0][0]["label"], "Início")

    def test_prefixo_url_valido_e_invalido(self):
        for ok in ("site", "meu-site", "docs_2", "A" * 32):
            config(self, {"prefixo_url": ok})
            self.assertEqual(sync.prefixo_url(), ok)
            self.assertEqual(sync.avisos_config(), [])
        for ruim in ("a/b", "..", "", "api", "API", "tem espaço", "A" * 33, 5, None, ["x"], "/_ag", "x.y"):
            config(self, {"prefixo_url": ruim})
            self.assertEqual(sync.prefixo_url(), "_ag", repr(ruim))
            self.assertTrue(any("prefixo_url" in a for a in sync.avisos_config()), repr(ruim))

    def test_aviso_quando_o_prefixo_esconde_uma_pasta_da_raiz(self):
        config(self, {"prefixo_url": "01-A"})
        self.assertTrue(any("fica escondida" in a for a in sync.avisos_config()))


class Recarga(ta.Base):
    def test_editar_so_o_config_refaz_o_content_js(self):
        import agwrite
        antes = agwrite.versao()["carimbo"]
        config(self, {"titulo": "Título Novo", "textos": {"grafo": "◎ Mapa"}})
        depois = agwrite.versao()["carimbo"]
        self.assertNotEqual(antes, depois)
        with open(sync.CONTENT_JS_PATH, encoding="utf-8") as f:
            js = f.read()
        self.assertIn("Título Novo", js)
        self.assertIn("◎ Mapa", js)
        self.assertEqual(agwrite.versao()["carimbo"], depois)   # estável: sem mudança, sem novo sync


class Servido(ta.Base):
    """Base com servidor temporário em porta livre; get(rota) -> (status, Location, corpo). Sem testes próprios."""

    def setUp(self):
        super().setUp()
        escrever(self.ag, "site/index.html", "<title>site</title>")
        self.quieto = mock.patch.object(serve.Handler, "log_message", lambda *a: None)
        self.quieto.start()
        self.srv = ThreadingHTTPServer(("127.0.0.1", 0), serve.Handler)
        self.porta = self.srv.server_address[1]
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()

    def tearDown(self):
        self.srv.shutdown()
        self.srv.server_close()
        self.quieto.stop()
        super().tearDown()

    def get(self, rota):
        c = http.client.HTTPConnection("127.0.0.1", self.porta, timeout=5)
        c.request("GET", rota, headers={"Host": f"localhost:{self.porta}"})
        r = c.getresponse()
        corpo = r.read().decode("utf-8")
        loc = r.getheader("Location")
        c.close()
        return r.status, loc, corpo


class Endereco(Servido):
    def test_padrao_e_ag(self):
        self.assertEqual(self.get("/")[:2], (302, "/_ag/"))
        self.assertEqual(self.get("/_ag/")[0::2], (200, "<title>site</title>"))

    def test_prefixo_configurado(self):
        config(self, {"prefixo_url": "docs-site"})
        self.assertEqual(self.get("/")[:2], (302, "/docs-site/"))
        self.assertEqual(self.get("/docs-site/")[0::2], (200, "<title>site</title>"))
        self.assertEqual(self.get("/docs-site/index.html")[0], 200)
        self.assertEqual(self.get("/_ag/")[0], 404)            # o endereço antigo deixa de existir
        self.assertEqual(self.get("/01-A/nota.md")[0], 200)    # a raiz continua servida em /
        self.assertEqual(self.get("/agLocalSite/serve.py")[0], 404)
        self.assertEqual(self.get("/api/ping")[0], 200)


class Raiz(ta.Base):
    def test_padrao_e_a_propria_pasta(self):
        self.assertEqual(sync.resolver_raiz(), self.ag)

    def test_raiz_pedida_no_config(self):
        os.makedirs(os.path.join(self.tmp, "01-A", "sub"), exist_ok=True)
        casos = {"..": self.tmp, ".": self.ag, "../01-A": os.path.join(self.tmp, "01-A"),
                 "../01-A/sub": os.path.join(self.tmp, "01-A", "sub"), os.path.join(self.tmp, "02-B"): os.path.join(self.tmp, "02-B")}
        for pedido, esperado in casos.items():
            config(self, {"raiz": pedido})
            self.assertEqual(os.path.normcase(sync.resolver_raiz()), os.path.normcase(esperado), pedido)
            self.assertEqual(sync.avisos_config(), [], pedido)

    def test_raiz_invalida_cai_na_propria_pasta_com_aviso(self):
        for ruim in ("../nao-existe", 5, ["x"], {"a": 1}, "02-B/sub/x.md"):
            config(self, {"raiz": ruim})
            self.assertEqual(sync.resolver_raiz(), self.ag, repr(ruim))
            self.assertTrue(any('"raiz"' in a for a in sync.avisos_config()), repr(ruim))
        for vazio in ("", None, "   "):   # vazio = padrão, sem aviso
            config(self, {"raiz": vazio})
            self.assertEqual(sync.resolver_raiz(), self.ag)
            self.assertEqual(sync.avisos_config(), [])

    def test_protegido(self):
        # raiz = pasta pai: a agLocalSite inteira e o que é oculto ficam de fora
        for partes in (["agLocalSite"], ["agLocalSite", "dados", "x.md"], ["AGLOCALSITE", "site"], [".git", "config"], ["01-A", ".x"]):
            self.assertTrue(sync.protegido(partes), partes)
        for partes in (["01-A", "nota.md"], ["INICIO.md"], ["agLocalSite2", "x.md"]):
            self.assertFalse(sync.protegido(partes), partes)
        # raiz = a própria agLocalSite: só dados/ (histórico e post-its) e ocultos ficam de fora
        sync.ROOT = self.ag
        for partes in (["dados"], ["dados", "historico", "x.md"], ["Dados", "postits"], [".git"]):
            self.assertTrue(sync.protegido(partes), partes)
        for partes in (["docs", "a.md"], ["LEIA-ME.md"], ["site", "index.html"], ["dados2", "x.md"]):
            self.assertFalse(sync.protegido(partes), partes)

    def test_raiz_propria_nao_varre_dados(self):
        os.unlink(os.path.join(self.ag, "ignorado.md"))
        for rel in ("LEIA-ME.md", "docs/specs/a.md", "dados/historico/copia.md", "dados/postits/x.md", "site/js/vendor/v.md"):
            escrever(self.ag, rel, "# t\n")
        sync.ROOT = self.ag
        rels = sorted(os.path.relpath(p, self.ag).replace("\\", "/") for p in sync.arquivos_md())
        self.assertEqual(rels, ["LEIA-ME.md", "docs/specs/a.md"])
        self.assertEqual(sorted(sync.pastas_topo()), ["docs", "site"])
        self.assertEqual(sync.dados_site()["etiqueta"], "agLocalSite")


class RaizPropria(Servido):
    def setUp(self):
        super().setUp()
        os.unlink(os.path.join(self.ag, "ignorado.md"))
        for rel, txt in (("LEIA-ME.md", "# Leia\n"), ("docs/a.md", "# A\n"), ("dados/historico/copia.md", "# segredo\n")):
            escrever(self.ag, rel, txt)
        sync.ROOT = self.ag
        agwrite_mod = sys.modules["agwrite"]
        agwrite_mod._ultimo = agwrite_mod._dados = None

    def test_serve_a_raiz_mas_nao_o_dados(self):
        self.assertEqual(self.get("/docs/a.md")[0::2], (200, "# A\n"))
        self.assertEqual(self.get("/LEIA-ME.md")[0], 200)
        for rota in ("/dados/historico/copia.md", "/DADOS/historico/copia.md", "/dados/", "/.git/config"):
            self.assertEqual(self.get(rota)[0], 404, rota)

    def test_menu_so_com_o_que_esta_na_propria_pasta(self):
        s, _, corpo = self.get("/api/estado")
        self.assertEqual(s, 200)
        self.assertEqual(sorted(json.loads(corpo)["mtimes"]), ["LEIA-ME.md", "docs/a.md"])


if __name__ == "__main__":
    unittest.main()
