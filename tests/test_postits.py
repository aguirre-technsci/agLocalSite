"""Testes dos post-its (agwrite.py e as rotas /api/postit*). Mesmo molde do test_agwrite.py: cópia
temporária, nada toca os arquivos reais."""
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
import agwrite
import serve
import sync

from test_agwrite import Base, escrever  # reaproveita o setUp/tearDown da cópia temporária


def postit(id_="k3f9a1", x=62.5, y=340, w=200, h=160, cor="amarelo", texto="oi"):
    return {"id": id_, "x": x, "y": y, "w": w, "h": h, "cor": cor, "texto": texto}


class Salvar(Base):
    def test_cria_arquivo_no_primeiro_postit(self):
        caminho = self.caminho("agLocalSite/dados/postits/01-A/nota.json")
        self.assertFalse(os.path.exists(caminho))
        r = agwrite.postit_salvar("01-A/nota.md", postit())
        self.assertEqual(r, {"ok": True})
        self.assertTrue(os.path.exists(caminho))
        with open(caminho, encoding="utf-8") as f:
            dados = json.load(f)
        self.assertEqual(dados["postits"], [
            {"id": "k3f9a1", "x": 62.5, "y": 340, "w": 200, "h": 160, "cor": "amarelo", "texto": "oi"},
        ])

    def test_mesmo_id_substitui_e_vai_para_o_fim(self):
        agwrite.postit_salvar("01-A/nota.md", postit("aaaa", texto="primeiro"))
        agwrite.postit_salvar("01-A/nota.md", postit("bbbb", texto="segundo"))
        agwrite.postit_salvar("01-A/nota.md", postit("aaaa", texto="primeiro, editado"))
        lista = agwrite._ler_postits(self.caminho("agLocalSite/dados/postits/01-A/nota.json"))
        self.assertEqual([p["id"] for p in lista], ["bbbb", "aaaa"])
        self.assertEqual(lista[1]["texto"], "primeiro, editado")

    def test_postits_diferentes_do_mesmo_documento_nao_se_sobrescrevem(self):
        agwrite.postit_salvar("01-A/nota.md", postit("aaaa"))
        agwrite.postit_salvar("01-A/nota.md", postit("bbbb"))
        agwrite.postit_salvar("01-A/nota.md", postit("cccc"))
        ids = {p["id"] for p in agwrite._ler_postits(self.caminho("agLocalSite/dados/postits/01-A/nota.json"))}
        self.assertEqual(ids, {"aaaa", "bbbb", "cccc"})

    def test_arredonda_x_e_y_ao_gravar(self):
        agwrite.postit_salvar("01-A/nota.md", postit(x=62.567, y=340.9))
        p = agwrite._ler_postits(self.caminho("agLocalSite/dados/postits/01-A/nota.json"))[0]
        self.assertEqual((p["x"], p["y"]), (62.57, 341))

    def test_documentos_diferentes_tem_arquivos_diferentes(self):
        agwrite.postit_salvar("01-A/nota.md", postit("aaaa"))
        agwrite.postit_salvar("02-B/sub/x.md", postit("bbbb"))
        self.assertEqual(len(agwrite._ler_postits(self.caminho("agLocalSite/dados/postits/01-A/nota.json"))), 1)
        self.assertEqual(len(agwrite._ler_postits(self.caminho("agLocalSite/dados/postits/02-B/sub/x.json"))), 1)

    def test_limite_de_200(self):
        for i in range(200):
            agwrite.postit_salvar("01-A/nota.md", postit(f"a{i:03d}"))
        with self.assertRaises(agwrite.Erro) as c:
            agwrite.postit_salvar("01-A/nota.md", postit("a999"))
        self.assertEqual((c.exception.status, c.exception.codigo), (400, "limite"))
        # mas substituir um id que já existe continua valendo (não é um 201º post-it)
        agwrite.postit_salvar("01-A/nota.md", postit("a000", texto="trocado"))

    def test_nao_toca_no_md(self):
        antes = self.ler("01-A/nota.md")
        agwrite.postit_salvar("01-A/nota.md", postit())
        self.assertEqual(self.ler("01-A/nota.md"), antes)
        self.assertFalse(os.path.isdir(self.caminho("agLocalSite/dados/historico")))

    def test_falha_na_troca_do_arquivo_deixa_o_original_intacto(self):
        agwrite.postit_salvar("01-A/nota.md", postit("aaaa"))
        caminho = self.caminho("agLocalSite/dados/postits/01-A/nota.json")
        with open(caminho, encoding="utf-8") as f:
            antes = f.read()
        with mock.patch("os.replace", side_effect=OSError("disco cheio")):
            with self.assertRaises(agwrite.Erro) as c:
                agwrite.postit_salvar("01-A/nota.md", postit("bbbb"))
        self.assertEqual(c.exception.codigo, "gravar")
        with open(caminho, encoding="utf-8") as f:
            self.assertEqual(f.read(), antes)
        sobras = [n for n in os.listdir(os.path.dirname(caminho)) if n != "nota.json"]
        self.assertEqual(sobras, [])


