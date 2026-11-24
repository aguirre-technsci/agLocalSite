"""Testes do agwrite.py e das rotas /api do serve.py. Rodam numa cópia temporária: nada toca os arquivos reais."""
import http.client
import json
import os
import shutil
import sys
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from unittest import mock

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)
import agwrite
import serve
import sync

CASOS = json.load(open(os.path.join(RAIZ, "tests", "casos_nota.json"), encoding="utf-8"))

INICIO = "---\ntags: [alfa]\n---\n# Início\n\n- [ ] um\n- [x] dois\n"


def escrever(base, rel, texto, binario=False):
    caminho = os.path.join(base, *rel.split("/"))
    os.makedirs(os.path.dirname(caminho), exist_ok=True)
    with open(caminho, "wb") as f:
        f.write(texto if binario else texto.encode("utf-8"))
    return caminho


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        escrever(self.tmp, "INICIO.md", INICIO)
        escrever(self.tmp, "01-A/nota.md", "# Nota A\n\ncorpo\n")
        escrever(self.tmp, "02-B/sub/x.md", "# X\n")
        escrever(self.tmp, "node_modules/ignorado.md", "# site\n")
        escrever(self.tmp, "agLocalSite/ignorado.md", "# tests\n")
        escrever(self.tmp, ".oculta/z.md", "# oculta\n")
        self.ag = os.path.join(self.tmp, "agLocalSite")
        os.makedirs(os.path.join(self.ag, "site", "js"))
        self._nomes = ("ROOT", "AG_DIR", "SITE_DIR", "DADOS_DIR", "CONFIG_PATH", "CONTENT_JS_PATH", "GRAPH_JS_PATH", "TEMA_DADOS_JS_PATH")
        self._velho = [getattr(sync, n) for n in self._nomes]
        sync.ROOT, sync.AG_DIR = self.tmp, self.ag
        sync.SITE_DIR, sync.DADOS_DIR = os.path.join(self.ag, "site"), os.path.join(self.ag, "dados")
        sync.CONFIG_PATH = os.path.join(self.ag, "config.json")
        sync.CONTENT_JS_PATH = os.path.join(self.ag, "site", "js", "content.js")
        sync.GRAPH_JS_PATH = os.path.join(self.ag, "site", "js", "graph-data.js")
        sync.TEMA_DADOS_JS_PATH = os.path.join(self.ag, "site", "js", "tema-dados.js")
        agwrite._ultimo = agwrite._dados = None
        self.mudo = mock.patch("builtins.print")  # o graphdata avisa no terminal; nos testes fica quieto
        self.mudo.start()

    def tearDown(self):
        self.mudo.stop()
        for n, v in zip(self._nomes, self._velho):
            setattr(sync, n, v)
        shutil.rmtree(self.tmp)

    def caminho(self, rel):
        return os.path.join(self.tmp, *rel.split("/"))

    def ler(self, rel):
        with open(self.caminho(rel), "rb") as f:
            return f.read().decode("utf-8")

    def mtime(self, rel):
        return agwrite.mtimes()[rel]


