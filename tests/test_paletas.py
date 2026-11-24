"""Paletas de cor: cada nome de sync.PALETAS tem seus dois blocos em paletas.css, só com os tokens certos, e nenhuma fica pior que a Padrão em contraste."""
import os
import re
import sys
import unittest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)
import sync

TOKENS = {"bg", "bg-grid", "panel", "ink", "muted", "line", "line-soft", "accent", "accent-soft", "accent2", "cite", "glass", "on-line",
          "g-tag", "g-tag-dim", "g-doc-dim", "g-link", "g-link-dim"}
PROIBIDOS = ("pi-", "code-", "hit-", "danger")
PARES = [("ink", "bg"), ("ink", "panel"), ("muted", "bg"), ("muted", "panel"), ("accent", "panel"), ("accent2", "panel"),
         ("cite", "panel"), ("on-line", "line")]
NOVAS = [n for n, _ in sync.PALETAS if n != "padrao"]


def ler(rel):
    with open(os.path.join(RAIZ, "site", "css", rel), encoding="utf-8") as f:
        return re.sub(r"/\*.*?\*/", "", f.read(), flags=re.S)


def declaracoes(corpo):
    return {m.group(1): m.group(2).strip() for m in re.finditer(r"--([a-z0-9-]+)\s*:\s*([^;]+);", corpo)}


def blocos(css):
    """{seletor normalizado: {token: valor}} de cada regra com seletor :root[...]."""
    return {re.sub(r"\s+", "", m.group(1)): declaracoes(m.group(2)) for m in re.finditer(r"(:root[^{]*)\{([^}]*)\}", css)}


def luminancia(hexa):
    r, g, b = (int(hexa[i:i + 2], 16) / 255 for i in (1, 3, 5))
    f = lambda c: c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b)


def razao(a, b):
    x, y = sorted((luminancia(a), luminancia(b)), reverse=True)
    return (x + 0.05) / (y + 0.05)


STYLE = blocos(ler("style.css"))
PALETAS = blocos(ler("paletas.css")) if os.path.exists(os.path.join(RAIZ, "site", "css", "paletas.css")) else {}
PADRAO_CLARO = STYLE[":root"]
PADRAO_ESCURO = {**PADRAO_CLARO, **STYLE[':root[data-theme="dark"]']}


def seletor(nome, escuro):
    return f':root[data-palette="{nome}"]' + ('[data-theme="dark"]' if escuro else "")


class Paletas(unittest.TestCase):
    def test_cada_paleta_tem_os_dois_blocos_e_nenhum_sobra(self):
        esperados = {seletor(n, e) for n in NOVAS for e in (False, True)}
        self.assertEqual(set(PALETAS), esperados)

    def test_blocos_definem_exatamente_os_tokens_da_paleta(self):
        for sel, decl in PALETAS.items():
            self.assertEqual(set(decl), TOKENS, sel)
            for token in decl:
                self.assertFalse(token.startswith(PROIBIDOS), f"{sel} mexe em --{token}, que tem significado fixo")

    def test_so_hex_nos_pares_de_contraste_e_rgba_no_glass(self):
        for sel, decl in PALETAS.items():
            for token, valor in decl.items():
                if token == "glass":
                    self.assertRegex(valor, r"^rgba\(\d+, \d+, \d+, 0\.82\)$", sel)
                else:
                    self.assertRegex(valor, r"^#[0-9a-f]{6}$", f"{sel} --{token}")

    def test_paletas_sao_diferentes_entre_si_e_da_padrao(self):
        vistos = {}
        for n in NOVAS:
            claro, escuro = PALETAS[seletor(n, False)], PALETAS[seletor(n, True)]
            self.assertNotEqual(claro["bg"], escuro["bg"], n)
            self.assertNotEqual(claro["accent"], PADRAO_CLARO["accent"], n)
            for chave in (claro["accent"], claro["bg"]):
                self.assertNotIn(chave, vistos, f"{n} repete uma cor de {vistos.get(chave)}")
                vistos[chave] = n

    def test_contraste_nao_piora_a_padrao(self):
        falhas = []
        for modo, padrao, escuro in (("claro", PADRAO_CLARO, False), ("escuro", PADRAO_ESCURO, True)):
            for fg, bg in PARES:
                piso = min(4.5, razao(padrao[fg], padrao[bg]))
                for n in NOVAS:
                    t = PALETAS[seletor(n, escuro)]
                    r = razao(t[fg], t[bg])
                    if r < piso - 1e-9:
                        falhas.append(f"{n}/{modo} {fg} sobre {bg}: {r:.2f} < {piso:.2f}")
        self.assertEqual(falhas, [])

    def test_padrao_fixa_os_numeros_de_hoje(self):
        # o piso das paletas novas deriva da Padrão; se ela mudar sem querer, este teste avisa
        self.assertTrue(3.0 <= razao(PADRAO_CLARO["accent"], PADRAO_CLARO["panel"]) <= 3.3)
        self.assertGreater(razao(PADRAO_CLARO["ink"], PADRAO_CLARO["bg"]), 14)
        self.assertGreater(razao(PADRAO_ESCURO["ink"], PADRAO_ESCURO["bg"]), 15)


if __name__ == "__main__":
    unittest.main()
