"""
agwrite.py — regras de gravação do workspace. Sem HTTP: o serve.py só roteia as chamadas para cá.

Valida o caminho, guarda uma cópia em dados/historico/, grava de forma atômica, cria nota nova,
calcula o carimbo de versão e roda o sync (montar_dados + escrever_arquivos do sync.py).

Só biblioteca padrão do Python 3.
"""

import hashlib
import json
import math
import os
import re
import shutil
import stat
import tempfile
import threading
import time
from datetime import datetime

import configedit
import graphdata
import sync

MAX_COPIAS = 20   # cópias em dados/historico/ por arquivo; as mais antigas saem

# ---------- configuração (painel ⚙) ----------
# O painel edita só as chaves seguras do config.json (configedit decide quais). Tudo sob o LOCK, na ordem da seção 6.2 da spec.
# Cópias do arquivo ficam em agLocalSite/dados/config-historico/<data_hora>.json (pasta própria: não colide com notas).

def _versao_config():
    try:
        return _mtime(sync.CONFIG_PATH)
    except OSError:
        return "ausente"


def _pasta_config_historico():
    return os.path.join(sync.DADOS_DIR, "config-historico")


def _copias_config():
    pasta = _pasta_config_historico()
    return sorted(f for f in os.listdir(pasta) if f.endswith(".json")) if os.path.isdir(pasta) else []


def _valores_editaveis(atual):
    return {k: atual[k] for k in configedit.CHAVES_EDITAVEIS if k in atual}


def _estado_config():
    """Corpo de GET /api/config; chamar com o LOCK."""
    try:
        atual, problema = sync.ler_config_estrito(), None
    except sync.ConfigIlegivel as e:
        atual, problema = {}, {"mensagem": e.msg, "linha": e.linha, "coluna": e.coluna}
    c = sync.config()
    rotulos = c.get("rotulos") if isinstance(c.get("rotulos"), dict) else {}
    base = sync.dados_site({})
    estado = {
        "legivel": problema is None,
        "valores": _valores_editaveis(atual),
        "padroes": {
            "titulo": base["titulo"], "subtitulo": base["subtitulo"], "etiqueta": base["etiqueta"], "titulo_aba": base["titulo_aba"],
            "textos": dict(sync.TEXTOS_PADRAO), "tema": {"paleta": "padrao", "modo": "claro"},
            "ignorar": [], "ignoradas_sempre": sorted(sync.IGNORE_DIRS), "rotulos": {}, "home_prioridade": list(sync.HOME_PRIORITY),
        },
        "somente_leitura": {"raiz": sync.ROOT, "prefixo_url": sync.prefixo_url(), "porta": c.get("porta", 8000), "arquivo": sync.CONFIG_PATH},
        "pastas": [{"nome": n, "rotulo": rotulos[n] if isinstance(rotulos.get(n), str) else ""} for n in sync.pastas_topo()],
        "paletas": [{"nome": n, "rotulo": r} for n, r in sync.PALETAS],
        "limites": dict(sync.LIMITES),
        "versao": _versao_config(),
        "historico": len(_copias_config()),   # quantas versões anteriores o Desfazer tem
        "site": sync.dados_site(),
    }
    if problema:
        estado["problema"] = problema
    return estado


def config_estado():
    with LOCK:
        return _estado_config()


def config_salvar(valores, base_versao):
    """Aplica as mudanças do painel ao config.json e devolve o estado novo. base_versao é a versão que o painel viu ao abrir."""
    if not isinstance(base_versao, str):
        raise Erro(400, "corpo", "Pedido incompleto.")
    with LOCK:
        try:
            atual = sync.ler_config_estrito()
        except sync.ConfigIlegivel as e:   # nunca sobrescrever um arquivo que não conseguimos ler
            raise Erro(409, "config_ilegivel", "O config.json está com JSON inválido: corrija o arquivo e abra o painel de novo.",
                       linha=e.linha, coluna=e.coluna, detalhe=e.msg)
        versao = _versao_config()
        if versao != base_versao:
            raise Erro(409, "conflito", "O config.json mudou por fora desde que o painel foi aberto.",
                       versao=versao, valores=_valores_editaveis(atual))
        try:
            patch = configedit.validar(valores)
        except configedit.ErroValidacao as e:
            raise Erro(400, "somente_leitura" if e.campo in configedit.SOMENTE_LEITURA else "validacao", e.msg, campo=e.campo)
        novo = configedit.mesclar(atual, patch)
        if novo == atual:
            return _estado_config()
        existe = os.path.exists(sync.CONFIG_PATH)
        if existe:
            _guardar_copia(_pasta_config_historico(), sync.CONFIG_PATH, ".json")
        _gravar(sync.CONFIG_PATH, json.dumps(novo, indent=2, ensure_ascii=False) + "\n", crlf=existe and b"\r\n" in _ler(sync.CONFIG_PATH))
        _sincronizar()
        return _estado_config()