class Caminhos(Base):
    def test_caminhos_invalidos_nao_gravam(self):
        fora = os.path.join(os.path.dirname(self.tmp), "fora.md")
        ruins = ["../fora.md", "01-A/../../fora.md", fora, "/etc/passwd", "01-A/nota.txt", "01-A", "",
                 "node_modules/ignorado.md", "agLocalSite/ignorado.md", ".oculta/z.md", "agLocalSite/dados/historico/a.md",
                 "01-A/nao-existe.md", "01-A\\nota.md", None, 7]
        for ruim in ruins:
            with self.assertRaises(agwrite.Erro, msg=repr(ruim)) as c:
                agwrite.salvar(ruim, "x", "0")
            self.assertEqual((c.exception.status, c.exception.codigo), (400, "caminho"), repr(ruim))
        self.assertFalse(os.path.exists(fora))
        self.assertEqual(self.ler("01-A/nota.md"), "# Nota A\n\ncorpo\n")

    def test_docs_entra_e_pasta_do_config_fica_fora(self):
        # docs/ é pasta comum de projeto: entra. O que o config.json manda ignorar sai do menu e da escrita.
        escrever(self.tmp, "docs/specs/desenho.md", "# Desenho\n")
        escrever(self.tmp, "rascunhos/x.md", "# X\n")
        escrever(self.ag, "config.json", json.dumps({"ignorar": ["rascunhos"]}))
        self.assertIn("docs/specs/desenho.md", agwrite.mtimes())
        self.assertNotIn("rascunhos/x.md", agwrite.mtimes())
        with self.assertRaises(agwrite.Erro) as c:
            agwrite.salvar("rascunhos/x.md", "x", "0")
        self.assertEqual(c.exception.codigo, "caminho")

    def test_titulo_e_rotulos_do_config(self):
        escrever(self.ag, "config.json", json.dumps({"titulo": "Meu Projeto", "rotulos": {"01-A": "Pasta A"}}))
        grupos, _ = sync.montar_dados()
        self.assertEqual({g["folder"]: g["label"] for g in grupos}["01-A"], "Pasta A")
        self.assertEqual({g["folder"]: g["label"] for g in grupos}["02-B"], "02 · B")
        self.assertEqual(sync.dados_site()["titulo"], "Meu Projeto")

    def test_salvar_um_arquivo_valido(self):
        agwrite.salvar("01-A/nota.md", "# Novo\n", self.mtime("01-A/nota.md"))
        self.assertEqual(self.ler("01-A/nota.md"), "# Novo\n")

    def test_nova_em_subpasta_ignorada_recusa_sem_gravar(self):
        os.makedirs(os.path.join(self.tmp, "01-A", "vendor"))
        with self.assertRaises(agwrite.Erro) as c:
            agwrite.nova("01-A/vendor", "fantasma", [], "")
        self.assertEqual((c.exception.status, c.exception.codigo), (400, "pasta"))
        self.assertFalse(os.path.exists(os.path.join(self.tmp, "01-A", "vendor", "fantasma.md")))

    def test_servidor_aceita_fila_de_conexoes_maior_que_a_padrao(self):
        self.assertGreaterEqual(serve.Servidor.request_queue_size, 64)

    def test_titulo_ignora_comentario_de_shell_dentro_de_fence(self):
        t = sync.title_from_file("a.md", "a.md", "```bash\n# comentario\nls\n```\n\ntexto\n")
        self.assertEqual(t, "a")   # sem H1 de verdade: cai no nome do arquivo
        self.assertEqual(sync.title_from_file("a.md", "a.md", "```\n# x\n```\n# Titulo real\n"), "Titulo real")
        self.assertEqual(sync.title_from_file("a.md", "a.md", "# Antes\n```\n# x\n```\n"), "Antes")
        self.assertEqual(sync.title_from_file("a.md", "a.md", "```\n# nunca fecha\n"), "a")

    def test_salvar_por_symlink_grava_no_destino_e_mantem_o_link(self):
        alvo = escrever(self.tmp, "../alvo-externo-" + os.path.basename(self.tmp) + ".md", "# Alvo\n")
        link = os.path.join(self.tmp, "01-A", "ligada.md")
        try:
            os.symlink(alvo, link)
        except (OSError, NotImplementedError):
            self.skipTest("sem permissão para criar symlink aqui")
        try:
            m = str(os.stat(link).st_mtime_ns)
            agwrite.salvar("01-A/ligada.md", "# Alterado\n", m)
            self.assertTrue(os.path.islink(link), "o link virou arquivo comum")
            with open(alvo, encoding="utf-8") as f:
                self.assertEqual(f.read(), "# Alterado\n")
        finally:
            os.remove(alvo)

    def test_sync_nao_deixa_js_temporario_para_tras(self):
        agwrite.versao()
        pasta = os.path.dirname(sync.CONTENT_JS_PATH)
        self.assertEqual([f for f in os.listdir(pasta) if f.endswith(".tmp")], [])
        self.assertTrue(os.path.exists(sync.CONTENT_JS_PATH))

    def test_protegido_resiste_a_nomes_do_windows(self):
        P = sync.protegido
        self.assertTrue(P(["agLocalSite", "dados", "x.md"]))
        self.assertTrue(P(["AGLOCALSITE", "dados"]))
        for nome in ("agLocalSite.", "agLocalSite ", "agLocalSite. .", "agLocalSite::$DATA", "AgLocalSite...."):
            self.assertTrue(P([nome, "dados", "x.md"]), nome)
        self.assertFalse(P(["01-A", "nota.md"]))
        self.assertFalse(P(["agLocalSite2", "x.md"]))

    def test_protegido_nome_curto_8_3_so_no_windows(self):
        with mock.patch.object(sync.os, "name", "nt"):
            self.assertTrue(sync.protegido(["AGLOCA~1", "dados", "x.md"]))
            self.assertFalse(sync.protegido(["notes~1", "x.md"]))
            self.assertFalse(sync.protegido(["01-A~1", "nota.md"]))
        with mock.patch.object(sync.os, "name", "posix"):
            self.assertFalse(sync.protegido(["AGLOCA~1", "dados"]))

    def test_pasta_invalida_em_nova(self):
        for pasta in ["..", "../x", "node_modules", "agLocalSite", "agLocalSite/dados/historico", "02-B/nao-existe", "01-A\\..\\..", "nao-existe"]:
            with self.assertRaises(agwrite.Erro, msg=pasta) as c:
                agwrite.nova(pasta, "Titulo", [], "")
            self.assertIn(c.exception.codigo, ("pasta",), pasta)
        self.assertEqual(sorted(os.listdir(self.tmp)), sorted(["INICIO.md", "01-A", "02-B", "agLocalSite", "node_modules", ".oculta"]))