class Validacao(Base):
    def test_id_invalido(self):
        for ruim in ["", "ab", "a" * 33, "ABCD", "abc-d", "abc def", None, 7, "abcçd"]:
            with self.assertRaises(agwrite.Erro) as c:
                agwrite.postit_salvar("01-A/nota.md", postit(id_=ruim))
            self.assertEqual((c.exception.status, c.exception.codigo), (400, "postit"), repr(ruim))

    def test_cor_invalida(self):
        for ruim in ["", "vermelho", "Amarelo", None, 7]:
            with self.assertRaises(agwrite.Erro) as c:
                agwrite.postit_salvar("01-A/nota.md", postit(cor=ruim))
            self.assertEqual(c.exception.codigo, "postit", repr(ruim))

    def test_x_e_y_fora_da_faixa_ou_tipo_errado(self):
        for x in [-0.1, 100.1, "62", None, True, False, float("nan"), float("inf")]:
            with self.assertRaises(agwrite.Erro, msg=repr(x)):
                agwrite.postit_salvar("01-A/nota.md", postit(x=x))
        for y in [-1, 100001, "340", None, True]:
            with self.assertRaises(agwrite.Erro, msg=repr(y)):
                agwrite.postit_salvar("01-A/nota.md", postit(y=y))
        agwrite.postit_salvar("01-A/nota.md", postit(x=0, y=0))     # limites inclusivos
        agwrite.postit_salvar("01-A/nota.md", postit(x=100, y=100000))

    def test_texto_acima_de_1000_ou_tipo_errado(self):
        with self.assertRaises(agwrite.Erro) as c:
            agwrite.postit_salvar("01-A/nota.md", postit(texto="a" * 1001))
        self.assertEqual(c.exception.codigo, "postit")
        with self.assertRaises(agwrite.Erro):
            agwrite.postit_salvar("01-A/nota.md", postit(texto=None))
        agwrite.postit_salvar("01-A/nota.md", postit(texto="a" * 1000))  # limite inclusivo

    def test_w_e_h_fora_da_faixa_ou_tipo_errado(self):
        for w in [159, 481, "200", None, True, float("nan")]:
            with self.assertRaises(agwrite.Erro, msg=repr(w)):
                agwrite.postit_salvar("01-A/nota.md", postit(w=w))
        for h in [119, 641, "160", None, True]:
            with self.assertRaises(agwrite.Erro, msg=repr(h)):
                agwrite.postit_salvar("01-A/nota.md", postit(h=h))
        agwrite.postit_salvar("01-A/nota.md", postit(w=160, h=120))    # limites inclusivos
        agwrite.postit_salvar("01-A/nota.md", postit(w=480, h=640))

    def test_w_e_h_tem_padrao_para_post_it_antigo_sem_tamanho(self):
        p = postit()
        del p["w"], p["h"]
        agwrite.postit_salvar("01-A/nota.md", p)
        salvo = agwrite._ler_postits(self.caminho("agLocalSite/dados/postits/01-A/nota.json"))[0]
        self.assertEqual((salvo["w"], salvo["h"]), (200, 160))

    def test_postit_nao_e_objeto(self):
        for ruim in [None, "x", 7, [1, 2]]:
            with self.assertRaises(agwrite.Erro) as c:
                agwrite.postit_salvar("01-A/nota.md", ruim)
            self.assertEqual(c.exception.codigo, "postit")

    def test_campos_desconhecidos_sao_descartados(self):
        p = postit()
        p["intruso"] = "x"
        agwrite.postit_salvar("01-A/nota.md", p)
        salvo = agwrite._ler_postits(self.caminho("agLocalSite/dados/postits/01-A/nota.json"))[0]
        self.assertEqual(set(salvo), {"id", "x", "y", "w", "h", "cor", "texto"})

    def test_caminhos_invalidos(self):
        fora = os.path.join(os.path.dirname(self.tmp), "fora.md")
        ruins = ["../fora.md", fora, "01-A/nota.txt", "01-A", "", "node_modules/ignorado.md",
                 "agLocalSite/ignorado.md", ".oculta/z.md", "01-A/nao-existe.md", None, 7]
        for ruim in ruins:
            with self.assertRaises(agwrite.Erro) as c:
                agwrite.postit_salvar(ruim, postit())
            self.assertEqual((c.exception.status, c.exception.codigo), (400, "caminho"), repr(ruim))
            with self.assertRaises(agwrite.Erro) as c2:
                agwrite.postit_apagar(ruim, "k3f9a1")
            self.assertEqual((c2.exception.status, c2.exception.codigo), (400, "caminho"), repr(ruim))