def config_desfazer():
    """Volta o config.json à cópia mais recente do histórico; o estado de agora vira cópia (então desfazer duas vezes volta ao início).
    Funciona também com o arquivo quebrado: é a forma de recuperar o que foi estragado à mão."""
    with LOCK:
        copias = _copias_config()
        if not copias:
            raise Erro(409, "sem_historico", "Não há versão anterior do config.json para voltar.")
        origem = os.path.join(_pasta_config_historico(), copias[-1])   # escolhida antes de a cópia de agora entrar no histórico
        try:
            with open(origem, "rb") as f:
                dados = f.read()
        except OSError:
            raise Erro(500, "copia", "Não foi possível ler a cópia de segurança.")
        if os.path.exists(sync.CONFIG_PATH):
            _guardar_copia(_pasta_config_historico(), sync.CONFIG_PATH, ".json")
        _gravar(sync.CONFIG_PATH, dados.decode("utf-8", "replace").replace("\r\n", "\n"), crlf=b"\r\n" in dados)
        _sincronizar()
        return _estado_config()


# ---------- post-its ----------
POSTIT_CORES = {"amarelo", "verde", "azul", "rosa", "laranja"}
POSTIT_ID_RE = re.compile(r"^[a-z0-9]{4,32}$")
MAX_POSTITS = 200      # por documento
MAX_TEXTO_POSTIT = 1000  # caracteres
POSTIT_W_MIN, POSTIT_W_MAX = 160, 480    # largura em px
POSTIT_H_MIN, POSTIT_H_MAX = 120, 640    # altura em px

# Um único Lock protege gravação e sync: o servidor atende em threads.
LOCK = threading.Lock()
_ultimo = None    # carimbo do último sync
_dados = None     # (grupos, grafo) do último sync


class Erro(Exception):
    """Erro para o usuário: status HTTP, código curto e mensagem sem caminho absoluto."""

    def __init__(self, status, codigo, msg, **extra):
        super().__init__(msg)
        self.status, self.codigo, self.msg, self.extra = status, codigo, msg, extra

    def corpo(self):
        return {"erro": self.msg, "codigo": self.codigo, **self.extra}


def _rel(caminho):
    return os.path.relpath(caminho, sync.ROOT).replace("\\", "/")


def _mtime(caminho):
    # texto, não número: mtime_ns passa de 2^53 e o JavaScript perderia dígitos
    return str(os.stat(caminho).st_mtime_ns)


def _ler(caminho):
    with open(caminho, "rb") as f:
        return f.read()


# ---------- versão e sync ----------

def carimbo():
    """Hash de (caminho, mtime_ns, tamanho) de todo .md que o sync varre, mais o config.json."""
    h = hashlib.sha1()
    for p in sync.arquivos_md():
        try:
            st = os.stat(p)
        except OSError:
            continue  # sumiu entre a listagem e o stat
        h.update(f"{_rel(p)}|{st.st_mtime_ns}|{st.st_size}\n".encode())
    try:  # editar só o config.json (título, rótulos, ignorar...) também refaz o content.js
        st = os.stat(sync.CONFIG_PATH)
        h.update(f"config|{st.st_mtime_ns}|{st.st_size}\n".encode())
    except OSError:
        pass
    return h.hexdigest()[:16]


def mtimes():
    out = {}
    for p in sync.arquivos_md():
        try:
            out[_rel(p)] = _mtime(p)
        except OSError:
            pass
    return out


def _sincronizar():
    """Chamar com o LOCK. Roda o sync se algum .md mudou desde o último. Devolve o carimbo."""
    global _ultimo, _dados
    c = carimbo()  # antes de ler: se algo mudar durante a leitura, o próximo carimbo difere e o sync roda de novo
    if c != _ultimo:
        _dados = sync.montar_dados()
        sync.escrever_arquivos(*_dados)
        _ultimo = c
    return c


def versao():
    with LOCK:
        return {"carimbo": _sincronizar(), "carimbo_postits": carimbo_postits()}


def estado():
    with LOCK:
        c = _sincronizar()
        return {
            "carimbo": c, "content": _dados[0], "graph": _dados[1], "mtimes": mtimes(),
            "carimbo_postits": carimbo_postits(), "postits": postits_todos(),
        }