class Copias(Base):
    def test_copia_antes_de_gravar(self):
        agwrite.salvar("01-A/nota.md", "# Novo\n", self.mtime("01-A/nota.md"))
        pasta = self.caminho("agLocalSite/dados/historico/01-A/nota")
        copias = os.listdir(pasta)
        self.assertEqual(len(copias), 1)
        self.assertRegex(copias[0], r"^\d{4}-\d{2}-\d{2}_\d{6}_\d{6}\.md$")
        with open(os.path.join(pasta, copias[0]), encoding="utf-8") as f:
            self.assertEqual(f.read(), "# Nota A\n\ncorpo\n")  # a versão de antes

    def test_poda_em_20(self):
        for i in range(25):
            agwrite.salvar("01-A/nota.md", f"# v{i}\n", self.mtime("01-A/nota.md"))
        pasta = self.caminho("agLocalSite/dados/historico/01-A/nota")
        copias = sorted(os.listdir(pasta))
        self.assertEqual(len(copias), 20)
        with open(os.path.join(pasta, copias[-1]), encoding="utf-8") as f:
            self.assertEqual(f.read(), "# v23\n")   # a mais nova guarda o que havia antes da 25ª gravação
        with open(os.path.join(pasta, copias[0]), encoding="utf-8") as f:
            self.assertEqual(f.read(), "# v4\n")    # as 5 mais antigas (original, v0..v3) saíram

    def test_historico_fora_do_menu(self):
        agwrite.salvar("01-A/nota.md", "# Novo\n", self.mtime("01-A/nota.md"))
        ids = [i["file"] for g in agwrite.estado()["content"] for i in g["items"]]
        self.assertFalse([f for f in ids if "agLocalSite/dados/historico" in f])

    def test_falha_na_copia_nao_grava(self):
        with mock.patch("agwrite.shutil.copy2", side_effect=OSError("disco cheio")):
            with self.assertRaises(agwrite.Erro) as c:
                agwrite.salvar("01-A/nota.md", "# Novo\n", self.mtime("01-A/nota.md"))
        self.assertEqual(c.exception.codigo, "copia")
        self.assertEqual(self.ler("01-A/nota.md"), "# Nota A\n\ncorpo\n")


