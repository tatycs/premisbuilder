# utils.py
# -----------------------------------------------------------------------------
# Utilitários para construir PREMIS 3.0 em XML a partir de CSV.
#
# Convenções e políticas:
# - Elementos PREMIS são emitidos no namespace padrão do PREMIS 3.0.
# - Para extensões do E-Docs usamos elementos literais do tipo:
#     <ext-edocs.ext.algo>...</ext-edocs.ext.algo>
#   (sem namespace XML; o nome inclui o prefixo como parte do local-name).
# - Blocos repetíveis são coletados por 'collect_blocks', que:
#     * percorre os pares (cabeçalho, valor) em ordem,
#     * agrupa pelos 'fields' definidos,
#     * permite marcar campos que acumulam valores (accumulate_keys),
#     * considera o bloco "válido" se QUALQUER campo tiver valor (accept_if_any=True).
# - Campos com múltiplos valores podem ser:
#     * repetidos em colunas iguais (coletor acumula),
#     * separados por pipe ("a | b | c") — use 'split_pipe' para "explodir".
# -----------------------------------------------------------------------------

import re
import xml.etree.ElementTree as ET
from datetime import datetime

# Namespace PREMIS como default (todos os elementos que criamos ficam nele).
PREMIS_NS = "http://www.loc.gov/premis/v3"

# Mapa de namespaces (se desejar registrar em outros pontos do programa).
NS = {"premis": PREMIS_NS,
      "xlink": "http://www.w3.org/1999/xlink",
      "xsi": "http://www.w3.org/2001/XMLSchema-instance",
}

# Prefixo textual usado nos elementos de extensão, como <ext-edocs.ext.summary>
# (não é um namespace XML; é parte literal do nome da tag).
EXT_NS_PREFIX = "ext-edocs"

# Se em algum lugar você criar o elemento raiz, convém registrar o default:
# ET.register_namespace('', PREMIS_NS)  # opcional; costuma ser feito na criação do root


# -----------------------------------------------------------------------------
# Helpers básicos para criação de elementos/texto
# -----------------------------------------------------------------------------

def _q(tag: str) -> str:
    """Monta um Clark notation '{ns}tag' para o namespace PREMIS."""
    return f"{{{PREMIS_NS}}}{tag}"

def add(parent: ET.Element, tag: str) -> ET.Element:
    """Cria um subelemento PREMIS (namespace default) dentro de 'parent'."""
    return ET.SubElement(parent, _q(tag))

def add_text(parent: ET.Element, tag: str, text) -> ET.Element | None:
    """
    Cria <tag> sob 'parent' (no ns PREMIS) somente se 'text' não for vazio.
    Normaliza para string e aplica .strip().
    Retorna o elemento criado ou None (se não criou).
    """
    val = str(text).strip() if text is not None else ""
    if not val:
        return None
    el = ET.SubElement(parent, _q(tag))
    el.text = val
    return el

def emit_roles(parent: ET.Element, tag: str, values) -> None:
    """
    Emite múltiplos elementos <tag> (ns PREMIS) a partir de 'values'.
    'values' pode ser:
      - string com pipes: "a | b | c"
      - string única: "a"
      - já acumulado por collect_blocks (mesma regra de pipe)
    """
    for piece in split_pipe(values):
        add_text(parent, tag, piece)

def first_nonempty(*values, default: str = "") -> str:
    """
    Compat: devolve o primeiro valor não-vazio (após strip()) dentre 'values'.
    Se todos forem vazios/None, retorna 'default'.
    """
    for v in values:
        s = "" if v is None else str(v).strip()
        if s:
            return s
    return default

# -----------------------------------------------------------------------------
# Coleta e transformação de pares (header, value)
# -----------------------------------------------------------------------------

def split_pipe(s) -> list[str]:
    """
    Divide uma string por pipes " | " em uma lista de valores limpos.
    Retorna [] se não houver conteúdo.
    """
    return [p.strip() for p in str(s or "").split("|") if str(p).strip()]

def collect_multival(pairs: list[tuple[str, str]], key: str) -> list[str]:
    """
    Retorna todos os valores (não-vazios) para o 'key' dado,
    preservando a ordem em que aparecem no CSV.
    Útil para elementos simples e repetíveis (ex.: objectCharacteristicsExtension).
    """
    out = []
    for k, v in pairs:
        if k == key:
            val = str(v).strip()
            if val:
                out.append(val)
    return out


# -----------------------------------------------------------------------------
# Coletor de blocos repetíveis
# -----------------------------------------------------------------------------