# ---------- salvar ----------

def _arquivo(file):
    """Caminho absoluto de um .md que o sync varre (lista de permissão); senão, erro 400."""
    if isinstance(file, str) and not any(p.startswith(".") for p in file.split("/")):
        for p in sync.arquivos_md():
            if _rel(p) == file:
                return p
    raise Erro(400, "caminho", "Arquivo inválido.")


def _guardar_copia(pasta, caminho, ext):
    """Copia o arquivo para <pasta>/<data_hora><ext> e poda as mais antigas, deixando MAX_COPIAS."""
    try:
        os.makedirs(pasta, exist_ok=True)
        shutil.copy2(caminho, os.path.join(pasta, datetime.now().strftime("%Y-%m-%d_%H%M%S_%f") + ext))
        for velha in sorted(f for f in os.listdir(pasta) if f.endswith(ext))[:-MAX_COPIAS]:
            os.remove(os.path.join(pasta, velha))
    except OSError:
        raise Erro(500, "copia", "Não foi possível guardar a cópia de segurança. Nada foi gravado.")


def _copia(rel, caminho):
    """Guarda o arquivo atual em agLocalSite/dados/historico/<caminho sem .md>/<data_hora>.md e poda as antigas."""
    _guardar_copia(os.path.join(sync.DADOS_DIR, "historico", rel[:-3]), caminho, ".md")


def _trocar(tmp, caminho, tentativas=5, espera=0.2):
    """os.replace com novas tentativas: OneDrive, antivírus e indexador seguram o arquivo por instantes no Windows."""
    for n in range(tentativas):
        try:
            return os.replace(tmp, caminho)
        except PermissionError:
            if n == tentativas - 1:
                raise
            time.sleep(espera)


def _gravar(caminho, texto, crlf=False):
    """Grava em arquivo temporário na mesma pasta e troca com os.replace: nunca sobra arquivo pela metade."""
    dados = (texto.replace("\r\n", "\n").replace("\n", "\r\n") if crlf else texto).encode("utf-8")
    if os.path.islink(caminho):
        caminho = os.path.realpath(caminho)   # nota ligada por symlink: grava no arquivo de verdade; o os.replace trocaria o link por uma cópia
    tmp = None
    try:
        fd, tmp = tempfile.mkstemp(dir=os.path.dirname(caminho), prefix=".ag-", suffix=".tmp")
        with os.fdopen(fd, "wb") as f:
            f.write(dados)
        os.chmod(tmp, stat.S_IMODE(os.stat(caminho).st_mode) if os.path.exists(caminho) else 0o644)
        _trocar(tmp, caminho)
    except OSError as e:
        if tmp and os.path.exists(tmp):
            os.unlink(tmp)
        if isinstance(e, PermissionError):  # no Windows, arquivo aberto em outro programa recusa a troca
            raise Erro(500, "gravar", "Não foi possível gravar: o arquivo está aberto em outro programa ou protegido contra escrita.")
        raise Erro(500, "gravar", "Não foi possível gravar o arquivo.")


def salvar(file, texto, base_mtime):
    if not isinstance(texto, str) or base_mtime is None:
        raise Erro(400, "corpo", "Pedido incompleto.")
    with LOCK:
        caminho = _arquivo(file)
        atual = _mtime(caminho)
        if atual != str(base_mtime):
            original = _ler(caminho).decode("utf-8", "replace").replace("\r\n", "\n")
            raise Erro(409, "conflito", "O arquivo mudou por fora.", texto=original, mtime=atual)
        original = _ler(caminho)
        _copia(file, caminho)
        _gravar(caminho, texto, crlf=b"\r\n" in original)
        _sincronizar()
        return {"ok": True, "mtime": _mtime(caminho)}


# ---------- post-its ----------
# Anotação solta na página de um documento; vive em agLocalSite/dados/postits/<doc sem .md>.json, fora do .md e do historico/.

def _raiz_postits():
    return os.path.join(sync.DADOS_DIR, "postits")


def _arquivo_postits(rel_md):
    """dados/postits/<rel_md sem .md>.json, a partir do caminho já validado por _arquivo()."""
    return os.path.join(_raiz_postits(), *rel_md[:-3].split("/")) + ".json"


