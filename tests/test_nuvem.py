"""Arquivos e pastas só na nuvem (OneDrive) não podem ser listados nem lidos pelo sync. Rodam numa cópia temporária."""
import os
import shutil
import sys
import tempfile
import unittest
from unittest import mock

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)
import sync


def escrever(base, rel, texto="# t\n"):
    caminho = os.path.join(base, *rel.split("/"))
    os.makedirs(os.path.dirname(caminho), exist_ok=True)
    with open(caminho, "w", encoding="utf-8") as f:
        f.write(texto)


class Nuvem(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        escrever(self.tmp, "INICIO.md")
        escrever(self.tmp, "SO-NUVEM.md")
        escrever(self.tmp, "01-local/a.md")
        escrever(self.tmp, "01-local/so-nuvem.md")
        escrever(self.tmp, "02-pesada/b.md")
        escrever(self.tmp, "03-outra/sub-nuvem/c.md")
        escrever(self.tmp, "03-outra/d.md")
        escrever(self.tmp, "01-local/foto.png")
        escrever(self.tmp, "01-local/pacote.zip")
        self.ag = os.path.join(self.tmp, "agLocalSite")
        os.makedirs(self.ag)
        self._velho = (sync.ROOT, sync.AG_DIR, sync.CONFIG_PATH)
        sync.ROOT, sync.AG_DIR, sync.CONFIG_PATH = self.tmp, self.ag, os.path.join(self.ag, "config.json")
        sync.NUVEM_PULADOS.clear()

    def tearDown(self):
        sync.ROOT, sync.AG_DIR, sync.CONFIG_PATH = self._velho
        sync.NUVEM_PULADOS.clear()
        shutil.rmtree(self.tmp)

    def rels(self):
        return sorted(os.path.relpath(p, self.tmp).replace("\\", "/") for p in sync.arquivos_md())

    def test_sem_nuvem_tudo_entra(self):
        self.assertEqual(self.rels(), ["01-local/a.md", "01-local/so-nuvem.md", "02-pesada/b.md",
                                       "03-outra/d.md", "03-outra/sub-nuvem/c.md", "INICIO.md", "SO-NUVEM.md"])

    def test_pula_o_que_esta_so_na_nuvem_e_nunca_le(self):
        marca = lambda e: e.name in {"SO-NUVEM.md", "so-nuvem.md", "02-pesada", "sub-nuvem", "foto.png", "pacote.zip"}
        lidos = []
        original = sync._ler
        with mock.patch.object(sync, "so_na_nuvem", marca), \
                mock.patch.object(sync, "_ler", lambda c: (lidos.append(c), original(c))[1]), \
                mock.patch("builtins.print") as imprime:
            grupos, _ = sync.montar_dados()
        self.assertEqual(sorted(i["file"] for g in grupos for i in g["items"]),
                         ["01-local/a.md", "03-outra/d.md", "INICIO.md"])
        nomes_lidos = {os.path.basename(c) for c in lidos}
        self.assertFalse(nomes_lidos & {"SO-NUVEM.md", "so-nuvem.md", "b.md", "c.md"})
        self.assertEqual(len(sync.NUVEM_PULADOS), 4)   # foto.png e pacote.zip só-nuvem não contam
        aviso = " ".join(str(c) for c in imprime.call_args_list)
        self.assertIn("2 .md e 2 pasta(s)", aviso)
        self.assertIn("só na nuvem", " ".join(str(c) for c in imprime.call_args_list))

    def test_atributos_do_windows(self):
        class Fake:
            def __init__(self, attrs):
                self.attrs = attrs

            def stat(self, follow_symlinks=True):
                return mock.Mock(st_file_attributes=self.attrs)

        with mock.patch.object(sync, "_WINDOWS", True):
            self.assertTrue(sync.so_na_nuvem(Fake(0x400000)))   # RECALL_ON_DATA_ACCESS (online-only)
            self.assertTrue(sync.so_na_nuvem(Fake(0x40000)))    # RECALL_ON_OPEN
            self.assertTrue(sync.so_na_nuvem(Fake(0x1000)))     # OFFLINE
            self.assertFalse(sync.so_na_nuvem(Fake(0x20)))      # arquivo comum (ARCHIVE)
            self.assertFalse(sync.so_na_nuvem(Fake(0x80000)))   # PINNED: sempre neste dispositivo, já baixado
        with mock.patch.object(sync, "_WINDOWS", False):
            self.assertFalse(sync.so_na_nuvem(Fake(0x400000)))


if __name__ == "__main__":
    unittest.main()
