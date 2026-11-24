#!/usr/bin/env python3
"""
sync.py — regenera site/js/content.js e site/js/graph-data.js a partir dos .md do projeto.

A RAIZ é a pasta que o site lê, e por padrão é a própria agLocalSite/ (onde ele está): nada fora dela é lido.
Para ler o projeto que CONTÉM a pasta (copiar agLocalSite/ para dentro de um projeto), ponha "raiz": ".." no config.json;
qualquer outra pasta também serve ("raiz": "../AgIAWeb"). Nenhum caminho precisa ser informado na linha de comando.

Rode este script quando editar um .md por fora do site, ou crie um .md/pasta nova. (Com o site aberto
pelo start.bat / start.sh isso é automático: o serve.py roda o mesmo sync quando percebe um .md alterado.
montar_dados() e escrever_arquivos() também são usadas pelo agwrite.py.)

Uso:
  python3 sync.py

Só biblioteca padrão do Python 3. Opções (título, pastas ignoradas, rótulos): agLocalSite/config.json.
"""

import json
import os
import re
import sys

import graphdata

AG_DIR = os.path.dirname(os.path.abspath(__file__))   # a pasta agLocalSite/
SITE_DIR = os.path.join(AG_DIR, "site")
DADOS_DIR = os.path.join(AG_DIR, "dados")              # historico/ (cópias) e postits/: nunca suja a raiz do projeto
CONFIG_PATH = os.path.join(AG_DIR, "config.json")
CONTENT_JS_PATH = os.path.join(SITE_DIR, "js", "content.js")
GRAPH_JS_PATH = os.path.join(SITE_DIR, "js", "graph-data.js")
TEMA_DADOS_JS_PATH = os.path.join(SITE_DIR, "js", "tema-dados.js")

# Pastas que nunca entram (em qualquer nível), além das ocultas (.git, .venv...), da própria agLocalSite e das do config.json.
IGNORE_DIRS = {
    "node_modules", "__pycache__", "venv", "env", "dist", "build", "target", "out", "coverage",
    "site-packages", "bower_components", "vendor", "Pods", "obj", "bin",
}
MAX_ARQUIVOS = 1500   # teto de .md no menu (o resto fica de fora, com aviso): content.js carrega o texto de todos
HOME_PRIORITY = ["inicio", "home", "index", "readme"]   # .md soltos na raiz que vêm primeiro no grupo Home


def config():
    """config.json (opcional). Chaves: raiz, titulo, subtitulo, ignorar [pastas], rotulos {pasta: rótulo}, home_prioridade [nomes], textos {...}."""
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8-sig") as f:
            c = json.load(f)
        return c if isinstance(c, dict) else {}
    except FileNotFoundError:
        return {}
    except (OSError, ValueError):
        print("AVISO: config.json ilegível ou com JSON inválido; usando os padrões.")
        return {}


class ConfigIlegivel(Exception):
    """config.json com JSON quebrado ou que não é um objeto; guarda a mensagem e a posição do erro."""

    def __init__(self, msg, linha=1, coluna=1):
        super().__init__(msg)
        self.msg, self.linha, self.coluna = msg, linha, coluna


def ler_config_estrito():
    """Como config(), mas sem engolir o erro: arquivo ausente dá {}; JSON quebrado levanta ConfigIlegivel (com linha e coluna)."""
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8-sig") as f:
            c = json.load(f)
    except FileNotFoundError:
        return {}
    except json.JSONDecodeError as e:
        raise ConfigIlegivel(e.msg, e.lineno, e.colno)
    except (OSError, ValueError) as e:   # UnicodeDecodeError é um ValueError
        raise ConfigIlegivel(f"não foi possível ler o arquivo ({e.__class__.__name__})")
    if not isinstance(c, dict):
        raise ConfigIlegivel('o config.json precisa ser um objeto, como { "titulo": "..." }')
    return c


def caminho_raiz(pedido):
    """Pasta pedida em config.json > raiz (relativa à pasta agLocalSite; também aceita caminho absoluto), ou None se não existir."""
    if not isinstance(pedido, str) or not pedido.strip():
        return None
    caminho = os.path.normpath(os.path.join(AG_DIR, os.path.expanduser(pedido.strip())))
    return caminho if os.path.isdir(caminho) else None


def resolver_raiz():
    return caminho_raiz(config().get("raiz", ".")) or AG_DIR


ROOT = resolver_raiz()   # a pasta lida pelo site: por padrão a própria agLocalSite. Mudar "raiz" no config.json vale no próximo start.


