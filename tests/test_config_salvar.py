"""Estado, gravação, histórico e desfazer do config.json pelo painel (agwrite.config_*). Cópia temporária."""
import json
import os
import sys
import unittest
from unittest import mock

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)
sys.path.insert(0, os.path.join(RAIZ, "tests"))
import agwrite
import sync
import test_agwrite as ta   # módulo, não as classes: senão o unittest roda os testes de lá de novo aqui

escrever = ta.escrever
Erro = agwrite.Erro


class Base(ta.Base):
    def cfg(self):
        with open(sync.CONFIG_PATH, encoding="utf-8-sig") as f:
            return json.load(f)

    def cfg_bytes(self):
        with open(sync.CONFIG_PATH, "rb") as f:
            return f.read()

    def escreve(self, texto, dados=None):
        with open(sync.CONFIG_PATH, "wb") as f:
            f.write(texto.encode("utf-8") if dados is None else dados)

    def versao(self):
        return agwrite.config_estado()["versao"]

    def copias(self):
        pasta = os.path.join(sync.DADOS_DIR, "config-historico")
        return sorted(os.listdir(pasta)) if os.path.isdir(pasta) else []

    def erro(self, f, *a):
        with self.assertRaises(Erro) as c:
            f(*a)
        return c.exception


class Estado(Base):
    def test_sem_arquivo(self):
        e = agwrite.config_estado()
        self.assertEqual(set(e), {"legivel", "valores", "padroes", "somente_leitura", "pastas", "paletas", "limites", "versao", "historico", "site"})
        self.assertTrue(e["legivel"])
        self.assertEqual((e["versao"], e["valores"]), ("ausente", {}))   # Foco 3: projeto novo abre com os padrões

    def test_com_arquivo_so_chaves_editaveis(self):
        self.escreve(json.dumps({"titulo": "X", "raiz": ".", "porta": 8100, "minha": 1, "rotulos": {"01-A": "Um"}}))
        e = agwrite.config_estado()
        self.assertEqual(e["valores"], {"titulo": "X", "rotulos": {"01-A": "Um"}})
        self.assertNotEqual(e["versao"], "ausente")
        self.assertEqual(e["somente_leitura"], {"raiz": sync.ROOT, "prefixo_url": "_ag", "porta": 8100, "arquivo": sync.CONFIG_PATH})
        pastas = {p["nome"]: p["rotulo"] for p in e["pastas"]}
        self.assertEqual(pastas["01-A"], "Um")
        self.assertEqual(pastas["02-B"], "")

    def test_porta_padrao(self):
        self.assertEqual(agwrite.config_estado()["somente_leitura"]["porta"], 8000)

    def test_padroes(self):
        p = agwrite.config_estado()["padroes"]
        self.assertEqual(p["titulo"], os.path.basename(self.tmp))
        self.assertEqual(p["textos"], sync.TEXTOS_PADRAO)
        self.assertEqual(p["home_prioridade"], sync.HOME_PRIORITY)
        self.assertEqual(p["tema"], {"paleta": "padrao", "modo": "claro"})
        self.assertIn("node_modules", p["ignoradas_sempre"])

    def test_textos_padrao_batem_com_o_site(self):
        texto = ""
        for rel in ("index.html", "js/app.js", "js/editor-ui.js", "js/kanban-view.js"):
            with open(os.path.join(RAIZ, "site", *rel.split("/")), encoding="utf-8") as f:
                texto += f.read()
        for chave, valor in sync.TEXTOS_PADRAO.items():
            self.assertIn(valor, texto, chave)

    def test_historico_conta_as_copias(self):
        self.assertEqual(agwrite.config_estado()["historico"], 0)
        agwrite.config_salvar({"titulo": "A"}, "ausente")
        self.assertEqual(agwrite.config_estado()["historico"], 0)   # a primeira gravação não tinha arquivo anterior
        agwrite.config_salvar({"titulo": "B"}, self.versao())
        self.assertEqual(agwrite.config_estado()["historico"], 1)
        agwrite.config_desfazer()
        self.assertEqual(agwrite.config_estado()["historico"], 2)

    def test_paletas_e_limites(self):
        e = agwrite.config_estado()
        self.assertEqual([p["nome"] for p in e["paletas"]], ["padrao", "oceano", "floresta", "grafite", "ameixa"])
        self.assertEqual(e["paletas"][1], {"nome": "oceano", "rotulo": "Oceano"})
        self.assertEqual(e["limites"], sync.LIMITES)

    def test_arquivo_quebrado(self):
        self.escreve('{\n  "titulo": "x",\n  "ignorar": [,\n}')
        e = agwrite.config_estado()
        self.assertFalse(e["legivel"])
        self.assertEqual(e["valores"], {})
        self.assertEqual(e["problema"]["linha"], 3)
        self.assertIsInstance(e["problema"]["coluna"], int)
        self.assertTrue(e["problema"]["mensagem"])

    def test_paleta_desconhecida_no_arquivo(self):   # Foco 5
        self.escreve(json.dumps({"tema": {"paleta": "neon", "modo": "roxo"}}))
        e = agwrite.config_estado()
        self.assertEqual(e["valores"]["tema"]["paleta"], "neon")           # o que está no arquivo
        self.assertEqual(e["site"]["tema"], {"paleta": "padrao", "modo": "claro"})   # o que a página usa


