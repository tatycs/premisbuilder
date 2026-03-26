# premis_builder_pkg/premis_builder/cli.py
# -----------------------------------------------------------------------------
# Ponto de entrada (linha de comando) para gerar PREMIS 3.0 a partir de um CSV.
# Funções-chave:
#  - Leitura robusta do CSV (detecção de delimitador, remoção de BOM, strip).
#  - Roteamento por entidade (object/event/agent/rights) com filtros mínimos
#    para não criar elementos "fantasmas" (vazios).
#  - Escrita do XML com indentação (pretty print).
#
# Uso:
#   python premis_builder_cli.py <entrada.csv> <saida.xml>
# -----------------------------------------------------------------------------

import csv
import sys
import xml.etree.ElementTree as ET
from xml.dom import minidom

from .utils import NS
from .object_builder import build_object
from .event_builder import build_event
from .agent_builder import build_agent
from .rights_builder import build_rights


# -----------------------------------------------------------------------------
# Escrita "pretty" do XML (tenta ET.indent; se faltar, usa minidom)
# -----------------------------------------------------------------------------
def write_pretty_xml(root_el: ET.Element, out_path: str):
    """
    Grava o XML com indentação legível.
    - Em Python 3.9+: usa ET.indent().
    - Caso contrário, recorre ao minidom.toprettyxml().
    """
    try:
        tree = ET.ElementTree(root_el)
        # Disponível em Python 3.9+
        ET.indent(tree, space="  ", level=0)
        tree.write(out_path, encoding="utf-8", xml_declaration=True)
    except AttributeError:
        rough = ET.tostring(root_el, encoding="utf-8")
        pretty = minidom.parseString(rough).toprettyxml(indent="  ", encoding="utf-8")
        with open(out_path, "wb") as f:
            f.write(pretty)


# -----------------------------------------------------------------------------
# Leitura robusta do CSV
# -----------------------------------------------------------------------------
def _read_rows(path):
    """
    Lê o CSV:
      - Detecta delimitador com csv.Sniffer (fallback: vírgula).
      - Remove BOM (utf-8-sig).
      - Normaliza espaços em headers/valores.
      - Garante que cada linha tenha o mesmo número de colunas que o cabeçalho.

    Retorna:
      (headers: list[str], rows: list[list[(header, value)]])
    """
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        sample = f.read(2048)
        f.seek(0)
        try:
            dialect = csv.Sniffer().sniff(sample)
        except Exception:
            dialect = csv.excel  # fallback: vírgula
        reader = csv.reader(f, dialect)
        rows = list(reader)

    if not rows:
        return [], []

    # Normaliza cabeçalhos (strip + remove BOM residual)
    headers = [str(h).strip().lstrip("\ufeff") for h in rows[0]]
    data = rows[1:]

    norm = []
    for r in data:
        # Equaliza comprimento ao dos headers
        if len(r) < len(headers):
            r = r + [""] * (len(headers) - len(r))
        elif len(r) > len(headers):
            r = r[:len(headers)]
        # Strip por célula
        r = [str(v).strip() for v in r]
        pairs = list(zip(headers, r))
        norm.append(pairs)

    return headers, norm


# -----------------------------------------------------------------------------
# Predicados mínimos por entidade (evitam gerar elementos "vazios")
# -----------------------------------------------------------------------------
def _any_filled(pairs, prefix: str) -> bool:
    """Há algum campo com nome começando por 'prefix' com valor não-vazio?"""
    return any(k.startswith(prefix) and str(v).strip() for k, v in pairs)

def _has_min_object(pairs) -> bool:
    """
    Critério mínimo para construir <object>:
      - preferencial: ob.objectIdentifierType + ob.objectIdentifierValue
      - (facultativo) ob.xsi_type ou ob.objectCategory podem existir, mas não são obrigatórios
      - alternativa: qualquer ob.* preenchido (para casos muito parciais)
    """
    has_type  = any(k == "ob.objectIdentifierType"  and str(v).strip() for k, v in pairs)
    has_value = any(k == "ob.objectIdentifierValue" and str(v).strip() for k, v in pairs)
    return (has_type and has_value) or _any_filled(pairs, "ob.")

