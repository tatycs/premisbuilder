# utils.py
# -----------------------------------------------------------------------------
# Funções utilitárias compartilhadas por todos os construtores PREMIS.
#
# Este módulo fornece:
#   - Constantes de namespace (NS, PREMIS_NS, EXT_NS_PREFIX)
#   - Helpers para criar elementos XML: add(), add_text(), emit_roles()
#   - Coletores de dados do CSV: collect_multival(), collect_blocks()
#   - Normalização de datas: normalize_dt()
#   - Divisão por pipe: split_pipe()
#
# Convenções adotadas no projeto:
#   - Todos os elementos PREMIS são criados no namespace oficial do PREMIS 3.0.
#   - Elementos de extensão (ob.ext.*) usam o prefixo "ext-edocs" como parte
#     literal do nome da tag (não são namespace XML; é só convenção de nome).
#   - Blocos repetíveis no CSV são agrupados por collect_blocks().
#   - Valores múltiplos em um mesmo campo podem vir separados por pipe " | ".
#
# Legenda usada nos comentários dos builders:
#   M  = Mandatory   (obrigatório no esquema PREMIS)
#   O  = Optional    (opcional)
#   R  = Repeatable  (pode ocorrer mais de uma vez)
#   NR = Not Repeatable (ocorre no máximo uma vez)
# -----------------------------------------------------------------------------

import re
import xml.etree.ElementTree as ET
from datetime import datetime


# =============================================================================
# Constantes de namespace
# =============================================================================

# URI oficial do namespace PREMIS 3.0
PREMIS_NS = "http://www.loc.gov/premis/v3"

# Dicionário de namespaces usado ao registrar prefixos e criar elementos raiz
NS = {
    "premis": PREMIS_NS,
    "xlink":  "http://www.w3.org/1999/xlink",
    "xsi":    "http://www.w3.org/2001/XMLSchema-instance",
}

# Prefixo textual para elementos de extensão customizados.
# Exemplo: a chave "ob.ext.resumo" vira o elemento <ext-edocs.ext.resumo>.
# NÃO é um namespace XML — o prefixo faz parte do nome literal da tag.
EXT_NS_PREFIX = "ext-edocs"


# =============================================================================
# Helpers básicos para criação de elementos e texto XML
# =============================================================================

def _q(tag: str) -> str:
    """
    Monta a notação Clark para um elemento no namespace PREMIS.

    A notação Clark é o formato que o ElementTree usa internamente:
        {http://www.loc.gov/premis/v3}nomeDoElemento

    Exemplo:
        _q('object') → '{http://www.loc.gov/premis/v3}object'
    """
    return f"{{{PREMIS_NS}}}{tag}"


def add(parent: ET.Element, tag: str) -> ET.Element:
    """
    Cria e retorna um subelemento PREMIS vazio dentro de 'parent'.

    O elemento é criado no namespace PREMIS (usando notação Clark internamente).
    No XML final, aparecerá com o prefixo "premis:" se o namespace estiver
    registrado, ex.: <premis:object>.

    Parâmetros:
        parent — elemento pai no qual o novo elemento será inserido
        tag    — nome local do elemento (ex.: 'object', 'event', 'agent')
    """
    return ET.SubElement(parent, _q(tag))


def add_text(parent: ET.Element, tag: str, text) -> ET.Element | None:
    """
    Cria um subelemento PREMIS com conteúdo textual dentro de 'parent',
    MAS somente se o texto não for vazio após normalização.

    Política "sem elementos fantasmas": se 'text' for None, vazio ou só
    espaços, o elemento NÃO é criado e a função retorna None.
    Isso evita gerar tags vazias como <premis:formatName/> no XML.

    Parâmetros:
        parent — elemento pai
        tag    — nome local do elemento (ex.: 'formatName')
        text   — conteúdo textual (qualquer tipo; será convertido para str)

    Retorna:
        O elemento criado, ou None se o texto estava vazio.
    """
    val = str(text).strip() if text is not None else ""
    if not val:
        return None  # não cria o elemento
    el = ET.SubElement(parent, _q(tag))
    el.text = val
    return el


def emit_roles(parent: ET.Element, tag: str, values) -> None:
    """
    Emite múltiplos elementos <tag> a partir de um valor que pode conter
    vários itens separados por pipe (" | ").

    Exemplo:
        emit_roles(el, 'linkingAgentRole', 'executor | validator')
        → cria <linkingAgentRole>executor</linkingAgentRole>
               <linkingAgentRole>validator</linkingAgentRole>

    Parâmetros:
        parent — elemento pai
        tag    — nome do elemento a ser emitido
        values — string com um ou mais valores separados por " | "
    """
    for piece in split_pipe(values):
        add_text(parent, tag, piece)