class Salvar(Base):
    def test_cria_arquivo_ausente_sem_historico(self):
        r = agwrite.config_salvar({"titulo": "Novo"}, "ausente")
        self.assertEqual(self.cfg(), {"titulo": "Novo"})
        self.assertEqual(self.copias(), [])
        self.assertEqual(r["valores"], {"titulo": "Novo"})
        self.assertNotEqual(r["versao"], "ausente")
        self.assertEqual(r["site"]["titulo"], "Novo")

    def test_preserva_desconhecidas_somente_leitura_e_ordem(self):
        self.escreve('{"raiz": ".", "minha": {"x": 1}, "titulo": "A", "porta": 8100}')
        agwrite.config_salvar({"titulo": "B", "subtitulo": "S"}, self.versao())
        c = self.cfg()
        self.assertEqual(list(c), ["raiz", "minha", "titulo", "porta", "subtitulo"])
        self.assertEqual((c["raiz"], c["minha"], c["porta"], c["titulo"]), (".", {"x": 1}, 8100, "B"))
        self.assertEqual(len(self.copias()), 1)

    def test_preserva_crlf(self):
        self.escreve('{\r\n  "titulo": "A"\r\n}\r\n')
        agwrite.config_salvar({"titulo": "B"}, self.versao())
        dados = self.cfg_bytes()
        self.assertIn(b"\r\n", dados)
        self.assertNotIn(b"\n", dados.replace(b"\r\n", b""))

    def test_le_arquivo_com_bom(self):
        self.escreve("", dados=b"\xef\xbb\xbf" + '{"titulo": "Ol\u00e1", "minha": 1}'.encode("utf-8"))
        agwrite.config_salvar({"subtitulo": "S"}, self.versao())
        self.assertEqual(self.cfg(), {"titulo": "Olá", "minha": 1, "subtitulo": "S"})

    def test_sem_mudancas_nao_grava(self):   # Foco 1
        self.escreve('{"titulo": "A"}')
        v, antes = self.versao(), self.cfg_bytes()
        for valores in ({}, {"titulo": "A"}, {"subtitulo": None}):   # nada a mudar, ou mudar para o que já é
            r = agwrite.config_salvar(valores, v)
            self.assertEqual(r["versao"], v)
        self.assertEqual(self.cfg_bytes(), antes)
        self.assertEqual(self.copias(), [])

    def test_texto_hostil_gravado_literal(self):   # Foco 2
        agwrite.config_salvar({"titulo": ' <b>"x"</b> ✓ '}, "ausente")
        self.assertEqual(self.cfg()["titulo"], '<b>"x"</b> ✓')
        self.assertIn("✓".encode("utf-8"), self.cfg_bytes())   # sem \u2713: o arquivo continua legível

    def test_duas_abas_com_a_mesma_base(self):   # Foco 4
        v = self.versao()
        agwrite.config_salvar({"titulo": "Aba 1"}, v)
        e = self.erro(agwrite.config_salvar, {"titulo": "Aba 2"}, v)
        self.assertEqual((e.status, e.codigo), (409, "conflito"))
        self.assertEqual(e.extra["valores"], {"titulo": "Aba 1"})
        self.assertEqual(e.extra["versao"], self.versao())
        self.assertEqual(self.cfg(), {"titulo": "Aba 1"})

    def test_mudou_por_fora(self):
        self.escreve('{"titulo": "A"}')
        v = self.versao()
        self.escreve('{"titulo": "editado à mão"}')
        os.utime(sync.CONFIG_PATH, ns=(1, 1))   # mtime diferente, sem depender da resolução do relógio
        self.assertEqual(self.erro(agwrite.config_salvar, {"titulo": "B"}, v).codigo, "conflito")

    def test_arquivo_quebrado_recusa_e_nao_altera(self):
        self.escreve('{"titulo": ')
        antes = self.cfg_bytes()
        e = self.erro(agwrite.config_salvar, {"titulo": "B"}, self.versao())
        self.assertEqual((e.status, e.codigo), (409, "config_ilegivel"))
        self.assertIn("linha", e.extra)
        self.assertEqual(self.cfg_bytes(), antes)
        self.assertEqual(self.copias(), [])

    def test_somente_leitura_recusada(self):
        self.escreve('{"titulo": "A"}')
        antes = self.cfg_bytes()
        for chave in ("raiz", "prefixo_url", "porta"):
            e = self.erro(agwrite.config_salvar, {chave: "x"}, self.versao())
            self.assertEqual((e.status, e.codigo, e.extra["campo"]), (400, "somente_leitura", chave))
        self.assertEqual(self.cfg_bytes(), antes)

    def test_validacao_devolve_o_campo(self):
        e = self.erro(agwrite.config_salvar, {"textos": {"grafo": "g" * 121}}, "ausente")
        self.assertEqual((e.status, e.codigo, e.extra["campo"]), (400, "validacao", "textos.grafo"))
        e = self.erro(agwrite.config_salvar, "x", "ausente")
        self.assertEqual((e.codigo, e.extra["campo"]), ("validacao", "valores"))

    def test_base_versao_obrigatoria(self):
        for ruim in (None, 5, ["x"]):
            e = self.erro(agwrite.config_salvar, {"titulo": "x"}, ruim)
            self.assertEqual((e.status, e.codigo), (400, "corpo"))

    def test_historico_copia_e_poda(self):
        agwrite.config_salvar({"titulo": "T0"}, "ausente")
        for i in range(1, 26):
            agwrite.config_salvar({"titulo": f"T{i}"}, self.versao())
        copias = self.copias()
        self.assertEqual(len(copias), agwrite.MAX_COPIAS)
        self.assertTrue(all(c.endswith(".json") for c in copias))
        with open(os.path.join(sync.DADOS_DIR, "config-historico", copias[-1]), encoding="utf-8") as f:
            self.assertEqual(json.load(f), {"titulo": "T24"})   # a mais recente é a versão anterior à última gravação

    def test_falha_ao_copiar_deixa_tudo_intacto(self):
        self.escreve('{"titulo": "A"}')
        antes, v = self.cfg_bytes(), self.versao()
        with mock.patch("agwrite.shutil.copy2", side_effect=OSError("disco cheio")):
            e = self.erro(agwrite.config_salvar, {"titulo": "B"}, v)
        self.assertEqual((e.status, e.codigo), (500, "copia"))
        self.assertEqual(self.cfg_bytes(), antes)

    def test_falha_na_troca_deixa_o_original_e_nenhum_temporario(self):
        self.escreve('{"titulo": "A"}')
        antes, v = self.cfg_bytes(), self.versao()
        with mock.patch("agwrite.os.replace", side_effect=OSError("falhou")):
            e = self.erro(agwrite.config_salvar, {"titulo": "B"}, v)
        self.assertEqual((e.status, e.codigo), (500, "gravar"))
        self.assertEqual(self.cfg_bytes(), antes)
        self.assertEqual([f for f in os.listdir(self.ag) if f.endswith(".tmp")], [])

    def test_sincroniza_antes_de_responder(self):
        antes = agwrite.versao()["carimbo"]
        agwrite.config_salvar({"titulo": "Sincronizado", "tema": {"paleta": "oceano", "modo": "escuro"}}, "ausente")
        with open(sync.CONTENT_JS_PATH, encoding="utf-8") as f:
            self.assertIn("Sincronizado", f.read())
        with open(sync.TEMA_DADOS_JS_PATH, encoding="utf-8") as f:
            self.assertIn('"paleta": "oceano"', f.read())
        self.assertNotEqual(agwrite.versao()["carimbo"], antes)


