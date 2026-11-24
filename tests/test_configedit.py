"""configedit: validação e mesclagem puras do config.json (seções 5.1 e 5.2 da spec). Sem arquivo e sem rede."""
import copy
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import configedit
from configedit import ErroValidacao, mesclar, validar


def campo_do_erro(valores):
    with unittest.TestCase().assertRaises(ErroValidacao) as c:
        validar(valores)
    return c.exception.campo


class Validar(unittest.TestCase):
    def test_aceita_parcial_e_faz_strip(self):
        self.assertEqual(validar({"titulo": "  Meu Projeto  "}), {"titulo": "Meu Projeto"})
        self.assertEqual(validar({}), {})
        self.assertEqual(validar({"titulo": None}), {"titulo": None})

    def test_vazio_vira_remocao_menos_o_rodape(self):
        self.assertEqual(validar({"titulo": "", "subtitulo": "   ", "etiqueta": "", "titulo_aba": ""}),
                         {"titulo": None, "subtitulo": None, "etiqueta": None, "titulo_aba": None})
        self.assertEqual(validar({"textos": {"grafo": "", "quadro": "  ", "rodape": "", "menu": None}}),
                         {"textos": {"grafo": None, "quadro": None, "rodape": "", "menu": None}})

    def test_somente_leitura_recusada_mandando_editar_o_arquivo(self):
        for chave in ("raiz", "prefixo_url", "porta"):
            with self.assertRaises(ErroValidacao) as c:
                validar({chave: "x"})
            self.assertEqual(c.exception.campo, chave)
            self.assertIn("config.json", c.exception.msg)

    def test_chave_desconhecida_e_valores_fora_de_objeto(self):
        self.assertEqual(campo_do_erro({"inventada": 1}), "inventada")
        self.assertEqual(campo_do_erro([]), "valores")
        self.assertEqual(campo_do_erro("x"), "valores")

    def test_tipos_errados(self):
        for valores, campo in (({"titulo": 5}, "titulo"), ({"subtitulo": ["x"]}, "subtitulo"), ({"textos": ["x"]}, "textos"),
                               ({"textos": {"grafo": 5}}, "textos.grafo"), ({"tema": "x"}, "tema"),
                               ({"ignorar": "a"}, "ignorar"), ({"ignorar": [5]}, "ignorar"), ({"rotulos": []}, "rotulos"),
                               ({"rotulos": {"a": 5}}, "rotulos"), ({"home_prioridade": {"a": 1}}, "home_prioridade")):
            self.assertEqual(campo_do_erro(valores), campo, valores)

    def test_tamanhos_de_texto(self):
        self.assertEqual(validar({"titulo": "a" * 120}), {"titulo": "a" * 120})
        self.assertEqual(campo_do_erro({"titulo": "a" * 121}), "titulo")
        self.assertEqual(validar({"textos": {"rodape": "r" * 2000}}), {"textos": {"rodape": "r" * 2000}})
        self.assertEqual(campo_do_erro({"textos": {"rodape": "r" * 2001}}), "textos.rodape")
        self.assertEqual(campo_do_erro({"textos": {"grafo": "g" * 121}}), "textos.grafo")

    def test_textos_so_com_chaves_conhecidas(self):
        self.assertEqual(campo_do_erro({"textos": {"inventado": "x"}}), "textos.inventado")
        for chave in ("grafo", "quadro", "mais", "menu", "tema_claro", "tema_escuro", "home", "rodape"):
            self.assertEqual(validar({"textos": {chave: "ok"}}), {"textos": {chave: "ok"}})

    def test_tema(self):
        self.assertEqual(validar({"tema": {"paleta": "oceano", "modo": "sistema"}}), {"tema": {"paleta": "oceano", "modo": "sistema"}})
        self.assertEqual(validar({"tema": {"paleta": None}}), {"tema": {"paleta": None}})
        self.assertEqual(campo_do_erro({"tema": {"paleta": "neon"}}), "tema.paleta")
        self.assertEqual(campo_do_erro({"tema": {"modo": "roxo"}}), "tema.modo")
        self.assertEqual(campo_do_erro({"tema": {"fonte": "x"}}), "tema.fonte")
        self.assertEqual(campo_do_erro({"tema": {"paleta": ["oceano"]}}), "tema.paleta")   # não hashable não pode quebrar

    def test_ignorar(self):
        self.assertEqual(validar({"ignorar": [" dist ", "tmp"]}), {"ignorar": ["dist", "tmp"]})
        self.assertEqual(validar({"ignorar": []}), {"ignorar": []})
        for lixo in (["a/b"], ["a\\b"], [""], ["  "], ["x" * 101], ["a", "a"]):
            self.assertEqual(campo_do_erro({"ignorar": lixo}), "ignorar", lixo)
        self.assertEqual(campo_do_erro({"ignorar": ["i%d" % n for n in range(201)]}), "ignorar")
        self.assertEqual(len(validar({"ignorar": ["i%d" % n for n in range(200)]})["ignorar"]), 200)

    def test_rotulos(self):
        self.assertEqual(validar({"rotulos": {" 02-Produtos ": " 02 · Produtos "}}), {"rotulos": {"02-Produtos": "02 · Produtos"}})
        self.assertEqual(validar({"rotulos": {"a": ""}}), {"rotulos": {}})   # rótulo vazio = sem rótulo, a entrada some
        for lixo in ({"a/b": "x"}, {"a\\b": "x"}, {"": "x"}, {"x" * 101: "x"}, {"a": "r" * 121}):
            self.assertEqual(campo_do_erro({"rotulos": lixo}), "rotulos", lixo)
        self.assertEqual(campo_do_erro({"rotulos": {"p%d" % n: "x" for n in range(201)}}), "rotulos")

    def test_home_prioridade(self):
        self.assertEqual(validar({"home_prioridade": ["leia-me", "inicio"]}), {"home_prioridade": ["leia-me", "inicio"]})
        self.assertEqual(validar({"home_prioridade": []}), {"home_prioridade": []})
        for lixo in (["readme.md"], ["README.MD"], ["a/b"], [""], ["x" * 101], ["a", "a"]):
            self.assertEqual(campo_do_erro({"home_prioridade": lixo}), "home_prioridade", lixo)
        self.assertEqual(campo_do_erro({"home_prioridade": ["h%d" % n for n in range(51)]}), "home_prioridade")

    def test_texto_hostil_passa_literal(self):
        hostil = '<script>alert("x")</script> \'a\' ✓ \u202e'
        self.assertEqual(validar({"titulo": hostil})["titulo"], hostil.strip())

    def test_surrogate_solto_nao_se_grava(self):
        # "\ud800" vale em JSON, mas str.encode("utf-8") falha: tem de ser recusado na validação
        for valores, campo in (({"titulo": "a\ud800"}, "titulo"), ({"textos": {"grafo": "\ud800"}}, "textos.grafo"),
                               ({"ignorar": ["\ud800"]}, "ignorar"), ({"rotulos": {"\ud800": "x"}}, "rotulos"),
                               ({"rotulos": {"a": "\udfff"}}, "rotulos"), ({"home_prioridade": ["\ud800"]}, "home_prioridade")):
            self.assertEqual(campo_do_erro(valores), campo, valores)

    def test_chaves_editaveis_e_somente_leitura(self):
        self.assertEqual(configedit.SOMENTE_LEITURA, ("raiz", "prefixo_url", "porta"))
        self.assertEqual(configedit.CHAVES_EDITAVEIS,
                         ("titulo", "subtitulo", "etiqueta", "titulo_aba", "textos", "tema", "ignorar", "rotulos", "home_prioridade"))


