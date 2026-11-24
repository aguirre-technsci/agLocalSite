"""
graphdata.py — tags e dados do grafo. Usado pelo sync.py; não roda sozinho.

Cada documento recebe tags de três origens:
  curated : frontmatter do .md   (tags: [algoritmo, 3d, dados_abertos])
  folder  : caminho da pasta, em níveis aninhados (produtos/alfa/...)
  text    : palavras distintivas do texto (TF-IDF sobre todos os documentos)

Só biblioteca padrão do Python 3.
"""

import json
import math
import re
import unicodedata
from collections import Counter

TEXT_TAGS_PER_DOC = 5
MIN_WORD_LEN = 4

# Bloco de frontmatter: '---' na primeira linha, YAML, '---' de fechamento.
_FM = re.compile(r"\A\ufeff?---[ \t]*\r?\n(.*?)\r?\n---[ \t]*(?:\r?\n|\Z)", re.S)
# Uma linha de frontmatter válido: comentário, item de lista, continuação ou 'chave: valor'.
_FM_LINE = re.compile(r"^(\s*#.*|\s*-\s.*|\s+\S.*|[A-Za-z_][\w -]*:.*|\s*)$")

STOPWORDS = set("""
para como mais muito muitos muita muitas quando entre sobre depois antes essa esse essas esses esta este estas estes
isso isto aquela aquele aquilo onde porque pela pelo pelas pelos dele dela deles delas suas seus sua nosso nossa
nossos nossas voce voces tudo toda todo todas todos cada outro outra outros outras ainda apenas assim tambem mesmo
mesma mesmos mesmas entao aqui alem pode podem poder deve devem dever tenha tenho tinha temos tiver ter ser sao foi
foram esta estao estou estamos estar estava havia sendo sido fazer feito fazendo faz fazem pois desde sempre nunca
cujo cuja qual quais quem fora dentro junto logo seja sejam sera serao seria seriam quer quero queria alguns algumas
algum alguma nenhum nenhuma qualquer quaisquer vez vezes bem mal maior menor melhor pior primeiro primeira segundo
segunda terceiro terceira ultimo ultima ambos ambas tanto tanta tantos tantas tao quase demais menos alias ante
apos atraves contra durante perante sob trás tras conforme segundo mediante embora porem contudo todavia entretanto
enquanto portanto assim caso via cada onde aonde donde eles elas voce coisa coisas parte partes forma formas modo
modos tipo tipos ponto pontos lado lados casos ordem numero numeros exemplo exemplos http https html readme
""".split())


def strip_accents(s):
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


def normalize_tag(s):
    """minúsculas, sem acento; espaço e hífen viram '_'; '/' separa níveis. Igual ao normTag de search.js."""
    s = strip_accents(str(s)).lower().strip().lstrip("#")
    s = re.sub(r"[\s-]+", "_", s)
    s = re.sub(r"[^a-z0-9_/]", "", s)
    s = re.sub(r"_+", "_", s)
    s = re.sub(r"/+", "/", s)
    return re.sub(r"_?/_?", "/", s).strip("_/")


def split_frontmatter(text):
    """Devolve (bloco_yaml, corpo). Sem frontmatter válido: (None, texto)."""
    m = _FM.match(text)
    if not m:
        return None, text
    if not all(_FM_LINE.match(line) for line in m.group(1).splitlines()):
        return None, text  # '---' de linha horizontal, não frontmatter
    return m.group(1), text[m.end():]


def strip_frontmatter(text):
    return split_frontmatter(text)[1]


def parse_curated_tags(fm, warn=None, where=""):
    """Lê 'tags: [a, b]', 'tags: a, b' ou lista em linhas ('- a'). Chave 'tag:' também vale."""
    lines = fm.splitlines()
    for i, line in enumerate(lines):
        m = re.match(r"^tags?\s*:\s*(.*)$", line, re.I)
        if not m:
            continue
        rest = m.group(1).strip()
        if rest.startswith("["):
            if not rest.endswith("]"):
                if warn:
                    warn(f"AVISO: 'tags' com colchete aberto em {where}; tags curadas ignoradas.")
                return []
            items = rest[1:-1].split(",")
        elif rest:
            items = re.split(r"\s*,\s*|\s+", rest)
        else:
            items = []
            for nxt in lines[i + 1:]:
                lm = re.match(r"^\s*-\s*(.+)$", nxt)
                if not lm:
                    break
                items.append(lm.group(1))
        out = []
        for it in items:
            t = normalize_tag(it.strip().strip("\"'"))
            if t and t not in out:
                out.append(t)
        return out
    return []


def folder_tags(rel_path):
    """02-Produtos/Alfa/X/README.md -> [produtos, produtos/alfa, produtos/alfa/x]"""
    out, acc = [], ""
    for part in rel_path.replace("\\", "/").split("/")[:-1]:
        name = normalize_tag(re.sub(r"^\d+[-_ ]*", "", part))
        if not name:
            continue
        acc = f"{acc}/{name}" if acc else name
        out.append(acc)
    return out


def _tokens(body):
    body = re.sub(r"```.*?```", " ", body, flags=re.S)
    body = re.sub(r"https?://\S+", " ", body)
    words = re.findall(r"[a-z]{%d,}" % MIN_WORD_LEN, strip_accents(body).lower())
    return [w for w in words if w not in STOPWORDS]


def text_tags(bodies, exclude=None):
    """TF-IDF. bodies: {id: corpo}. Só palavras em >=2 documentos e em menos da metade deles."""
    exclude = exclude or {}
    counts = {i: Counter(_tokens(b)) for i, b in bodies.items()}
    df = Counter()
    for c in counts.values():
        df.update(c.keys())
    n = len(bodies)
    out = {}
    for i, c in counts.items():
        cands = [
            (tf * math.log(n / df[w]), w)
            for w, tf in c.items()
            if df[w] >= 2 and df[w] < n * 0.5 and w not in exclude.get(i, ())
        ]
        cands.sort(key=lambda x: (-x[0], x[1]))
        out[i] = [w for _, w in cands[:TEXT_TAGS_PER_DOC]]
    return out


def build(groups, warn=print):
    """groups: lista de grupos do content.js. Devolve {'docs': [...]} para o graph-data.js."""
    docs, bodies, curated_by_id = [], {}, {}
    for g in groups:
        for it in g["items"]:
            text = it["fallback"]
            fm, body = split_frontmatter(text)
            curated = []
            if fm is not None:
                curated = parse_curated_tags(fm, warn, it["file"])
            elif re.match(r"\A\ufeff?---[ \t]*\r?\n[A-Za-z_][\w -]*:", text):
                warn(f"AVISO: frontmatter sem fechamento em {it['file']}; ignorado.")
            docs.append({
                "id": it["id"],
                "title": it["title"],
                "file": it["file"],
                "tags": {"curated": curated, "folder": folder_tags(it["file"]), "text": []},
            })
            bodies[it["id"]] = body
            curated_by_id[it["id"]] = set(curated)
    auto = text_tags(bodies, curated_by_id)
    for d in docs:
        d["tags"]["text"] = auto[d["id"]]
    return {"docs": docs}


def render_js(graph):
    return (
        "// Dados do grafo — GERADO AUTOMATICAMENTE por sync.py.\n"
        "// Não edite à mão: edite as tags no frontmatter dos .md e rode o sync de novo.\n"
        "const AG_GRAPH = "
        + json.dumps(graph, ensure_ascii=False, indent=1)
        + ";\n"
    )