def _has_min_event(pairs) -> bool:
    """
    Critério mínimo para construir <event>:
      - preferencial: ev.eventIdentifierType + ev.eventIdentifierValue
      - alternativa: qualquer ev.* preenchido
    """
    has_type  = any(k == "ev.eventIdentifierType"  and str(v).strip() for k, v in pairs)
    has_value = any(k == "ev.eventIdentifierValue" and str(v).strip() for k, v in pairs)
    return (has_type and has_value) or _any_filled(pairs, "ev.")

def _has_min_agent(pairs) -> bool:
    """
    Critério mínimo para construir <agent>:
      - preferencial: ag.agentIdentifierType + ag.agentIdentifierValue
      - alternativa: qualquer ag.* preenchido
    """
    has_type  = any(k == "ag.agentIdentifierType"  and str(v).strip() for k, v in pairs)
    has_value = any(k == "ag.agentIdentifierValue" and str(v).strip() for k, v in pairs)
    return (has_type and has_value) or _any_filled(pairs, "ag.")

def _has_min_rights(pairs) -> bool:
    """
    Critério mínimo para construir <rights> (rightsStatement):
      - preferencial: rt.rightsStatementIdentifierType + rt.rightsStatementIdentifierValue
      - alternativa: qualquer rt.* preenchido
    """
    has_type  = any(k == "rt.rightsStatementIdentifierType"  and str(v).strip() for k, v in pairs)
    has_value = any(k == "rt.rightsStatementIdentifierValue" and str(v).strip() for k, v in pairs)
    return (has_type and has_value) or _any_filled(pairs, "rt.")


# -----------------------------------------------------------------------------
# main(): orquestra a leitura, construção e escrita do XML
# -----------------------------------------------------------------------------
def main():
    if len(sys.argv) < 3:
        print("Uso: premis_builder_cli.py <entrada.csv> <saida.xml>")
        sys.exit(1)

    in_csv = sys.argv[1]
    out_xml = sys.argv[2]

    # Registra prefixos de namespace explícitos (premis, xlink, xsi)
    ET.register_namespace("premis", NS["premis"])
    ET.register_namespace("xlink", NS["xlink"])
    ET.register_namespace("xsi", NS["xsi"])

    # Cria a raiz PREMIS com prefixo e atributos recomendados (versão 3.0)
    premis_root = ET.Element(f"{{{NS['premis']}}}premis", {
        "version": "3.0",
        f"{{{NS['xsi']}}}schemaLocation": (
            f"{NS['premis']} https://www.loc.gov/standards/premis/premis.xsd"
        ),
    })

    headers, rows = _read_rows(in_csv)
    if not rows:
        # Grava pelo menos o <premis/> vazio
        write_pretty_xml(premis_root, out_xml)
        return

    for pairs in rows:
        # Pula linhas totalmente vazias
        if not any(v for _, v in pairs):
            continue

        # Descobre a entidade (default: object)
        d = {str(k).strip(): v for k, v in pairs}
        entity = str(d.get("entity", "object")).strip().lower()

        if entity == "object":
            if _has_min_object(pairs):
                build_object(premis_root, pairs)

        elif entity == "event":
            if _has_min_event(pairs):
                build_event(premis_root, pairs)

        elif entity == "agent":
            if _has_min_agent(pairs):
                build_agent(premis_root, pairs)

        elif entity == "rights":
            if _has_min_rights(pairs):
                build_rights(premis_root, pairs)

        else:
            # Entidade desconhecida: trate como object se houver dados mínimos
            if _has_min_object(pairs):
                build_object(premis_root, pairs)

    # Escrita indentada do XML
    write_pretty_xml(premis_root, out_xml)


if __name__ == "__main__":
    main()
