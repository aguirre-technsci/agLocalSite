"""Tema do site (paleta e modo) vindo do config.json, o arquivo gerado tema-dados.js e o leitor estrito do config. Cópia temporária."""
import json
import os
import sys
import unittest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)
sys.path.insert(0, os.path.join(RAIZ, "tests"))
import sync
import test_agwrite as ta   # módulo, não as classes: senão o unittest roda os testes de lá de novo aqui

escrever = ta.escrever
NOMES = ["padrao", "oceano", "floresta", "grafite", "ameixa"]


def config(self, dados):
    escrever(self.ag, "config.json", json.dumps(dados))


class Tema(ta.Base):
    def test_tema_padrao(self):
        self.assertEqual(sync.tema(), {"paleta": "padrao", "modo": "claro"})

    def test_listas_fixas(self):
        self.assertEqual([n for n, _ in sync.PALETAS], NOMES)
        self.assertEqual([r for _, r in sync.PALETAS], ["Padrão", "Oceano", "Floresta", "Grafite", "Ameixa"])
        self.assertEqual(sync.MODOS, ("claro", "escuro", "sistema"))
        self.assertEqual(sync.LIMITES, {"texto": 120, "rodape": 2000, "itens_ignorar": 200, "nome": 100, "rotulos": 200, "home": 50})

    def test_tema_valido(self):
        config(self, {"tema": {"paleta": "oceano", "modo": "sistema"}})
        self.assertEqual(sync.tema(), {"paleta": "oceano", "modo": "sistema"})
        self.assertEqual(sync.avisos_config(), [])

    def test_tema_invalido_cai_no_padrao_com_aviso(self):
        config(self, {"tema": {"paleta": "neon", "modo": "roxo"}})
        self.assertEqual(sync.tema(), {"paleta": "padrao", "modo": "claro"})
        av = " ".join(sync.avisos_config())
        self.assertIn('"tema.paleta"', av)
        self.assertIn('"tema.modo"', av)

    def test_tema_de_tipo_errado(self):
        for ruim in ("x", 5, ["oceano"]):
            config(self, {"tema": ruim})
            self.assertEqual(sync.tema(), {"paleta": "padrao", "modo": "claro"})
            self.assertIn('"tema" precisa ser um objeto', " ".join(sync.avisos_config()))
        config(self, {"tema": {"paleta": ["x"], "modo": {"a": 1}}})   # valores não hashable não podem quebrar
        self.assertEqual(sync.tema(), {"paleta": "padrao", "modo": "claro"})

    def test_dados_site_tem_tema(self):
        config(self, {"tema": {"paleta": "ameixa", "modo": "escuro"}})
        self.assertEqual(sync.dados_site()["tema"], sync.tema())

    def test_tema_dados_gerado(self):
        config(self, {"tema": {"paleta": "oceano", "modo": "sistema"}})
        sync.escrever_arquivos(*sync.montar_dados())
        with open(sync.TEMA_DADOS_JS_PATH, encoding="utf-8") as f:
            js = f.read()
        self.assertIn("GERADO", js.splitlines()[0])
        self.assertIn('const AG_TEMA = {"paleta": "oceano", "modo": "sistema", "paletas": ["padrao", "oceano", "floresta", "grafite", "ameixa"]};', js)


class LeitorEstrito(ta.Base):
    def test_ausente_da_vazio(self):
        self.assertEqual(sync.ler_config_estrito(), {})

    def test_bom_e_aceito(self):
        with open(sync.CONFIG_PATH, "wb") as f:
            f.write(b"\xef\xbb\xbf" + '{"titulo": "Ol\u00e1"}'.encode("utf-8"))
        self.assertEqual(sync.ler_config_estrito(), {"titulo": "Olá"})

    def test_json_quebrado_levanta_com_linha_e_coluna(self):
        with open(sync.CONFIG_PATH, "w", encoding="utf-8") as f:
            f.write('{\n  "titulo": "x",\n  "ignorar": [,\n}')
        with self.assertRaises(sync.ConfigIlegivel) as c:
            sync.ler_config_estrito()
        self.assertIsInstance(c.exception.linha, int)
        self.assertIsInstance(c.exception.coluna, int)
        self.assertEqual(c.exception.linha, 3)
        self.assertTrue(c.exception.msg)

    def test_nao_objeto_levanta(self):
        for texto in ("[]", '"x"', "5", "null"):
            with open(sync.CONFIG_PATH, "w", encoding="utf-8") as f:
                f.write(texto)
            with self.assertRaises(sync.ConfigIlegivel, msg=texto):
                sync.ler_config_estrito()

    def test_bytes_invalidos_levantam(self):
        with open(sync.CONFIG_PATH, "wb") as f:
            f.write(b'{"titulo": "\xff\xfe"}')
        with self.assertRaises(sync.ConfigIlegivel):
            sync.ler_config_estrito()


if __name__ == "__main__":
    unittest.main()