class Mesclar(unittest.TestCase):
    def test_chave_de_topo_none_remove(self):
        self.assertEqual(mesclar({"titulo": "A", "porta": 8000}, {"titulo": None}), {"porta": 8000})
        self.assertEqual(mesclar({"a": 1}, {"titulo": None}), {"a": 1})   # remover o que não existe não falha

    def test_textos_e_tema_mesclam_subchave(self):
        atual = {"textos": {"grafo": "G", "quadro": "Q"}, "tema": {"paleta": "oceano", "modo": "escuro"}}
        self.assertEqual(mesclar(atual, {"textos": {"grafo": "Novo"}, "tema": {"modo": "claro"}}),
                         {"textos": {"grafo": "Novo", "quadro": "Q"}, "tema": {"paleta": "oceano", "modo": "claro"}})
        self.assertEqual(mesclar(atual, {"textos": {"grafo": None}})["textos"], {"quadro": "Q"})

    def test_objeto_que_fica_vazio_some(self):
        self.assertEqual(mesclar({"textos": {"grafo": "G"}}, {"textos": {"grafo": None}}), {})
        self.assertEqual(mesclar({}, {"textos": {"grafo": None}}), {})

    def test_listas_e_mapas_substituem_por_inteiro(self):
        atual = {"ignorar": ["a", "b"], "rotulos": {"x": "X", "y": "Y"}, "home_prioridade": ["a"]}
        novo = mesclar(atual, {"ignorar": ["c"], "rotulos": {"z": "Z"}, "home_prioridade": []})
        self.assertEqual(novo, {"ignorar": ["c"], "rotulos": {"z": "Z"}, "home_prioridade": []})

    def test_cria_textos_quando_nao_existia(self):
        self.assertEqual(mesclar({}, {"textos": {"rodape": ""}}), {"textos": {"rodape": ""}})

    def test_preserva_desconhecidas_somente_leitura_e_ordem(self):
        atual = {"raiz": "..", "minha_opcao": {"x": 1}, "titulo": "A", "porta": 8100, "prefixo_url": "wiki"}
        novo = mesclar(atual, {"titulo": "B", "subtitulo": "S"})
        self.assertEqual(list(novo), ["raiz", "minha_opcao", "titulo", "porta", "prefixo_url", "subtitulo"])
        self.assertEqual(novo["raiz"], "..")
        self.assertEqual(novo["minha_opcao"], {"x": 1})
        self.assertEqual(novo["titulo"], "B")

    def test_nao_altera_o_argumento(self):
        atual = {"textos": {"grafo": "G"}, "ignorar": ["a"]}
        copia = copy.deepcopy(atual)
        mesclar(atual, {"textos": {"grafo": "Novo", "menu": "M"}, "ignorar": ["z"]})
        self.assertEqual(atual, copia)


if __name__ == "__main__":
    unittest.main()