class Apagar(Base):
    def test_apaga_o_postit_e_mantem_os_outros(self):
        agwrite.postit_salvar("01-A/nota.md", postit("aaaa"))
        agwrite.postit_salvar("01-A/nota.md", postit("bbbb"))
        agwrite.postit_apagar("01-A/nota.md", "aaaa")
        lista = agwrite._ler_postits(self.caminho("agLocalSite/dados/postits/01-A/nota.json"))
        self.assertEqual([p["id"] for p in lista], ["bbbb"])

    def test_id_que_nao_existe_e_sucesso(self):
        agwrite.postit_salvar("01-A/nota.md", postit("aaaa"))
        r = agwrite.postit_apagar("01-A/nota.md", "zzzz")
        self.assertEqual(r, {"ok": True})

    def test_documento_sem_nenhum_postit_e_sucesso(self):
        r = agwrite.postit_apagar("01-A/nota.md", "zzzz")
        self.assertEqual(r, {"ok": True})
        self.assertFalse(os.path.exists(self.caminho("agLocalSite/dados/postits")))

    def test_id_invalido_ainda_e_validado(self):
        with self.assertRaises(agwrite.Erro) as c:
            agwrite.postit_apagar("01-A/nota.md", "AB")
        self.assertEqual(c.exception.codigo, "postit")

    def test_ultimo_apagado_remove_arquivo_e_pastas_vazias(self):
        agwrite.postit_salvar("02-B/sub/x.md", postit("aaaa"))
        caminho = self.caminho("agLocalSite/dados/postits/02-B/sub/x.json")
        self.assertTrue(os.path.exists(caminho))
        agwrite.postit_apagar("02-B/sub/x.md", "aaaa")
        self.assertFalse(os.path.exists(caminho))
        self.assertFalse(os.path.exists(self.caminho("agLocalSite/dados/postits/02-B/sub")))
        self.assertFalse(os.path.exists(self.caminho("agLocalSite/dados/postits/02-B")))
        self.assertTrue(os.path.exists(self.caminho("agLocalSite/dados/postits")))  # a raiz em si fica

    def test_pasta_nao_esvaziada_fica(self):
        agwrite.postit_salvar("02-B/sub/x.md", postit("aaaa"))
        escrever(self.tmp, "02-B/y.md", "# Y\n")
        agwrite.postit_salvar("02-B/y.md", postit("bbbb"))
        agwrite.postit_apagar("02-B/sub/x.md", "aaaa")
        self.assertFalse(os.path.exists(self.caminho("agLocalSite/dados/postits/02-B/sub")))
        self.assertTrue(os.path.exists(self.caminho("agLocalSite/dados/postits/02-B/y.json")))  # a pasta 02-B não é apagada


