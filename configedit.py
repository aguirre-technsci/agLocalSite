"""Validação e mesclagem do config.json para o painel de configurações. Puro: não lê nem grava arquivo, não usa rede.

validar(valores) confere o que o painel quer mudar e devolve a versão normalizada; mesclar(atual, patch) aplica isso ao conteúdo atual
do arquivo. As regras estão nas seções 5.1 e 5.2 de docs/specs/2026-11-21-painel-de-configuracoes-design.md.
"""
import copy

import sync

CHAVES_EDITAVEIS = ("titulo", "subtitulo", "etiqueta", "titulo_aba", "textos", "tema", "ignorar", "rotulos", "home_prioridade")
SOMENTE_LEITURA = ("raiz", "prefixo_url", "porta")   # definem o que o servidor lê e serve (ou exigem reiniciar): só pelo arquivo
TEXTOS_SIMPLES = ("titulo", "subtitulo", "etiqueta", "titulo_aba")


class ErroValidacao(Exception):
    """Valor recusado. campo diz qual (ex.: "textos.grafo"); msg é curta, em português, para mostrar ao lado do campo."""

    def __init__(self, campo, msg):
        super().__init__(msg)
        self.campo, self.msg = campo, msg


def _utf8(campo, v):
    """JSON aceita "\\ud800" (surrogate solto), mas isso não se grava em UTF-8: recusar aqui evita o erro depois da cópia de segurança."""
    try:
        v.encode("utf-8")
    except UnicodeEncodeError:
        raise ErroValidacao(campo, "tem um caractere que não pode ser gravado.")


def _texto(campo, v, maximo, vazio_remove=True):
    """Texto de uma linha: strip; maior que o limite é erro; vazio vira None (remove a chave) quando vazio_remove."""
    if v is None:
        return None
    if not isinstance(v, str):
        raise ErroValidacao(campo, "precisa ser texto.")
    v = v.strip()
    _utf8(campo, v)
    if len(v) > maximo:
        raise ErroValidacao(campo, f"use no máximo {maximo} caracteres.")
    return (None if vazio_remove else v) if v == "" else v


def _nome(campo, v):
    """Nome simples de pasta ou arquivo: 1 a 100 caracteres, sem / nem \\."""
    if not isinstance(v, str):
        raise ErroValidacao(campo, "precisa ser texto.")
    v = v.strip()
    _utf8(campo, v)
    if not v or len(v) > sync.LIMITES["nome"]:
        raise ErroValidacao(campo, f"cada nome tem de 1 a {sync.LIMITES['nome']} caracteres.")
    if "/" in v or "\\" in v:
        raise ErroValidacao(campo, 'nomes não podem ter "/" nem "\\" (é o nome da pasta, não o caminho).')
    return v


def _lista_de_nomes(campo, v, maximo, sem_md=False):
    if v is None:
        return None
    if not isinstance(v, list):
        raise ErroValidacao(campo, "precisa ser uma lista.")
    if len(v) > maximo:
        raise ErroValidacao(campo, f"use no máximo {maximo} itens.")
    nomes = [_nome(campo, x) for x in v]
    if len(set(nomes)) != len(nomes):
        raise ErroValidacao(campo, "há itens repetidos.")
    if sem_md and any(n.lower().endswith(".md") for n in nomes):
        raise ErroValidacao(campo, 'escreva o nome sem ".md".')
    return nomes


def _textos(campo, v):
    if v is None:
        return None
    if not isinstance(v, dict):
        raise ErroValidacao(campo, "precisa ser um objeto.")
    out = {}
    for sub, valor in v.items():
        c = f"{campo}.{sub}"
        if sub not in sync.TEXTOS_CHAVES:
            raise ErroValidacao(c, "texto desconhecido (use: " + ", ".join(sync.TEXTOS_CHAVES) + ").")
        rodape = sub == "rodape"
        # no rodapé, "" quer dizer ocultar; nos outros, vazio é voltar ao padrão
        out[sub] = _texto(c, valor, sync.LIMITES["rodape"] if rodape else sync.LIMITES["texto"], vazio_remove=not rodape)
    return out


def _tema(campo, v):
    if v is None:
        return None
    if not isinstance(v, dict):
        raise ErroValidacao(campo, "precisa ser um objeto.")
    out = {}
    for sub, valor in v.items():
        c = f"{campo}.{sub}"
        opcoes = {"paleta": [n for n, _ in sync.PALETAS], "modo": list(sync.MODOS)}.get(sub)
        if opcoes is None:
            raise ErroValidacao(c, "opção desconhecida (use: paleta, modo).")
        if valor is not None and (not isinstance(valor, str) or valor not in opcoes):
            raise ErroValidacao(c, "use um destes: " + ", ".join(opcoes) + ".")
        out[sub] = valor
    return out


def _rotulos(campo, v):
    if v is None:
        return None
    if not isinstance(v, dict):
        raise ErroValidacao(campo, "precisa ser um objeto.")
    if len(v) > sync.LIMITES["rotulos"]:
        raise ErroValidacao(campo, f"use no máximo {sync.LIMITES['rotulos']} rótulos.")
    out = {}
    for pasta, rotulo in v.items():
        nome = _nome(campo, pasta)
        texto = _texto(campo, rotulo, sync.LIMITES["texto"])
        if texto is not None:   # rótulo vazio = sem rótulo: a entrada some
            out[nome] = texto
    return out


def validar(valores):
    """Confere o que o painel quer mudar. Devolve o patch normalizado (mesma forma, textos com strip, vazio como None);
    levanta ErroValidacao(campo, msg) no primeiro problema."""
    if not isinstance(valores, dict):
        raise ErroValidacao("valores", "precisa ser um objeto.")
    out = {}
    for chave, v in valores.items():
        if chave in SOMENTE_LEITURA:
            raise ErroValidacao(chave, f'"{chave}" só se muda editando o config.json (e vale no próximo start).')
        if chave in TEXTOS_SIMPLES:
            out[chave] = _texto(chave, v, sync.LIMITES["texto"])
        elif chave == "textos":
            out[chave] = _textos(chave, v)
        elif chave == "tema":
            out[chave] = _tema(chave, v)
        elif chave == "ignorar":
            out[chave] = _lista_de_nomes(chave, v, sync.LIMITES["itens_ignorar"])
        elif chave == "rotulos":
            out[chave] = _rotulos(chave, v)
        elif chave == "home_prioridade":
            out[chave] = _lista_de_nomes(chave, v, sync.LIMITES["home"], sem_md=True)
        else:
            raise ErroValidacao(chave, "opção desconhecida.")
    return out


def mesclar(atual, patch):
    """Aplica o patch (já validado) ao conteúdo atual do config.json e devolve uma cópia nova; atual não é alterado.
    Topo com None remove a chave; textos e tema mesclam por subchave (None remove só ela; objeto vazio some);
    listas e mapas substituem por inteiro. Chaves que o painel não conhece e as somente leitura ficam como estão, na mesma ordem."""
    novo = copy.deepcopy(atual)
    for chave, v in patch.items():
        if v is None:
            novo.pop(chave, None)
        elif chave in ("textos", "tema"):
            base = novo.get(chave) if isinstance(novo.get(chave), dict) else {}
            for sub, valor in v.items():
                if valor is None:
                    base.pop(sub, None)
                else:
                    base[sub] = valor
            if base:
                novo[chave] = base
            else:
                novo.pop(chave, None)
        else:
            novo[chave] = v
    return novo