TEXTOS_CHAVES = ("grafo", "quadro", "mais", "menu", "tema_claro", "tema_escuro", "home", "rodape")
MAX_TEXTO, MAX_RODAPE = 120, 2000
# O que cada rótulo mostra quando o config.json não define "textos": são os do index.html e dos JS (um teste confere que não divergem).
TEXTOS_PADRAO = {"grafo": "◎ Grafo de tags", "quadro": "▦ Quadro", "mais": "+", "menu": "☰ Menu",
                 "tema_claro": "☀ Claro", "tema_escuro": "☾ Escuro", "home": "Home"}
PALETAS = (("padrao", "Padrão"), ("oceano", "Oceano"), ("floresta", "Floresta"), ("grafite", "Grafite"), ("ameixa", "Ameixa"))
MODOS = ("claro", "escuro", "sistema")
# Limites que o servidor valida e que o painel recebe de volta (para cliente e servidor nunca divergirem).
LIMITES = {"texto": MAX_TEXTO, "rodape": MAX_RODAPE, "itens_ignorar": 200, "nome": 100, "rotulos": 200, "home": 50}


def tema():
    """config.json > tema: {"paleta", "modo"}. Valor fora da lista cai no padrão (avisos_config() avisa)."""
    bruto = config().get("tema", {})
    bruto = bruto if isinstance(bruto, dict) else {}
    paleta, modo = bruto.get("paleta"), bruto.get("modo")
    return {"paleta": paleta if paleta in [n for n, _ in PALETAS] else "padrao",
            "modo": modo if modo in MODOS else "claro"}
PREFIXO_PADRAO = "_ag"


def textos():
    """config.json > textos: só as chaves conhecidas e só strings. Ex.: {"grafo": "◎ Mapa", "rodape": ""}."""
    bruto = config().get("textos", {})
    if not isinstance(bruto, dict):
        return {}
    return {k: v.strip()[:MAX_RODAPE if k == "rodape" else MAX_TEXTO]
            for k, v in bruto.items() if k in TEXTOS_CHAVES and isinstance(v, str)}


def prefixo_url():
    """Endereço do site dentro do servidor (padrão: _ag, ou seja, http://localhost:8000/_ag/). Um só trecho: letras, números, _ e -."""
    v = config().get("prefixo_url", PREFIXO_PADRAO)
    return v if isinstance(v, str) and re.fullmatch(r"[A-Za-z0-9_-]{1,32}", v) and v.lower() != "api" else PREFIXO_PADRAO


def avisos_config():
    """Problemas do config.json que o usuário precisa saber (chave com erro de digitação, prefixo inválido ou que esconde uma pasta)."""
    out = []
    bruto = config().get("textos", {})
    if isinstance(bruto, dict):
        for k in bruto:
            if k not in TEXTOS_CHAVES:
                out.append(f'config.json: "textos.{k}" não existe (use: {", ".join(TEXTOS_CHAVES)}).')
            elif not isinstance(bruto[k], str):
                out.append(f'config.json: "textos.{k}" precisa ser texto.')
    elif "textos" in config():
        out.append('config.json: "textos" precisa ser um objeto, como {"grafo": "◎ Mapa"}.')
    bruto_tema = config().get("tema")
    if bruto_tema is not None:
        nomes = [n for n, _ in PALETAS]
        if not isinstance(bruto_tema, dict):
            out.append('config.json: "tema" precisa ser um objeto, como {"paleta": "oceano", "modo": "sistema"}.')
        else:
            if "paleta" in bruto_tema and bruto_tema["paleta"] not in nomes:
                out.append(f'config.json: "tema.paleta" ({bruto_tema["paleta"]!r}) não existe; usando "padrao". Opções: {", ".join(nomes)}.')
            if "modo" in bruto_tema and bruto_tema["modo"] not in MODOS:
                out.append(f'config.json: "tema.modo" ({bruto_tema["modo"]!r}) não existe; usando "claro". Opções: {", ".join(MODOS)}.')
    raiz = config().get("raiz", ".")
    em_branco = raiz is None or (isinstance(raiz, str) and not raiz.strip())   # vazio = padrão, sem aviso
    if not em_branco and caminho_raiz(raiz) is None:
        out.append(f'config.json: "raiz" ({raiz!r}) não é uma pasta existente (o caminho é relativo à agLocalSite); lendo só a própria agLocalSite.')
    pedido = config().get("prefixo_url", PREFIXO_PADRAO)
    if pedido != prefixo_url():
        out.append(f'config.json: "prefixo_url" inválido ({pedido!r}); usando "{PREFIXO_PADRAO}". Aceita letras, números, _ e -, até 32, e não pode ser "api".')
    if os.path.isdir(os.path.join(ROOT, prefixo_url())):
        out.append(f'config.json: a pasta "{prefixo_url()}" da raiz fica escondida atrás do endereço do site; troque "prefixo_url".')
    return out