class Conflito(Base):
    def test_mtime_diferente_devolve_409_e_nao_grava(self):
        base = self.mtime("01-A/nota.md")
        escrever(self.tmp, "01-A/nota.md", "# Mudou por fora\n")
        os.utime(self.caminho("01-A/nota.md"), ns=(1_000_000_000, 1_000_000_000))
        with self.assertRaises(agwrite.Erro) as c:
            agwrite.salvar("01-A/nota.md", "# Minha\n", base)
        e = c.exception
        self.assertEqual((e.status, e.codigo), (409, "conflito"))
        self.assertEqual(e.extra["texto"], "# Mudou por fora\n")
        self.assertEqual(e.extra["mtime"], self.mtime("01-A/nota.md"))
        self.assertEqual(self.ler("01-A/nota.md"), "# Mudou por fora\n")
        self.assertFalse(os.path.exists(self.caminho("agLocalSite/dados/historico")))
        # sobrescrever de propósito: reenvia com o mtime devolvido
        agwrite.salvar("01-A/nota.md", "# Minha\n", e.extra["mtime"])
        self.assertEqual(self.ler("01-A/nota.md"), "# Minha\n")


class Gravacao(Base):
    def test_sem_sobra_de_temporario(self):
        agwrite.salvar("01-A/nota.md", "# Novo\n", self.mtime("01-A/nota.md"))
        self.assertEqual(sorted(os.listdir(self.caminho("01-A"))), ["nota.md"])

    def test_falha_na_troca_deixa_o_original_inteiro(self):
        with mock.patch("agwrite.os.replace", side_effect=OSError("sem permissão")):
            with self.assertRaises(agwrite.Erro) as c:
                agwrite.salvar("01-A/nota.md", "# Novo\n", self.mtime("01-A/nota.md"))
        self.assertEqual(c.exception.codigo, "gravar")
        self.assertEqual(self.ler("01-A/nota.md"), "# Nota A\n\ncorpo\n")
        self.assertEqual(sorted(os.listdir(self.caminho("01-A"))), ["nota.md"])  # o temporário foi apagado

    def test_arquivo_aberto_em_outro_programa(self):
        # no Windows, os.replace levanta PermissionError se outro programa segura o arquivo
        with mock.patch("agwrite.os.replace", side_effect=PermissionError("em uso")):
            with self.assertRaises(agwrite.Erro) as c:
                agwrite.salvar("01-A/nota.md", "# Novo\n", self.mtime("01-A/nota.md"))
        self.assertEqual(c.exception.codigo, "gravar")
        self.assertIn("aberto em outro programa", c.exception.msg)
        self.assertEqual(self.ler("01-A/nota.md"), "# Nota A\n\ncorpo\n")
        self.assertEqual(sorted(os.listdir(self.caminho("01-A"))), ["nota.md"])

    def test_crlf_preservado(self):
        escrever(self.tmp, "01-A/win.md", b"# Win\r\n\r\ncorpo\r\n", binario=True)
        agwrite.salvar("01-A/win.md", "# Win\n\nlinha nova\n", self.mtime("01-A/win.md"))
        with open(self.caminho("01-A/win.md"), "rb") as f:
            self.assertEqual(f.read(), b"# Win\r\n\r\nlinha nova\r\n")

    def test_lf_continua_lf(self):
        agwrite.salvar("01-A/nota.md", "# A\n\nb\n", self.mtime("01-A/nota.md"))
        with open(self.caminho("01-A/nota.md"), "rb") as f:
            self.assertNotIn(b"\r", f.read())

    def test_utf8_sem_bom(self):
        agwrite.salvar("01-A/nota.md", "# Ação\n", self.mtime("01-A/nota.md"))
        with open(self.caminho("01-A/nota.md"), "rb") as f:
            self.assertEqual(f.read(), "# Ação\n".encode("utf-8"))

    def test_salvar_roda_o_sync(self):
        agwrite.salvar("01-A/nota.md", "# Título mudado\n", self.mtime("01-A/nota.md"))
        with open(sync.CONTENT_JS_PATH, encoding="utf-8") as f:
            self.assertIn("Título mudado", f.read())


