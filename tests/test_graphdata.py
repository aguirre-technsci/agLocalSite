import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import graphdata as g
import sync


class Normalize(unittest.TestCase):
    def test_casos(self):
        casos = {
            "Dados Abertos": "dados_abertos",
            "  #Algoritmo ": "algoritmo",
            "Otimização-Térmica": "otimizacao_termica",
            "3D": "3d",
            "dados/ONS": "dados/ons",
            "a__b": "a_b",
            "/a//b/": "a/b",
            "a_/_b": "a/b",
            "!!!": "",
        }
        for entrada, esperado in casos.items():
            self.assertEqual(g.normalize_tag(entrada), esperado, entrada)


class Frontmatter(unittest.TestCase):
    def test_valido(self):
        fm, body = g.split_frontmatter("---\ntags: [a, b]\n---\n# Título\ncorpo")
        self.assertEqual(fm, "tags: [a, b]")
        self.assertEqual(body, "# Título\ncorpo")

    def test_crlf_e_bom(self):
        fm, body = g.split_frontmatter("\ufeff---\r\ntags: [a]\r\n---\r\n# T")
        self.assertEqual(fm, "tags: [a]")
        self.assertEqual(body, "# T")

    def test_sem_frontmatter(self):
        texto = "# Título\n\ncorpo"
        self.assertEqual(g.split_frontmatter(texto), (None, texto))

    def test_linha_horizontal_nao_e_frontmatter(self):
        texto = "---\nIsto é um parágrafo qualquer.\n---\ncorpo"
        self.assertEqual(g.split_frontmatter(texto), (None, texto))

    def test_strip(self):
        self.assertEqual(g.strip_frontmatter("---\ntags: [a]\n---\nX"), "X")


class CuratedTags(unittest.TestCase):
    def tags(self, fm, warn=None):
        return g.parse_curated_tags(fm, warn)

    def test_lista_inline(self):
        self.assertEqual(self.tags("tags: [algoritmo, 3d, Dados Abertos]"), ["algoritmo", "3d", "dados_abertos"])

    def test_lista_com_aspas_e_hash(self):
        self.assertEqual(self.tags('tags: ["#a", \'b\']'), ["a", "b"])

    def test_escalar(self):
        self.assertEqual(self.tags("tags: a, b"), ["a", "b"])
        self.assertEqual(self.tags("tags: a b"), ["a", "b"])

    def test_lista_em_linhas(self):
        self.assertEqual(self.tags("title: x\ntags:\n  - a\n  - b c\nother: 1"), ["a", "b_c"])

    def test_chave_singular(self):
        self.assertEqual(self.tags("tag: solo"), ["solo"])

    def test_duplicadas_e_vazias_descartadas(self):
        self.assertEqual(self.tags("tags: [a, , A, !!!, b]"), ["a", "b"])

    def test_colchete_aberto_avisa_e_ignora(self):
        avisos = []
        self.assertEqual(self.tags("tags: [a, b", avisos.append), [])
        self.assertEqual(len(avisos), 1)

    def test_sem_campo_tags(self):
        self.assertEqual(self.tags("title: x"), [])


class FolderTags(unittest.TestCase):
    def test_aninhadas_sem_prefixo_numerico(self):
        self.assertEqual(
            g.folder_tags("02-Produtos-e-Modulos/Alfa/Alfa-Dashboard/README.md"),
            ["produtos_e_modulos", "produtos_e_modulos/alfa", "produtos_e_modulos/alfa/alfa_dashboard"],
        )

    def test_arquivo_na_raiz_nao_tem_tag_de_pasta(self):
        self.assertEqual(g.folder_tags("INICIO.md"), [])

    def test_barra_invertida(self):
        self.assertEqual(g.folder_tags("99-etc\\x.md"), ["etc"])


class TextTags(unittest.TestCase):
    def setUp(self):
        # 10 documentos: 'turbina' em 3 (vale), 'raro' em 1 (não vale), 'comum' em 8 (>= metade, não vale)
        self.bodies = {f"d{i}": "comum " + ("turbina " * 3 if i < 3 else "") + ("raro" if i == 0 else "") for i in range(8)}
        self.bodies["d8"] = "comum comum"
        self.bodies["d9"] = "nada"

    def test_df_minimo_e_maximo(self):
        t = g.text_tags(self.bodies)
        self.assertEqual(t["d0"], ["turbina"])
        self.assertEqual(t["d5"], [])

    def test_exclui_curadas(self):
        t = g.text_tags(self.bodies, {"d0": {"turbina"}})
        self.assertEqual(t["d0"], [])

    def test_limite_por_documento_e_ordem_alfabetica(self):
        palavras = "alfa beta gama delta epsilon zeta iota theta".split()
        b = {"x": " ".join(palavras), "y": " ".join(palavras)}
        b.update({f"z{i}": "outra coisa qualquer" for i in range(3)})
        self.assertEqual(g.text_tags(b)["x"], sorted(palavras)[:5])

    def test_ignora_codigo_url_e_palavras_vazias(self):
        b = {"a": "```\nzzzzcodigo\n```\nhttps://exemplo.com/zzzzurl pelas turbina", "b": "turbina pelas zzzzcodigo"}
        b.update({f"c{i}": "outra" for i in range(4)})
        self.assertEqual(g.text_tags(b)["a"], ["turbina"])


class Build(unittest.TestCase):
    def grupos(self, texto):
        it = {"id": "x", "title": "X", "file": "01-A/B/doc.md", "fallback": texto}
        return [{"id": "01-a", "label": "01", "folder": "01-A", "items": [it]}]

    def test_estrutura(self):
        graph = g.build(self.grupos("---\ntags: [algoritmo]\n---\n# X"))
        d = graph["docs"][0]
        self.assertEqual(d["tags"]["curated"], ["algoritmo"])
        self.assertEqual(d["tags"]["folder"], ["a", "a/b"])
        self.assertEqual(set(d), {"id", "title", "file", "tags"})

    def test_frontmatter_sem_fechamento_avisa(self):
        avisos = []
        graph = g.build(self.grupos("---\ntags: [a]\n# X sem fechar"), avisos.append)
        self.assertEqual(graph["docs"][0]["tags"]["curated"], [])
        self.assertEqual(len(avisos), 1)

    def test_render_js_e_json_valido(self):
        graph = g.build(self.grupos("# X"))
        js = g.render_js(graph)
        self.assertTrue(js.rstrip().endswith(";"))
        self.assertEqual(json.loads(js.split("const AG_GRAPH = ", 1)[1].rsplit(";", 1)[0]), graph)


class TituloComFrontmatter(unittest.TestCase):
    def test_titulo_vem_do_corpo(self):
        t = sync.title_from_file("a/x.md", "", "---\ntags: [a]\n---\n# Meu Título\n")
        self.assertEqual(t, "Meu Título")

    def test_comentario_no_frontmatter_nao_vira_titulo(self):
        t = sync.title_from_file("a/x.md", "", "---\n# comentário yaml\ntags: [a]\n---\n# Título Real\n")
        self.assertEqual(t, "Título Real")


if __name__ == "__main__":
    unittest.main()