def _ignoradas():
    extra = config().get("ignorar", [])
    return IGNORE_DIRS | {os.path.basename(AG_DIR)} | {x for x in extra if isinstance(x, str)}


def _oculta_ou_ignorada(nome, ignoradas):
    return nome.startswith(".") or nome in ignoradas


def auto_label(folder_name):
    """Rótulo para a pasta: '02-Produtos-e-Modulos' -> '02 · Produtos e modulos'. Troque em config.json > rotulos."""
    def cap(s):
        s = s.replace("-", " ").replace("_", " ").strip()
        return s[:1].upper() + s[1:]
    m = re.match(r"^(\d+)[-_]?(.*)$", folder_name)
    if m:
        num, rest = m.groups()
        rest = cap(rest)
        return f"{num} · {rest}" if rest else num
    return cap(folder_name)


def slugify(path):
    s = re.sub(r"\.md$", "", path, flags=re.IGNORECASE)
    s = re.sub(r"[/\\]", "-", s)
    s = s.lower()
    s = re.sub(r"[^a-z0-9\-]", "-", s)
    s = re.sub(r"-+", "-", s).strip("-")
    return s


def title_from_file(rel_path, abs_path, text):
    """Primeiro '# Título' do markdown; senão o nome do arquivo (ou da pasta, no caso de README.md)."""
    sem_fences = re.sub(r"^(```|~~~).*?^\1[^\n]*$|^(```|~~~).*\Z", "", graphdata.strip_frontmatter(text), flags=re.MULTILINE | re.DOTALL)  # "# comentário" de shell dentro de fence não é título
    m = re.search(r"^#\s+(.+)$", sem_fences, flags=re.MULTILINE)
    if m:
        return m.group(1).strip()
    base = os.path.splitext(os.path.basename(rel_path))[0]
    if base.lower() == "readme":
        parent = os.path.basename(os.path.dirname(rel_path))
        return parent or base
    return base.replace("-", " ").replace("_", " ")


def _ler(abs_path):
    # errors="replace": um .md fora de UTF-8 aparece com "?" em vez de derrubar o sync
    with open(abs_path, "r", encoding="utf-8", errors="replace") as f:
        return f.read()


# Windows + OneDrive ("Arquivos Sob Demanda"): arquivo ou pasta que existe só na nuvem. Abrir ou listar isso faz o OneDrive
# baixar. Os atributos vêm junto da listagem da pasta, então checar não baixa nada. OFFLINE | RECALL_ON_OPEN | RECALL_ON_DATA_ACCESS.
ATRIBUTOS_NUVEM = 0x1000 | 0x40000 | 0x400000
_WINDOWS = os.name == "nt"
NUVEM_PULADOS = set()   # caminhos que ficaram de fora por estarem só na nuvem (o montar_dados avisa)


def so_na_nuvem(entrada):
    """entrada é um os.DirEntry. Sempre False fora do Windows (não existe st_file_attributes)."""
    if not _WINDOWS:
        return False
    try:
        return bool(getattr(entrada.stat(follow_symlinks=False), "st_file_attributes", 0) & ATRIBUTOS_NUVEM)
    except OSError:
        return False


def _listar(pasta, seguir_links=False):
    """(subpastas, arquivos) de uma pasta, em ordem. Pula o que está só na nuvem, sem abrir nem entrar."""
    dirs, files = [], []
    try:
        with os.scandir(pasta) as it:
            for e in it:
                if so_na_nuvem(e):
                    # só vale avisar o que o site usaria: .md e pastas (zip, imagem etc. só-nuvem nunca entrariam no menu)
                    if e.name.lower().endswith(".md") or e.is_dir(follow_symlinks=False):
                        NUVEM_PULADOS.add(e.path)
                    continue
                try:
                    if e.is_dir(follow_symlinks=seguir_links):
                        dirs.append(e.name)
                    elif e.is_file():
                        files.append(e.name)
                except OSError:
                    continue
    except OSError:
        pass
    return sorted(dirs), sorted(files)


def _e_dados(caminho):
    """A pasta dados/ (histórico e post-its) nunca é varrida: quando a raiz é a própria agLocalSite, ela estaria dentro."""
    return os.path.normcase(os.path.abspath(caminho)) == os.path.normcase(os.path.abspath(DADOS_DIR))


def _norm_nome(p):
    """Como o Windows enxerga o nome: sem ponto ou espaço no fim ("dados." abre "dados") e sem fluxo alternativo NTFS ("dados::$DATA")."""
    return p.split(":")[0].rstrip(". ").lower()