class NotaNova(Base):
    def test_casos_compartilhados_com_o_js(self):
        for entrada, esperado in CASOS["slug"]:
            self.assertEqual(agwrite.slug_titulo(entrada), esperado, entrada)
        for c in CASOS["nota"]:
            self.assertEqual(agwrite.montar_nota(c["titulo"], c["tags"], c["corpo"], c.get("status", "")), c["esperado"], c)

    def test_cria_com_frontmatter_slug_com_acento_e_id_do_sync(self):
        r = agwrite.nova("01-A", "Reunião de Sexta!", ["Dados Abertos", "3D"], "pauta")
        self.assertEqual(r["file"], "01-A/reuniao-de-sexta.md")
        self.assertEqual(self.ler(r["file"]), "---\ntags: [dados_abertos, 3d]\n---\n# Reunião de Sexta!\n\npauta\n")
        grupos, _ = sync.montar_dados()  # o sync, rodado do zero, chega ao mesmo id
        ids = {i["file"]: i["id"] for g in grupos for i in g["items"]}
        self.assertEqual(r["id"], ids[r["file"]])
        self.assertEqual(r["mtime"], self.mtime(r["file"]))

    def test_raiz_e_subpasta(self):
        self.assertEqual(agwrite.nova("", "Solta", [], "")["file"], "solta.md")
        self.assertEqual(agwrite.nova("02-B/sub", "Fundo", [], "")["file"], "02-B/sub/fundo.md")

    def test_nao_sobrescreve_titulo_repetido(self):
        agwrite.nova("01-A", "Igual", [], "primeira")
        with self.assertRaises(agwrite.Erro) as c:
            agwrite.nova("01-A", "igual!", [], "segunda")  # mesmo nome depois do slug
        self.assertEqual((c.exception.status, c.exception.codigo), (409, "existe"))
        self.assertIn("primeira", self.ler("01-A/igual.md"))

    def test_status_no_frontmatter_depois_das_tags(self):
        r = agwrite.nova("01-A", "Com status", ["Dados"], "corpo", " Em   revisão ")
        self.assertEqual(self.ler(r["file"]), "---\ntags: [dados]\nstatus: Em revisão\n---\n# Com status\n\ncorpo\n")
        r = agwrite.nova("01-A", "So status", [], "", "Fazendo")
        self.assertEqual(self.ler(r["file"]), "---\nstatus: Fazendo\n---\n# So status\n")
        r = agwrite.nova("01-A", "Sem nada", [], "", "  ")
        self.assertEqual(self.ler(r["file"]), "# Sem nada\n")
        # as tags continuam certas com a chave nova no frontmatter
        tags = {d["id"]: d["tags"]["curated"] for d in agwrite.estado()["graph"]["docs"]}
        self.assertEqual(tags["01-a-com-status"], ["dados"])

    def test_status_invalido(self):
        with self.assertRaises(agwrite.Erro) as c:
            agwrite.nova("01-A", "Longo", [], "", "x" * 41)
        self.assertEqual((c.exception.status, c.exception.codigo), (400, "status"))
        agwrite.nova("01-A", "No limite", [], "", "x" * 40)
        with self.assertRaises(agwrite.Erro) as c:
            agwrite.nova("01-A", "Tipo errado", [], "", 3)
        self.assertEqual(c.exception.codigo, "corpo")
        self.assertFalse(os.path.exists(self.caminho("01-A/longo.md")))

    def test_nomes_reservados_do_windows(self):
        for titulo in ["CON", "nul", "Aux!", "COM1", "lpt9", "Prn"]:
            with self.assertRaises(agwrite.Erro, msg=titulo) as c:
                agwrite.nova("01-A", titulo, [], "")
            self.assertEqual((c.exception.status, c.exception.codigo), (400, "titulo"), titulo)
        self.assertEqual(agwrite.nova("01-A", "Con 2", [], "")["file"], "01-A/con-2.md")  # só o nome inteiro é reservado
        self.assertEqual(agwrite.nova("01-A", "Console", [], "")["file"], "01-A/console.md")
        self.assertFalse(os.path.exists(self.caminho("01-A/con.md")))

    def test_titulo_sem_letra_ou_numero(self):
        with self.assertRaises(agwrite.Erro) as c:
            agwrite.nova("01-A", "!!!", [], "")
        self.assertEqual(c.exception.codigo, "titulo")

    def test_pedido_mal_formado(self):
        for args in [(None, "T", [], ""), ("", 3, [], ""), ("", "T", "a,b", ""), ("", "T", [1], ""), ("", "T", [], None)]:
            with self.assertRaises(agwrite.Erro, msg=repr(args)) as c:
                agwrite.nova(*args)
            self.assertEqual(c.exception.codigo, "corpo")