def collect_blocks(
    pairs: list[tuple[str, str]],
    fields: list[str],
    accumulate_keys: set[str] | None = None,
    accumulate_last: bool | None = None,
    need_keys: list[str] | None = None,
    accept_if_any: bool = True,
) -> list[dict[str, str]]:
    """
    Varre 'pairs' da esquerda para a direita e agrupa valores conforme a lista 'fields'.

    Regras principais:
      - Segmentação de blocos: quando o PRIMEIRO campo de 'fields' reaparece
        e o bloco atual já é "aceitável", o bloco é fechado e um novo é iniciado.
      - Aceitação de bloco:
          * Se 'need_keys' foi fornecido: exige que TODOS esses campos estejam preenchidos.
          * Caso contrário, se 'accept_if_any'==True (padrão): aceita se QUALQUER campo do
            bloco estiver preenchido.
          * Senão (accept_if_any==False e need_keys ausente): cai no comportamento
            "antigo" (exigir os 2 primeiros campos).
      - Acúmulo (accumulate_keys): campos listados acumulam "a | b | c" em vez de sobrescrever.
      - Compatibilidade: se 'accumulate_last=True' for passado (código antigo),
        e 'accumulate_keys' não foi dado, acumula o ÚLTIMO campo de 'fields'.

    Retorno:
      Lista de dicionários, cada um com TODAS as chaves de 'fields'
      (ausentes/vazias com string vazia "").
    """
    # Compat: manter suporte ao parâmetro antigo 'accumulate_last'
    if accumulate_keys is None and accumulate_last:
        accumulate_keys = {fields[-1]}
    if accumulate_keys is None:
        accumulate_keys = set()

    def block_has_any(d: dict[str, str]) -> bool:
        return any(str(d.get(k, "")).strip() for k in fields)

    def block_is_complete(d: dict[str, str]) -> bool:
        if need_keys:
            return all(str(d.get(k, "")).strip() for k in need_keys)
        if accept_if_any:
            return block_has_any(d)
        # legado: exigir dois primeiros campos
        req = fields[:2]
        return all(str(d.get(k, "")).strip() for k in req)

    out: list[dict[str, str]] = []
    cur = {f: "" for f in fields}

    def flush_if_needed():
        nonlocal cur
        if block_is_complete(cur):
            out.append(cur)
        cur = {f: "" for f in fields}

    for k, v in pairs:
        # ignorar cabeçalhos fora do bloco
        if k not in fields:
            continue
        val = str(v).strip()

        # Se o primeiro campo reaparece e o bloco atual já é "aceitável", fecha bloco
        if k == fields[0] and block_is_complete(cur):
            flush_if_needed()

        if not val:
            continue

        # Campo com acúmulo (p.ex. notas/roles etc.)
        if k in accumulate_keys:
            cur[k] = (cur[k] + " | " + val) if cur[k] else val
        else:
            cur[k] = val

    # Fecha o último bloco, se tiver algo
    if block_is_complete(cur):
        out.append(cur)

    return out


# -----------------------------------------------------------------------------
# Normalização "leve" de datas/horas (best effort)
# -----------------------------------------------------------------------------

_ISO_RE = re.compile(r"^\d{4}-\d{2}-\d{2}(T|\s)\d{2}:\d{2}(:\d{2})?([+-]\d{2}:\d{2}|Z|[+-]\d{2})?$")
_DATE_ONLY_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

def normalize_dt(value: str) -> str:
    """
    Tenta devolver uma string de data/hora em formato consistente:
      - Se já parece ISO (YYYY-MM-DDTHH:MM[:SS][offset]), devolve como veio.
      - Se vier como "YYYY-MM-DD HH:MM[:SS][offset]" troca espaço por 'T'.
      - Se vier só data "YYYY-MM-DD", devolve como veio.
      - Caso contrário, retorna o texto original (não força conversão).
    """
    if value is None:
        return ""
    s = str(value).strip()
    if not s:
        return ""
    # já parece ISO
    if _ISO_RE.match(s):
        # normaliza espaço para 'T' se existir
        return s.replace(" ", "T")
    # data única
    if _DATE_ONLY_RE.match(s):
        return s
    # tenta alguns formatos comuns e converte para ISO sem timezone
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%d/%m/%Y %H:%M:%S", "%d/%m/%Y %H:%M"):
        try:
            dt = datetime.strptime(s, fmt)
            return dt.strftime("%Y-%m-%dT%H:%M:%S")
        except Exception:
            pass
    # manter original se não reconhecido
    return s