def first_nonempty(*values, default: str = "") -> str:
    """
    Retorna o primeiro valor não-vazio (após strip()) dentre os argumentos.
    Se todos forem vazios ou None, retorna 'default' (padrão: "").

    Útil quando há múltiplas fontes possíveis para um mesmo campo.

    Exemplo:
        first_nonempty("", None, "PDF") → "PDF"
        first_nonempty("", None, "")    → ""
    """
    for v in values:
        s = "" if v is None else str(v).strip()
        if s:
            return s
    return default


# =============================================================================
# Coleta e transformação de pares (header, value) do CSV
# =============================================================================

def split_pipe(s) -> list[str]:
    """
    Divide uma string em partes separadas pelo delimitador " | " (pipe).
    Remove espaços extras e ignora partes vazias.

    Usado para "explodir" valores múltiplos que foram acumulados em uma
    única célula do CSV ou em um único campo de bloco.

    Exemplos:
        split_pipe("executor | validator")   → ["executor", "validator"]
        split_pipe("único valor")            → ["único valor"]
        split_pipe("")                       → []
        split_pipe(None)                     → []
    """
    return [p.strip() for p in str(s or "").split("|") if str(p).strip()]


def collect_multival(pairs: list[tuple[str, str]], key: str) -> list[str]:
    """
    Coleta todos os valores não-vazios de um determinado campo ('key')
    em uma linha do CSV, preservando a ordem de aparição.

    No CSV, um campo repetível pode aparecer em múltiplas colunas com o
    mesmo nome. Esta função retorna todos esses valores como lista.

    Exemplo de CSV com coluna repetida:
        ag.agentName | ag.agentName
        "Ana"        | "Ana Souza"
        → collect_multival(pairs, 'ag.agentName') → ["Ana", "Ana Souza"]

    Parâmetros:
        pairs — lista de tuplas (cabeçalho, valor) da linha
        key   — nome da coluna a coletar

    Retorna:
        Lista de strings com os valores encontrados (sem vazios).
    """
    out = []
    for k, v in pairs:
        if k == key:
            val = str(v).strip()
            if val:
                out.append(val)
    return out


# =============================================================================
# Coletor de blocos repetíveis
# =============================================================================

def collect_blocks(
    pairs: list[tuple[str, str]],
    fields: list[str],
    accumulate_keys: set[str] | None = None,
    accumulate_last: bool | None = None,
    need_keys: list[str] | None = None,
    accept_if_any: bool = True,
) -> list[dict[str, str]]:
    """
    Agrupa os pares (cabeçalho, valor) do CSV em "blocos" de campos
    relacionados, permitindo tratar grupos de colunas como unidades repetíveis.

    Por que isso é necessário?
    --------------------------
    No PREMIS, muitos elementos são compostos e repetíveis. Por exemplo,
    um objeto pode ter múltiplos <objectIdentifier>, cada um com um par
    (Type, Value). No CSV, isso é representado por colunas repetidas:

        ob.objectIdentifierType | ob.objectIdentifierValue | ob.objectIdentifierType | ob.objectIdentifierValue
        "UUID"                  | "abc-123"               | "local"                 | "doc-001"

    collect_blocks() percorre esses pares e agrupa em blocos:
        [
          {'ob.objectIdentifierType': 'UUID',  'ob.objectIdentifierValue': 'abc-123'},
          {'ob.objectIdentifierType': 'local', 'ob.objectIdentifierValue': 'doc-001'},
        ]

    Regras de segmentação de blocos:
    ---------------------------------
    Um novo bloco começa quando o PRIMEIRO campo de 'fields' reaparece E
    o bloco atual já é considerado "aceitável" (tem ao menos um valor).

    Regras de aceitação de bloco:
    ------------------------------
    - Se 'need_keys' fornecido: todos esses campos devem estar preenchidos.
    - Se 'accept_if_any=True' (padrão): basta qualquer campo preenchido.
    - Se 'accept_if_any=False' (legado): exige os 2 primeiros campos.

    Acúmulo de valores (campos repetíveis dentro do mesmo bloco):
    -------------------------------------------------------------
    Campos listados em 'accumulate_keys' acumulam valores com " | " em vez
    de sobrescrever. Exemplo: notes "nota1" + "nota2" → "nota1 | nota2".

    Parâmetro de compatibilidade:
    -----------------------------
    'accumulate_last=True' é equivalente a accumulate_keys={fields[-1]}.
    Mantido para não quebrar código mais antigo.

    Parâmetros:
        pairs           — lista de tuplas (cabeçalho, valor) da linha do CSV
        fields          — lista de campos que formam um bloco
        accumulate_keys — conjunto de campos que acumulam valores (pipe)
        accumulate_last — atalho: acumula o último campo de 'fields'
        need_keys       — campos que devem estar preenchidos para aceitar o bloco
        accept_if_any   — True = aceita bloco com qualquer campo preenchido

    Retorna:
        Lista de dicionários; cada dicionário é um bloco com todas as chaves
        de 'fields' (vazias como "" quando ausentes).
    """

    # Compatibilidade: converte accumulate_last para accumulate_keys
    if accumulate_keys is None and accumulate_last:
        accumulate_keys = {fields[-1]}
    if accumulate_keys is None:
        accumulate_keys = set()

    def block_has_any(d: dict[str, str]) -> bool:
        """Verifica se o bloco tem ao menos um campo preenchido."""
        return any(str(d.get(k, "")).strip() for k in fields)

    def block_is_complete(d: dict[str, str]) -> bool:
        """
        Decide se o bloco atual é válido (deve ser emitido no XML).
        Aplica as regras de aceitação definidas nos parâmetros.
        """
        if need_keys:
            # Modo estrito: todos os campos obrigatórios devem estar preenchidos
            return all(str(d.get(k, "")).strip() for k in need_keys)
        if accept_if_any:
            # Modo padrão: basta qualquer campo ter valor
            return block_has_any(d)
        # Modo legado: exige pelo menos os dois primeiros campos
        req = fields[:2]
        return all(str(d.get(k, "")).strip() for k in req)

    out: list[dict[str, str]] = []
    cur = {f: "" for f in fields}  # bloco atual (começa vazio)

    def flush_if_needed():
        """Fecha o bloco atual (se válido) e inicia um novo bloco vazio."""
        nonlocal cur
        if block_is_complete(cur):
            out.append(cur)
        cur = {f: "" for f in fields}

    for k, v in pairs:
        # Ignora colunas que não pertencem a este bloco
        if k not in fields:
            continue

        val = str(v).strip()

        # Se o primeiro campo reaparece e o bloco atual é válido → fecha bloco
        if k == fields[0] and block_is_complete(cur):
            flush_if_needed()

        # Ignora valores vazios (não poluem o bloco)
        if not val:
            continue

        # Campos acumuláveis: concatena com pipe em vez de sobrescrever
        if k in accumulate_keys:
            cur[k] = (cur[k] + " | " + val) if cur[k] else val
        else:
            cur[k] = val  # campos normais: sobrescreve

    # Fecha o último bloco após percorrer todos os pares
    if block_is_complete(cur):
        out.append(cur)

    return out