def _nome_curto(p, alvo):
    """True se p parece o nome 8.3 do Windows (AGLOCA~1) de uma pasta de nome longo (agLocalSite)."""
    m = re.fullmatch(r"([^~.]{1,6})~\d+", p)
    return bool(m) and len(alvo) > 8 and alvo.replace(" ", "").startswith(m.group(1))


def protegido(partes):
    """True para o que o servidor nunca serve da raiz: pastas ocultas (.git), a própria agLocalSite (se está dentro da raiz) e dados/."""
    if any(p.startswith(".") for p in partes):
        return True
    abaixo = [_norm_nome(p) for p in partes]
    for alvo in (AG_DIR, DADOS_DIR):
        try:
            rel = os.path.relpath(alvo, ROOT)
        except ValueError:   # outro disco no Windows: não está dentro da raiz
            continue
        if rel == "." or rel.startswith(".."):
            continue
        alvo_partes = [p.lower() for p in rel.replace("\\", "/").split("/")]
        n = len(alvo_partes)
        if len(abaixo) >= n and all(a == b or (os.name == "nt" and _nome_curto(a, b)) for a, b in zip(abaixo, alvo_partes)):
            return True
    return False


def find_md_files(folder_abs):
    """Todo .md local dentro da pasta, recursivamente e em ordem estável, sem entrar em pasta oculta, ignorada ou só na nuvem."""
    ignoradas = _ignoradas()
    found = []

    def andar(pasta):
        dirs, files = _listar(pasta)
        found.extend(os.path.join(pasta, fn) for fn in files if fn.lower().endswith(".md"))
        for d in dirs:
            if not _oculta_ou_ignorada(d, ignoradas) and not _e_dados(os.path.join(pasta, d)):
                andar(os.path.join(pasta, d))

    andar(folder_abs)
    return found


def pastas_topo():
    """Pastas de topo da raiz que o sync varre."""
    ignoradas = _ignoradas()
    dirs, _ = _listar(ROOT, seguir_links=True)
    return [d for d in dirs if not _oculta_ou_ignorada(d, ignoradas) and not _e_dados(os.path.join(ROOT, d))]


def _soltos():
    """.md soltos na raiz do projeto (caminhos absolutos)."""
    _, files = _listar(ROOT)
    return [os.path.join(ROOT, fn) for fn in files if fn.lower().endswith(".md")]


def arquivos_md():
    """Todo .md que o sync varre (caminhos absolutos), limitado a MAX_ARQUIVOS."""
    todos = _soltos() + [p for d in pastas_topo() for p in find_md_files(os.path.join(ROOT, d))]
    return todos[:MAX_ARQUIVOS]


def build_home_group(permitidos):
    """Os .md soltos na raiz viram o grupo 'Home', sempre no topo do menu."""
    prioridade = [str(x).lower() for x in config().get("home_prioridade", HOME_PRIORITY)]

    def sort_key(fn):
        name = os.path.splitext(fn)[0].lower()
        if name in prioridade:
            return (prioridade.index(name), name)
        return (len(prioridade), name)

    root_mds = sorted((os.path.basename(p) for p in _soltos() if p in permitidos), key=sort_key)
    if not root_mds:
        return None
    items = []
    for fn in root_mds:
        text = _ler(os.path.join(ROOT, fn))
        items.append({"title": title_from_file(fn, fn, text), "file": fn, "id": slugify(fn), "fallback": text})
    return {"id": "home", "label": textos().get("home") or "Home", "folder": ".", "items": items}