class VersaoEEstado(Base):
    def test_mudar_postit_muda_carimbo_postits_e_nao_o_carimbo_nem_roda_o_sync(self):
        a = agwrite.versao()
        agwrite.postit_salvar("01-A/nota.md", postit())
        b = agwrite.versao()
        self.assertEqual(a["carimbo"], b["carimbo"])
        self.assertNotEqual(a["carimbo_postits"], b["carimbo_postits"])
        self.assertEqual(len(b["carimbo_postits"]), 16)

    def test_estado_traz_postits_e_ignora_documento_apagado(self):
        agwrite.postit_salvar("01-A/nota.md", postit("aaaa"))
        agwrite.postit_salvar("02-B/sub/x.md", postit("bbbb"))
        e = agwrite.estado()
        self.assertEqual(set(e["postits"]), {"01-A/nota.md", "02-B/sub/x.md"})
        self.assertEqual(len(e["postits"]["01-A/nota.md"]), 1)
        os.remove(self.caminho("02-B/sub/x.md"))
        e2 = agwrite.estado()
        self.assertEqual(set(e2["postits"]), {"01-A/nota.md"})
        json.dumps(e2)  # serializa

    def test_documento_sem_postit_nao_aparece_no_mapa(self):
        self.assertEqual(agwrite.estado()["postits"], {})


class Http(Base):
    """As rotas de verdade, pelo servidor de verdade."""

    def setUp(self):
        super().setUp()
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

    def pedir(self, metodo, rota, corpo=None, host=None, origin="auto", tipo="application/json"):
        c = http.client.HTTPConnection("127.0.0.1", self.porta, timeout=5)
        c.putrequest(metodo, rota, skip_host=True)
        if host is not False:
            c.putheader("Host", f"localhost:{self.porta}" if host is None else host)
        if origin == "auto":
            origin = f"http://localhost:{self.porta}"
        if origin:
            c.putheader("Origin", origin)
        dados = json.dumps(corpo).encode("utf-8") if corpo is not None else b""
        c.putheader("Content-Type", tipo)
        c.putheader("Content-Length", str(len(dados)))
        c.endheaders(dados)
        r = c.getresponse()
        texto = r.read().decode("utf-8")
        c.close()
        return r.status, (json.loads(texto) if texto.startswith("{") else texto)

    def test_criar_e_apagar_pela_rota(self):
        s, r = self.pedir("POST", "/api/postit", {"file": "01-A/nota.md", "postit": postit()})
        self.assertEqual((s, r), (200, {"ok": True}))
        self.assertTrue(os.path.exists(self.caminho("agLocalSite/dados/postits/01-A/nota.json")))
        s, r = self.pedir("POST", "/api/postit/apagar", {"file": "01-A/nota.md", "id": "k3f9a1"})
        self.assertEqual((s, r), (200, {"ok": True}))
        self.assertFalse(os.path.exists(self.caminho("agLocalSite/dados/postits/01-A/nota.json")))

    def test_host_estranho_recusado(self):
        s, e = self.pedir("POST", "/api/postit", {"file": "01-A/nota.md", "postit": postit()}, host="evil.com")
        self.assertEqual((s, e["codigo"]), (403, "host"))
        self.assertFalse(os.path.exists(self.caminho("agLocalSite/dados/postits")))

    def test_origin_estranho_recusado(self):
        s, e = self.pedir("POST", "/api/postit", {"file": "01-A/nota.md", "postit": postit()}, origin="http://evil.com")
        self.assertEqual((s, e["codigo"]), (403, "origem"))

    def test_content_type_errado_recusado(self):
        s, e = self.pedir("POST", "/api/postit", {"file": "01-A/nota.md", "postit": postit()}, tipo="text/plain")
        self.assertEqual((s, e["codigo"]), (415, "tipo"))

    def test_erro_nao_expoe_caminho_absoluto(self):
        s, e = self.pedir("POST", "/api/postit", {"file": "../../etc/passwd", "postit": postit()})
        self.assertNotIn(self.tmp, json.dumps(e))


if __name__ == "__main__":
    unittest.main()


class Robustez(Base):
    def test_arquivo_de_postits_com_item_corrompido_nao_derruba_salvar_nem_apagar(self):
        caminho = self.caminho("agLocalSite/dados/postits/01-A/nota.json")
        os.makedirs(os.path.dirname(caminho))
        with open(caminho, "w", encoding="utf-8") as f:
            json.dump({"postits": [1, {"x": 1}, {"id": 5}, postit("bom1", texto="fica")]}, f)
        agwrite.postit_salvar("01-A/nota.md", postit("novo", texto="n"))
        with open(caminho, encoding="utf-8") as f:
            ids = [p["id"] for p in json.load(f)["postits"]]
        self.assertEqual(ids, ["bom1", "novo"])
        self.assertEqual(agwrite.postit_apagar("01-A/nota.md", "bom1"), {"ok": True})
