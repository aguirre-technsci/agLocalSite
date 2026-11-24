"""Gravação com nova tentativa (OneDrive/antivírus), porta exclusiva no Windows e .bat sem segunda cópia do servidor."""
import os
import sys
import unittest
from unittest import mock

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)
import agwrite
import serve


class Trocar(unittest.TestCase):
    def test_passa_depois_de_travas_passageiras(self):
        with mock.patch("agwrite.os.replace", side_effect=[PermissionError("em uso"), PermissionError("em uso"), None]) as r, \
                mock.patch("agwrite.time.sleep") as dorme:
            agwrite._trocar("a.tmp", "a.md")
        self.assertEqual(r.call_count, 3)
        self.assertEqual(dorme.call_count, 2)

    def test_desiste_depois_de_todas_as_tentativas(self):
        with mock.patch("agwrite.os.replace", side_effect=PermissionError("em uso")) as r, mock.patch("agwrite.time.sleep"):
            with self.assertRaises(PermissionError):
                agwrite._trocar("a.tmp", "a.md", tentativas=4)
        self.assertEqual(r.call_count, 4)

    def test_outro_erro_nao_repete(self):
        with mock.patch("agwrite.os.replace", side_effect=OSError("disco cheio")) as r, mock.patch("agwrite.time.sleep"):
            with self.assertRaises(OSError):
                agwrite._trocar("a.tmp", "a.md")
        self.assertEqual(r.call_count, 1)


class Porta(unittest.TestCase):
    def test_reuso_de_porta_so_fora_do_windows(self):
        self.assertEqual(serve.Servidor.allow_reuse_address, os.name != "nt")


class Bats(unittest.TestCase):
    def ler(self, nome):
        with open(os.path.join(RAIZ, nome), "rb") as f:
            return f.read()

    def test_crlf_e_sem_segunda_execucao(self):
        for nome in ("start.bat", "sync.bat"):
            b = self.ler(nome)
            self.assertNotIn(b"\n", b.replace(b"\r\n", b""), nome + ": precisa de CRLF por causa do goto")
            self.assertNotIn(b"||", b, nome + ": 'a && b || c' roda c também quando b falha")
            self.assertEqual(b.count(b"serve.py %*") + b.count(b"sync.py"), 2, nome)


if __name__ == "__main__":
    unittest.main()