class Desfazer(Base):
    def test_ida_e_volta(self):
        agwrite.config_salvar({"titulo": "A"}, "ausente")
        agwrite.config_salvar({"titulo": "B"}, self.versao())
        self.assertEqual(agwrite.config_desfazer()["valores"], {"titulo": "A"})
        self.assertEqual(self.cfg(), {"titulo": "A"})
        self.assertEqual(agwrite.config_desfazer()["valores"], {"titulo": "B"})   # desfazer duas vezes volta ao ponto de partida

    def test_sem_historico(self):
        e = self.erro(agwrite.config_desfazer)
        self.assertEqual((e.status, e.codigo), (409, "sem_historico"))

    def test_funciona_com_o_arquivo_quebrado(self):
        agwrite.config_salvar({"titulo": "A"}, "ausente")
        agwrite.config_salvar({"titulo": "B"}, self.versao())
        self.escreve('{"titulo": ')   # estragado à mão
        n = len(self.copias())
        r = agwrite.config_desfazer()
        self.assertTrue(r["legivel"])
        self.assertEqual(self.cfg(), {"titulo": "A"})
        self.assertEqual(len(self.copias()), n + 1)   # o quebrado virou cópia
        with open(os.path.join(sync.DADOS_DIR, "config-historico", self.copias()[-1]), encoding="utf-8") as f:
            self.assertEqual(f.read(), '{"titulo": ')

    def test_sincroniza(self):
        agwrite.config_salvar({"titulo": "A"}, "ausente")
        agwrite.config_salvar({"titulo": "B"}, self.versao())
        agwrite.config_desfazer()
        with open(sync.CONTENT_JS_PATH, encoding="utf-8") as f:
            self.assertIn('"titulo": "A"', f.read())


if __name__ == "__main__":
    unittest.main()
