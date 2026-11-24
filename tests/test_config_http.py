"""Rotas do painel de configuração (GET/POST /api/config e /api/config/desfazer): contrato, segurança e fuzz. Servidor temporário."""
import http.client
import json
import os
import sys
import unittest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)
sys.path.insert(0, os.path.join(RAIZ, "tests"))
import sync
import test_config as tc   # módulo (não as classes): o Servido dele sobe o servidor temporário

CHAVES_ESTADO = {"legivel", "valores", "padroes", "somente_leitura", "pastas", "paletas", "limites", "versao", "historico", "site"}


class Rotas(tc.Servido):
    def pedir(self, metodo, rota, corpo=None, host=True, origin=True, tipo="application/json", tamanho=None):
        """(status, json). corpo é objeto Python (vira JSON) ou bytes crus; tamanho força o Content-Length (sem enviar o corpo)."""
        ok = f"localhost:{self.porta}"
        c = http.client.HTTPConnection("127.0.0.1", self.porta, timeout=5)
        c.putrequest(metodo, rota, skip_host=True)
        c.putheader("Host", ok if host is True else host)
        dados = b"" if corpo is None else (corpo if isinstance(corpo, bytes) else json.dumps(corpo).encode("utf-8"))
        if metodo == "POST":
            if origin is not False:
                c.putheader("Origin", f"http://{ok}" if origin is True else origin)
            if tipo:
                c.putheader("Content-Type", tipo)
            c.putheader("Content-Length", str(len(dados) if tamanho is None else tamanho))
        c.endheaders(dados if tamanho is None else b"")
        r = c.getresponse()
        texto = r.read().decode("utf-8")
        c.close()
        try:
            return r.status, json.loads(texto)
        except ValueError:
            return r.status, texto

    def versao(self):
        return self.pedir("GET", "/api/config")[1]["versao"]

    def cfg(self):
        with open(sync.CONFIG_PATH, encoding="utf-8") as f:
            return json.load(f)

    def test_get_contrato(self):
        s, e = self.pedir("GET", "/api/config")
        self.assertEqual(s, 200)
        self.assertEqual(set(e), CHAVES_ESTADO)
        self.assertEqual(e["versao"], "ausente")

    def test_checagens_de_seguranca(self):
        self.assertEqual(self.pedir("GET", "/api/config", host="evil.com")[0], 403)
        self.assertEqual(self.pedir("POST", "/api/config", {"valores": {}}, host="evil.com")[0], 403)
        self.assertEqual(self.pedir("POST", "/api/config", {"valores": {}}, origin=False)[0], 403)
        self.assertEqual(self.pedir("POST", "/api/config", {"valores": {}}, origin="http://evil.com")[0], 403)
        self.assertEqual(self.pedir("POST", "/api/config", {"valores": {}}, tipo="text/plain")[0], 415)
        self.assertEqual(self.pedir("POST", "/api/config/desfazer", {}, origin=False)[0], 403)
        self.assertFalse(os.path.exists(sync.CONFIG_PATH))

    def test_corpo_acima_de_64kb(self):
        s, e = self.pedir("POST", "/api/config", tamanho=70 * 1024)
        self.assertEqual((s, e["codigo"]), (413, "grande"))
        self.assertIn("64 KB", e["erro"])

    def test_corpo_invalido(self):
        for ruim in (b"", b"{", b"[1]", b'"x"', b"\xff\xfe"):
            s, e = self.pedir("POST", "/api/config", ruim)
            self.assertEqual((s, e["codigo"]), (400, "json"), ruim)

    def test_post_valido(self):
        s, e = self.pedir("POST", "/api/config", {"valores": {"titulo": "Via HTTP", "tema": {"paleta": "oceano"}}, "base_versao": "ausente"})
        self.assertEqual(s, 200)
        self.assertEqual(self.cfg(), {"titulo": "Via HTTP", "tema": {"paleta": "oceano"}})
        self.assertEqual(set(e), CHAVES_ESTADO)
        self.assertEqual(e["valores"]["titulo"], "Via HTTP")
        self.assertEqual(e["versao"], self.versao())

    def test_somente_leitura_recusada_sem_gravar(self):
        for chave in ("raiz", "prefixo_url", "porta"):
            s, e = self.pedir("POST", "/api/config", {"valores": {chave: "x"}, "base_versao": "ausente"})
            self.assertEqual((s, e["codigo"], e["campo"]), (400, "somente_leitura", chave))
        self.assertFalse(os.path.exists(sync.CONFIG_PATH))

    def test_campo_invalido_e_pedido_incompleto(self):
        s, e = self.pedir("POST", "/api/config", {"valores": {"textos": {"grafo": "g" * 121}}, "base_versao": "ausente"})
        self.assertEqual((s, e["codigo"], e["campo"]), (400, "validacao", "textos.grafo"))
        self.assertEqual(self.pedir("POST", "/api/config", {"valores": {"titulo": "x"}})[1]["codigo"], "corpo")
        self.assertEqual(self.pedir("POST", "/api/config", {"base_versao": "ausente"})[1]["codigo"], "validacao")

    def test_conflito(self):
        self.pedir("POST", "/api/config", {"valores": {"titulo": "A"}, "base_versao": "ausente"})
        s, e = self.pedir("POST", "/api/config", {"valores": {"titulo": "B"}, "base_versao": "ausente"})
        self.assertEqual((s, e["codigo"]), (409, "conflito"))
        self.assertEqual(e["valores"], {"titulo": "A"})

    def test_desfazer_so_por_post(self):
        self.pedir("POST", "/api/config", {"valores": {"titulo": "A"}, "base_versao": "ausente"})
        self.pedir("POST", "/api/config", {"valores": {"titulo": "B"}, "base_versao": self.versao()})
        self.assertEqual(self.pedir("GET", "/api/config/desfazer")[0], 404)
        s, e = self.pedir("POST", "/api/config/desfazer", {})
        self.assertEqual((s, e["valores"]), (200, {"titulo": "A"}))
        s, e = self.pedir("POST", "/api/config/desfazer", {})
        self.assertEqual((s, e["valores"]), (200, {"titulo": "B"}))

    def test_desfazer_sem_historico(self):
        s, e = self.pedir("POST", "/api/config/desfazer", {})
        self.assertEqual((s, e["codigo"]), (409, "sem_historico"))

    def test_json_aninhado_demais_nao_vira_500(self):
        # 20 mil colchetes cabem em 64 KB; o json.loads estoura a pilha (RecursionError, que não é ValueError)
        for rota in ("/api/config", "/api/salvar"):
            s, e = self.pedir("POST", rota, b"[" * 20000)
            self.assertEqual((s, e["codigo"]), (400, "json"), rota)

    def test_fuzz_dos_valores(self):
        antes = {os.path.join(d, f) for d, _, fs in os.walk(self.tmp) for f in fs}
        lixo = [None, 0, -1, 1.5, True, "", " ", "\x00", "\ud800", "../../x", "a/b", "a\\b", "x" * 5000, [], {}, [None], ["a"] * 300,
                {"a": {"b": {"c": [1, 2, {"d": None}]}}}, [[[[[]]]]], {"": ""}, {"../x": "y"}, ["a", "a"], "<script>alert(1)</script>"]
        chaves = ["titulo", "subtitulo", "etiqueta", "titulo_aba", "textos", "tema", "ignorar", "rotulos", "home_prioridade",
                  "raiz", "prefixo_url", "porta", "inventada", "../x", "", "__proto__"]
        proibidos = []
        for chave in chaves:
            for v in lixo:
                s, e = self.pedir("POST", "/api/config", {"valores": {chave: v}, "base_versao": self.versao()})
                if s not in (200, 400, 409):
                    proibidos.append((chave, repr(v)[:30], s))
        self.assertEqual(proibidos, [])
        depois = {os.path.join(d, f) for d, _, fs in os.walk(self.tmp) for f in fs}
        novos_fora = [p for p in depois - antes if not p.startswith(self.ag + os.sep)]
        self.assertEqual(novos_fora, [])   # nada novo fora de agLocalSite/ (config.json, dados/ e os gerados)
        self.assertTrue(all(os.path.basename(p) != "x" for p in depois))
        if os.path.exists(sync.CONFIG_PATH):
            self.cfg()   # o que sobrou no arquivo continua sendo JSON válido


if __name__ == "__main__":
    unittest.main()