# =============================================================================
# Normalização de datas e horas
# =============================================================================

# Expressão regular para detectar strings já no formato ISO 8601
_ISO_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}(T|\s)\d{2}:\d{2}(:\d{2})?([+-]\d{2}:\d{2}|Z|[+-]\d{2})?$"
)

# Expressão regular para detectar apenas a data (sem hora)
_DATE_ONLY_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def normalize_dt(value: str) -> str:
    """
    Normaliza uma string de data/hora para o formato ISO 8601, quando possível.

    O PREMIS exige datas no formato ISO 8601. Esta função tenta converter
    formatos comuns usados em planilhas brasileiras para ISO, sem forçar
    conversões que possam distorcer o dado original.

    Comportamento:
      - Já está em ISO (ex.: "2024-10-02T11:01:14-03:00") → retorna como veio.
      - ISO com espaço (ex.: "2024-10-02 11:01:14") → troca espaço por 'T'.
      - Apenas data (ex.: "2024-10-02") → retorna como veio.
      - Formatos comuns de planilha (dd/mm/aaaa hh:mm:ss) → converte para ISO.
      - Formato não reconhecido → retorna o texto original sem alterar.

    Parâmetros:
        value — string com a data/hora a normalizar

    Retorna:
        String normalizada, ou o valor original se não for possível converter.
    """
    if value is None:
        return ""
    s = str(value).strip()
    if not s:
        return ""

    # Caso 1: já parece ISO (com ou sem separador T/espaço)
    if _ISO_RE.match(s):
        return s.replace(" ", "T")  # garante 'T' como separador

    # Caso 2: apenas data YYYY-MM-DD
    if _DATE_ONLY_RE.match(s):
        return s

    # Caso 3: tenta converter formatos comuns de planilha para ISO
    for fmt in (
        "%Y-%m-%d %H:%M:%S",   # 2024-10-02 11:01:14
        "%Y-%m-%d %H:%M",      # 2024-10-02 11:01
        "%d/%m/%Y %H:%M:%S",   # 02/10/2024 11:01:14
        "%d/%m/%Y %H:%M",      # 02/10/2024 11:01
    ):
        try:
            dt = datetime.strptime(s, fmt)
            return dt.strftime("%Y-%m-%dT%H:%M:%S")
        except Exception:
            pass  # tenta o próximo formato

    # Caso 4: formato não reconhecido → retorna original sem alterar
    return s