class Versao(Base):
    def test_carimbo_muda_com_edicao_por_fora_e_o_sync_acompanha(self):
        a = agwrite.versao()["carimbo"]
        self.assertEqual(agwrite.versao()["carimbo"], a)
        escrever(self.tmp, "01-A/nota.md", "# Editada no bloco de notas\n")
        b = agwrite.versao()["carimbo"]
        self.assertNotEqual(a, b)
        with open(sync.CONTENT_JS_PATH, encoding="utf-8") as f:
            self.assertIn("Editada no bloco de notas", f.read())

    def test_arquivo_novo_e_apagado_mudam_o_carimbo(self):
        a = agwrite.versao()["carimbo"]
        escrever(self.tmp, "01-A/outra.md", "# Outra\n")
        b = agwrite.versao()["carimbo"]
        os.remove(self.caminho("01-A/outra.md"))
        self.assertEqual(len({a, b, agwrite.versao()["carimbo"]}), 2)  # apagar volta ao carimbo de antes

    def test_estado_traz_dados_e_mtimes_em_texto(self):
        e = agwrite.estado()
        self.assertEqual(set(e), {"carimbo", "content", "graph", "mtimes", "carimbo_postits", "postits"})
        self.assertEqual(e["content"][0]["items"][0]["file"], "INICIO.md")
        self.assertTrue(all(isinstance(v, str) for v in e["mtimes"].values()))
        self.assertEqual(set(e["mtimes"]), {"INICIO.md", "01-A/nota.md", "02-B/sub/x.md"})
        json.dumps(e)  # serializa