def _ler_postits(caminho):
    """Lista de post-its do arquivo, ou [] se ele não existe ou está corrompido."""
    try:
        with open(caminho, "r", encoding="utf-8") as f:
            lista = json.load(f).get("postits")
        if not isinstance(lista, list):
            return []
        return [p for p in lista if isinstance(p, dict) and isinstance(p.get("id"), str)]   # item corrompido à mão é descartado, não derruba a rota
    except (OSError, ValueError, AttributeError):
        return []


def _gravar_postits(caminho, lista):
    os.makedirs(os.path.dirname(caminho), exist_ok=True)
    _gravar(caminho, json.dumps({"postits": lista}, ensure_ascii=False, indent=1) + "\n")


def _limpar_pastas_postits(caminho):
    """Sobe apagando pastas vazias dentro de dados/postits/, sem tocar a própria pasta postits/."""
    raiz = _raiz_postits()
    pasta = os.path.dirname(caminho)
    while pasta != raiz and (pasta + os.sep).startswith(raiz + os.sep):
        try:
            os.rmdir(pasta)
        except OSError:
            break  # não está vazia (ou já sumiu): para por aqui
        pasta = os.path.dirname(pasta)


def _numero(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def _validar_postit(p):
    """Post-it normalizado (x/w com 2 casas, y/h inteiros, só os 6 campos), ou 400 'postit' com o campo na mensagem."""
    if not isinstance(p, dict):
        raise Erro(400, "postit", "Post-it inválido.")
    id_ = p.get("id")
    if not isinstance(id_, str) or not POSTIT_ID_RE.match(id_):
        raise Erro(400, "postit", "Campo «id» inválido.")
    x, y = p.get("x"), p.get("y")
    if not _numero(x) or not (0 <= x <= 100):
        raise Erro(400, "postit", "Campo «x» inválido.")
    if not _numero(y) or not (0 <= y <= 100000):
        raise Erro(400, "postit", "Campo «y» inválido.")
    w, h = p.get("w", 200), p.get("h", 160)
    if not _numero(w) or not (POSTIT_W_MIN <= w <= POSTIT_W_MAX):
        raise Erro(400, "postit", "Campo «w» inválido.")
    if not _numero(h) or not (POSTIT_H_MIN <= h <= POSTIT_H_MAX):
        raise Erro(400, "postit", "Campo «h» inválido.")
    if p.get("cor") not in POSTIT_CORES:
        raise Erro(400, "postit", "Campo «cor» inválido.")
    texto = p.get("texto")
    if not isinstance(texto, str) or len(texto) > MAX_TEXTO_POSTIT:
        raise Erro(400, "postit", "Campo «texto» inválido.")
    return {
        "id": id_, "x": round(x, 2), "y": round(y), "w": round(w), "h": round(h),
        "cor": p["cor"], "texto": texto,
    }


def postit_salvar(file, postit):
    """Cria ou atualiza (mesmo id) um post-it do documento; ele vai para o fim da lista."""
    novo = _validar_postit(postit)
    with LOCK:
        rel = _rel(_arquivo(file))
        caminho = _arquivo_postits(rel)
        lista = [p for p in _ler_postits(caminho) if p["id"] != novo["id"]]
        if len(lista) >= MAX_POSTITS:
            raise Erro(400, "limite", f"Este documento já tem {MAX_POSTITS} post-its.")
        lista.append(novo)
        _gravar_postits(caminho, lista)
        return {"ok": True}


def postit_apagar(file, id_):
    """Remove o post-it; um id que não existe é sucesso. Lista vazia apaga o arquivo e as pastas vazias."""
    if not isinstance(id_, str) or not POSTIT_ID_RE.match(id_):
        raise Erro(400, "postit", "Campo «id» inválido.")
    with LOCK:
        rel = _rel(_arquivo(file))
        caminho = _arquivo_postits(rel)
        lista = [p for p in _ler_postits(caminho) if p["id"] != id_]
        if os.path.exists(caminho):
            if lista:
                _gravar_postits(caminho, lista)
            else:
                try:
                    os.remove(caminho)
                except OSError:
                    pass
                _limpar_pastas_postits(caminho)
        return {"ok": True}


def carimbo_postits():
    """Hash de (caminho, mtime_ns, tamanho) de todo .json em dados/postits/."""
    h = hashlib.sha1()
    raiz = _raiz_postits()
    for dirpath, dirnames, filenames in os.walk(raiz):
        dirnames.sort()
        for nome in sorted(f for f in filenames if f.endswith(".json")):
            caminho = os.path.join(dirpath, nome)
            try:
                st = os.stat(caminho)
            except OSError:
                continue
            h.update(f"{_rel(caminho)}|{st.st_mtime_ns}|{st.st_size}\n".encode())
    return h.hexdigest()[:16]


def postits_todos():
    """{ '<doc.md>': [post-its] } só para documentos válidos que ainda têm post-its."""
    validos = {_rel(p) for p in sync.arquivos_md()}
    out = {}
    raiz = _raiz_postits()
    for dirpath, dirnames, filenames in os.walk(raiz):
        dirnames.sort()
        for nome in sorted(f for f in filenames if f.endswith(".json")):
            caminho = os.path.join(dirpath, nome)
            rel_md = os.path.relpath(caminho, raiz).replace("\\", "/")[:-5] + ".md"
            if rel_md not in validos:
                continue  # o documento foi renomeado, movido ou apagado por fora
            lista = _ler_postits(caminho)
            if lista:
                out[rel_md] = lista
    return out


# ---------- nota nova ----------

def slug_titulo(titulo):
    """'Reunião de Sexta!' -> 'reuniao-de-sexta'. Igual ao slugTitulo de write.js."""
    s = graphdata.strip_accents(titulo).lower()
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")[:80].strip("-")


# Nomes que o Windows não aceita como arquivo, com ou sem extensão (con.md, nul.md...): o título viraria um arquivo impossível.
RESERVADOS_WINDOWS = {"con", "prn", "aux", "nul"} | {f"{n}{i}" for n in ("com", "lpt") for i in range(1, 10)}

MAX_STATUS = 40   # caracteres; o título da coluna do quadro precisa caber


def frontmatter(tags, status=""):
    """'tags:' se houver tags, 'status:' se houver status. Igual ao frontmatter de write.js."""
    tags = list(dict.fromkeys(t for t in map(graphdata.normalize_tag, tags) if t))
    linhas = ([f"tags: [{', '.join(tags)}]"] if tags else []) + ([f"status: {' '.join(status.split())}"] if status.split() else [])
    return "---\n" + "\n".join(linhas) + "\n---\n" if linhas else ""


def montar_nota(titulo, tags, corpo, status=""):
    """Conteúdo do arquivo novo. Igual ao montarNota de write.js."""
    corpo = corpo.replace("\r\n", "\n").strip()
    if not corpo.startswith("# "):  # corpo com '# ' na primeira linha mantém o próprio título
        corpo = "# " + " ".join(titulo.split()) + (f"\n\n{corpo}" if corpo else "")
    return frontmatter(tags, status) + corpo + "\n"


def _pasta_valida(pasta):
    """'' é a raiz (grupo Home); senão, uma pasta existente dentro de uma pasta de topo que o sync varre."""
    if pasta == "":
        return True
    partes = pasta.split("/")
    return ("\\" not in pasta
            and not any(p == "" or p.startswith(".") for p in partes)
            and partes[0] in sync.pastas_topo()
            and not any(p in sync._ignoradas() for p in partes)   # node_modules, vendor...: a nota não entraria no menu
            and os.path.isdir(os.path.join(sync.ROOT, *partes)))


def nova(pasta, titulo, tags, corpo, status=""):
    if not all(isinstance(x, str) for x in (pasta, titulo, corpo, status)) or not isinstance(tags, list) \
            or not all(isinstance(t, str) for t in tags):
        raise Erro(400, "corpo", "Pedido incompleto.")
    if len(" ".join(status.split())) > MAX_STATUS:
        raise Erro(400, "status", f"O status pode ter até {MAX_STATUS} caracteres.")
    nome = slug_titulo(titulo)
    if not nome:
        raise Erro(400, "titulo", "O título precisa ter pelo menos uma letra ou número.")
    if nome in RESERVADOS_WINDOWS:
        raise Erro(400, "titulo", f"O nome «{nome}» não pode ser usado como arquivo no Windows. Mude o título.")
    pasta = pasta.strip("/")
    with LOCK:
        if not _pasta_valida(pasta):
            raise Erro(400, "pasta", "Pasta inválida.")
        rel = f"{pasta}/{nome}.md" if pasta else f"{nome}.md"
        caminho = os.path.join(sync.ROOT, *rel.split("/"))
        if os.path.exists(caminho):
            raise Erro(409, "existe", "Já existe uma nota com esse nome nesta pasta.")
        _gravar(caminho, montar_nota(titulo, tags, corpo, status))
        _sincronizar()
        for g in _dados[0]:
            for it in g["items"]:
                if it["file"] == rel:
                    return {"ok": True, "file": rel, "id": it["id"], "mtime": _mtime(caminho)}
        raise Erro(500, "sync", "A nota foi criada, mas não apareceu no menu.")