def montar_dados():
    """Lê os .md e devolve (grupos, grafo): o que vai para content.js e graph-data.js."""
    NUVEM_PULADOS.clear()
    permitidos = set(arquivos_md())
    total = len(_soltos()) + sum(len(find_md_files(os.path.join(ROOT, d))) for d in pastas_topo())
    if total > MAX_ARQUIVOS:
        print(f"AVISO: {total} arquivos .md; o menu mostra só {MAX_ARQUIVOS}. Use \"ignorar\" em config.json para as pastas que não interessam.")

    if NUVEM_PULADOS:
        mds = sorted(c for c in NUVEM_PULADOS if c.lower().endswith(".md"))
        pastas = len(NUVEM_PULADOS) - len(mds)
        ex = ", ".join(os.path.relpath(c, ROOT) for c in mds[:5])
        print(f"AVISO: {len(mds)} .md e {pastas} pasta(s) só na nuvem (OneDrive) ficaram de fora do menu para não serem baixados."
              f"{' Ex.: ' + ex + ('...' if len(mds) > 5 else '') + '.' if mds else ''}"
              " Para incluir, deixe-os \"sempre neste dispositivo\" no OneDrive.")

    rotulos = config().get("rotulos", {})
    groups, seen_ids = [], set()

    home_group = build_home_group(permitidos)
    if home_group:
        groups.append(home_group)
        seen_ids.update(it["id"] for it in home_group["items"])

    for folder_name in pastas_topo():
        md_files = [p for p in find_md_files(os.path.join(ROOT, folder_name)) if p in permitidos]
        if not md_files:
            continue  # pasta sem nenhum .md -> não aparece no menu

        items = []
        for abs_path in md_files:
            rel_path = os.path.relpath(abs_path, ROOT).replace("\\", "/")
            text = _ler(abs_path)
            item_id = base_id = slugify(rel_path)
            n = 2
            while item_id in seen_ids:  # id único mesmo em colisão extrema
                item_id = f"{base_id}-{n}"
                n += 1
            seen_ids.add(item_id)
            items.append({"title": title_from_file(rel_path, abs_path, text), "file": rel_path, "id": item_id, "fallback": text})

        label = rotulos.get(folder_name) if isinstance(rotulos, dict) else None
        groups.append({"id": slugify(folder_name), "label": label or auto_label(folder_name), "folder": folder_name, "items": items})

    return groups, graphdata.build(groups)


def dados_site(c=None):
    """O que o site mostra na tela, do config.json (cada chave é opcional; vazio usa o padrão).
    Com c = {} devolve os padrões de titulo, subtitulo, etiqueta e titulo_aba (textos e tema sempre vêm do config.json de verdade)."""
    c = config() if c is None else c
    pasta = os.path.basename(ROOT) or "Projeto"

    def txt(chave, padrao):
        v = c.get(chave)
        return " ".join(v.split())[:MAX_TEXTO] if isinstance(v, str) and v.strip() else padrao

    titulo = txt("titulo", pasta)
    return {
        "titulo": titulo,
        "subtitulo": txt("subtitulo", ""),
        "etiqueta": txt("etiqueta", "agLocalSite" if os.path.normcase(ROOT) == os.path.normcase(AG_DIR) else pasta.upper() + " / agLocalSite"),
        "titulo_aba": txt("titulo_aba", titulo + " — agLocalSite"),
        "pasta": pasta,
        "textos": textos(),
        "tema": tema(),
    }


def _escrever_atomico(caminho, texto):
    """Grava em arquivo temporário e troca: quem carrega a página nesse instante nunca lê um .js cortado.
    Se o sistema recusar a troca (Windows com o arquivo aberto), cai na escrita direta de antes."""
    tmp = caminho + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(texto)
        os.replace(tmp, caminho)
    except OSError:
        try:
            os.remove(tmp)
        except OSError:
            pass
        with open(caminho, "w", encoding="utf-8") as f:
            f.write(texto)


def escrever_arquivos(groups, graph):
    js = (
        "// Bloco de dados do site — GERADO AUTOMATICAMENTE por sync.py.\n"
        "// Não edite este arquivo à mão: edite os .md do projeto e rode `python3 sync.py` de novo\n"
        "// (ou dê duplo-clique em sync.bat / sync.sh).\n"
        "const AG_CONFIG = " + json.dumps(dados_site(), ensure_ascii=False) + ";\n"
        "const AG_CONTENT = " + json.dumps(groups, ensure_ascii=False, indent=2) + ";\n"
    )
    os.makedirs(os.path.dirname(CONTENT_JS_PATH), exist_ok=True)
    _escrever_atomico(CONTENT_JS_PATH, js)
    _escrever_atomico(GRAPH_JS_PATH, graphdata.render_js(graph))
    _escrever_atomico(TEMA_DADOS_JS_PATH, "// Tema do site — GERADO AUTOMATICAMENTE por sync.py a partir do config.json. Não edite.\n"
                "const AG_TEMA = " + json.dumps({**tema(), "paletas": [n for n, _ in PALETAS]}, ensure_ascii=False) + ";\n")


def main():
    for a in avisos_config():
        print("AVISO:", a)
    groups, graph = montar_dados()
    escrever_arquivos(groups, graph)
    total_items = sum(len(g["items"]) for g in groups)
    curated = sum(1 for d in graph["docs"] if d["tags"]["curated"])
    print(f"Raiz do projeto: {ROOT}")
    print(f"OK — content.js atualizado: {len(groups)} pastas, {total_items} documentos.")
    print(f"OK — graph-data.js atualizado: {curated} de {len(graph['docs'])} documentos com tags curadas.")


if __name__ == "__main__":
    main()