class Http(Base):
    """A rota de verdade, num servidor temporário em porta livre."""

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

    def pedir(self, metodo, rota, corpo=None, host=None, origin="auto", tipo="application/json", tamanho=None):
        c = http.client.HTTPConnection("127.0.0.1", self.porta, timeout=5)
        c.putrequest(metodo, rota, skip_host=True)
        if host is not False:  # False: sem cabeçalho Host
            c.putheader("Host", f"localhost:{self.porta}" if host is None else host)
        if origin == "auto":
            origin = f"http://localhost:{self.porta}"
        if origin and metodo == "POST":
            c.putheader("Origin", origin)
        dados = json.dumps(corpo).encode("utf-8") if corpo is not None else b""
        if metodo == "POST":
            c.putheader("Content-Type", tipo)
            c.putheader("Content-Length", str(len(dados) if tamanho is None else tamanho))
        c.endheaders(dados if tamanho is None else b"")
        r = c.getresponse()
        texto = r.read().decode("utf-8")
        c.close()
        return r.status, (json.loads(texto) if texto.startswith("{") else texto)

    def test_ping_versao_estado(self):
        self.assertEqual(self.pedir("GET", "/api/ping"), (200, {"escrita": True}))
        s, v = self.pedir("GET", "/api/versao")
        self.assertEqual(s, 200)
        self.assertEqual(len(v["carimbo"]), 16)
        s, e = self.pedir("GET", "/api/estado")
        self.assertEqual((s, e["carimbo"]), (200, v["carimbo"]))

    def test_host_estranho_recusado(self):
        for host in ["evil.com", f"evil.com:{self.porta}", f"localhost:{self.porta + 1}", "localhost", "", False]:
            s, e = self.pedir("GET", "/api/ping", host=host)
            self.assertEqual((s, e["codigo"]), (403, "host"), host)
        s, e = self.pedir("POST", "/api/nova", {"titulo": "X"}, host="evil.com")
        self.assertEqual(s, 403)
        self.assertFalse(os.path.exists(self.caminho("x.md")))

    def test_127_0_0_1_vale(self):
        self.assertEqual(self.pedir("GET", "/api/ping", host=f"127.0.0.1:{self.porta}")[0], 200)

    def test_origin_estranho_ou_ausente_recusado(self):
        for origin in ["http://evil.com", "https://localhost:%d" % self.porta, "null", None]:
            s, e = self.pedir("POST", "/api/nova", {"pasta": "", "titulo": "Invasor", "tags": [], "corpo": ""}, origin=origin)
            self.assertEqual((s, e["codigo"]), (403, "origem"), origin)
        self.assertFalse(os.path.exists(self.caminho("invasor.md")))

    def test_post_sem_json_recusado(self):
        s, e = self.pedir("POST", "/api/nova", {"titulo": "X"}, tipo="text/plain")
        self.assertEqual((s, e["codigo"]), (415, "tipo"))

    def test_corpo_grande_recusado(self):
        s, e = self.pedir("POST", "/api/salvar", tamanho=2 * 1024 * 1024 + 1)
        self.assertEqual((s, e["codigo"]), (413, "grande"))

    def test_json_invalido(self):
        c = http.client.HTTPConnection("127.0.0.1", self.porta, timeout=5)
        c.request("POST", "/api/nova", body=b"{nao e json", headers={
            "Content-Type": "application/json", "Origin": f"http://localhost:{self.porta}"})
        r = c.getresponse()
        self.assertEqual((r.status, json.loads(r.read())["codigo"]), (400, "json"))

    def test_criar_e_salvar_pela_rota(self):
        s, r = self.pedir("POST", "/api/nova", {"pasta": "01-A", "titulo": "Pela rota", "tags": ["x"], "corpo": "oi"})
        self.assertEqual((s, r["file"]), (200, "01-A/pela-rota.md"))
        s, r2 = self.pedir("POST", "/api/salvar", {"file": r["file"], "texto": "# Trocado\n", "base_mtime": r["mtime"]})
        self.assertEqual(s, 200)
        s, r3 = self.pedir("POST", "/api/salvar", {"file": r["file"], "texto": "# Velho\n", "base_mtime": r["mtime"]})
        self.assertEqual((s, r3["codigo"]), (409, "conflito"))
        self.assertEqual(self.ler(r["file"]), "# Trocado\n")

    def test_status_pela_rota(self):
        s, r = self.pedir("POST", "/api/nova", {"pasta": "01-A", "titulo": "Rota status", "tags": [], "corpo": "", "status": "Ideia"})
        self.assertEqual(s, 200)
        self.assertEqual(self.ler(r["file"]), "---\nstatus: Ideia\n---\n# Rota status\n")
        s, e = self.pedir("POST", "/api/nova", {"pasta": "01-A", "titulo": "Longo", "status": "y" * 50})
        self.assertEqual((s, e["codigo"]), (400, "status"))

    def test_erro_nao_expoe_caminho_absoluto(self):
        s, e = self.pedir("POST", "/api/salvar", {"file": "../../etc/passwd", "texto": "x", "base_mtime": "0"})
        self.assertNotIn(self.tmp, json.dumps(e))
        with mock.patch("agwrite.salvar", side_effect=RuntimeError(self.tmp)), mock.patch("traceback.print_exc"):
            s, e = self.pedir("POST", "/api/salvar", {"file": "x", "texto": "x", "base_mtime": "0"})
        self.assertEqual((s, e["codigo"]), (500, "interno"))
        self.assertNotIn(self.tmp, json.dumps(e))

    def test_rota_desconhecida_e_metodo(self):
        self.assertEqual(self.pedir("GET", "/api/nada")[0], 404)
        self.assertEqual(self.pedir("GET", "/api/salvar")[0], 404)
        self.assertEqual(self.pedir("POST", "/api/ping", {})[0], 404)


if __name__ == "__main__":
    unittest.main()
