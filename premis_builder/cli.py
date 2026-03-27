# premis_builder/cli.py
# -----------------------------------------------------------------------------
# Ponto de entrada (linha de comando) para gerar PREMIS 3.0 a partir de um CSV.
#
# Este módulo é o "maestro" do programa: ele lê o CSV, identifica que tipo de
# entidade PREMIS cada linha representa e chama o construtor correspondente.
# Ao final, grava o XML resultante com indentação legível (pretty print).
#
# Funções principais:
#   write_pretty_xml() → grava o XML indentado no disco
#   _read_rows()       → lê e normaliza o CSV de entrada
#   _has_min_*()       → verifica se uma linha tem dados suficientes para gerar
#                        um elemento PREMIS sem deixá-lo vazio
#   main()             → orquestra tudo: lê CSV → constrói XML → grava arquivo
#
# Uso na linha de comando:
#   python premis_builder_cli.py <entrada.csv> <saida.xml>
# -----------------------------------------------------------------------------

import csv
import sys
import xml.etree.ElementTree as ET
from xml.dom import minidom

# Importa os namespaces e os construtores de cada entidade PREMIS
from .utils import NS
from .object_builder import build_object
from .event_builder import build_event
from .agent_builder import build_agent
from .rights_builder import build_rights


# =============================================================================
# Escrita do XML com indentação (pretty print)
# =============================================================================

def write_pretty_xml(root_el: ET.Element, out_path: str):
    """
    Grava o XML com indentação legível no arquivo indicado por 'out_path'.

    Estratégia:
      - Python 3.9+: usa ET.indent(), que é a forma nativa e eficiente.
      - Python < 3.9: usa minidom.toprettyxml() como alternativa (mais lento,
        mas funcional em versões mais antigas).

    Parâmetros:
        root_el  — elemento raiz do XML (o <premis>)
        out_path — caminho do arquivo de saída (ex.: "saida.xml")
    """
    try:
        tree = ET.ElementTree(root_el)
        # ET.indent() disponível a partir do Python 3.9
        ET.indent(tree, space="  ", level=0)
        tree.write(out_path, encoding="utf-8", xml_declaration=True)
    except AttributeError:
        # Fallback para Python < 3.9: converte para string e usa minidom
        rough = ET.tostring(root_el, encoding="utf-8")
        pretty = minidom.parseString(rough).toprettyxml(indent="  ", encoding="utf-8")
        with open(out_path, "wb") as f:
            f.write(pretty)


# =============================================================================
# Leitura e normalização do CSV
# =============================================================================

def _read_rows(path):
    """
    Lê o arquivo CSV e retorna os dados normalizados.

    Cuidados aplicados:
      - Detecta automaticamente o delimitador (vírgula, ponto-e-vírgula, tab...)
        usando csv.Sniffer. Se a detecção falhar, usa vírgula como padrão.
      - Remove o BOM (Byte Order Mark) que editores como Excel adicionam ao
        início de arquivos UTF-8 (caractere invisível \ufeff).
      - Normaliza espaços extras em cabeçalhos e valores (str.strip()).
      - Garante que todas as linhas tenham o mesmo número de colunas que o
        cabeçalho (completa com "" ou trunca, conforme necessário).

    Retorna:
        (headers, rows) onde:
          headers — lista de strings com os nomes das colunas
          rows    — lista de linhas; cada linha é uma lista de tuplas (header, valor)
    """
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        # Lê uma amostra para detectar o delimitador do CSV
        sample = f.read(2048)
        f.seek(0)  # volta ao início do arquivo após ler a amostra
        try:
            dialect = csv.Sniffer().sniff(sample)
        except Exception:
            dialect = csv.excel  # fallback: usa vírgula como delimitador
        reader = csv.reader(f, dialect)
        rows = list(reader)

    if not rows:
        return [], []  # arquivo vazio

    # Linha 0 = cabeçalho; remove BOM residual e espaços
    headers = [str(h).strip().lstrip("\ufeff") for h in rows[0]]
    data = rows[1:]  # demais linhas são dados

    norm = []
    for r in data:
        # Equaliza o comprimento da linha ao número de colunas do cabeçalho
        if len(r) < len(headers):
            r = r + [""] * (len(headers) - len(r))   # completa com vazio
        elif len(r) > len(headers):
            r = r[:len(headers)]                       # trunca o excesso

        # Remove espaços de cada célula individualmente
        r = [str(v).strip() for v in r]

        # Transforma a linha em lista de tuplas (cabeçalho, valor)
        pairs = list(zip(headers, r))
        norm.append(pairs)

    return headers, norm


# =============================================================================
# Predicados mínimos por entidade
# (evitam criar elementos PREMIS "fantasmas" com tudo vazio)
# =============================================================================

def _any_filled(pairs, prefix: str) -> bool:
    """
    Retorna True se houver ao menos um campo cujo nome começa com 'prefix'
    e cujo valor seja não-vazio.

    Usado como critério alternativo quando os campos principais (Type+Value)
    não estão preenchidos mas outros campos da entidade estão.
    """
    return any(k.startswith(prefix) and str(v).strip() for k, v in pairs)


def _has_min_object(pairs) -> bool:
    """
    Verifica se a linha tem dados suficientes para construir um <object>.

    Critério preferencial: ter ob.objectIdentifierType E ob.objectIdentifierValue.
    Critério alternativo:  qualquer campo "ob.*" preenchido (casos parciais).
    """
    has_type  = any(k == "ob.objectIdentifierType"  and str(v).strip() for k, v in pairs)
    has_value = any(k == "ob.objectIdentifierValue" and str(v).strip() for k, v in pairs)
    return (has_type and has_value) or _any_filled(pairs, "ob.")


def _has_min_event(pairs) -> bool:
    """
    Verifica se a linha tem dados suficientes para construir um <event>.

    Critério preferencial: ter ev.eventIdentifierType E ev.eventIdentifierValue.
    Critério alternativo:  qualquer campo "ev.*" preenchido.
    """
    has_type  = any(k == "ev.eventIdentifierType"  and str(v).strip() for k, v in pairs)
    has_value = any(k == "ev.eventIdentifierValue" and str(v).strip() for k, v in pairs)
    return (has_type and has_value) or _any_filled(pairs, "ev.")


def _has_min_agent(pairs) -> bool:
    """
    Verifica se a linha tem dados suficientes para construir um <agent>.

    Critério preferencial: ter ag.agentIdentifierType E ag.agentIdentifierValue.
    Critério alternativo:  qualquer campo "ag.*" preenchido.
    """
    has_type  = any(k == "ag.agentIdentifierType"  and str(v).strip() for k, v in pairs)
    has_value = any(k == "ag.agentIdentifierValue" and str(v).strip() for k, v in pairs)
    return (has_type and has_value) or _any_filled(pairs, "ag.")


def _has_min_rights(pairs) -> bool:
    """
    Verifica se a linha tem dados suficientes para construir um <rights>.

    Critério preferencial: ter rt.rightsStatementIdentifierType E rt.rightsStatementIdentifierValue.
    Critério alternativo:  qualquer campo "rt.*" preenchido.
    """
    has_type  = any(k == "rt.rightsStatementIdentifierType"  and str(v).strip() for k, v in pairs)
    has_value = any(k == "rt.rightsStatementIdentifierValue" and str(v).strip() for k, v in pairs)
    return (has_type and has_value) or _any_filled(pairs, "rt.")


# =============================================================================
# Função principal
# =============================================================================

def main():
    """
    Função principal do programa. Executada quando o usuário chama:
        python premis_builder_cli.py entrada.csv saida.xml

    Fluxo:
      1. Valida os argumentos da linha de comando.
      2. Registra os namespaces XML (premis, xlink, xsi).
      3. Cria o elemento raiz <premis version="3.0">.
      4. Lê e normaliza o CSV.
      5. Para cada linha do CSV:
           a. Pula linhas totalmente vazias.
           b. Lê o valor da coluna "entity" para saber o tipo de entidade.
           c. Verifica se há dados mínimos para a entidade.
           d. Chama o construtor correspondente (build_object, build_event, etc.).
      6. Grava o XML com indentação no arquivo de saída.
    """

    # Verifica se o usuário passou os dois argumentos obrigatórios
    if len(sys.argv) < 3:
        print("Uso: premis_builder_cli.py <entrada.csv> <saida.xml>")
        sys.exit(1)

    in_csv  = sys.argv[1]  # arquivo CSV de entrada
    out_xml = sys.argv[2]  # arquivo XML de saída

    # Registra os prefixos de namespace para que o XML gerado use
    # "premis:", "xlink:" e "xsi:" em vez de notação Clark ({uri}tag)
    ET.register_namespace("premis", NS["premis"])
    ET.register_namespace("xlink",  NS["xlink"])
    ET.register_namespace("xsi",    NS["xsi"])

    # Cria o elemento raiz <premis> com os atributos padrão PREMIS 3.0:
    #   version="3.0" e xsi:schemaLocation apontando para o XSD oficial
    premis_root = ET.Element(f"{{{NS['premis']}}}premis", {
        "version": "3.0",
        f"{{{NS['xsi']}}}schemaLocation": (
            f"{NS['premis']} https://www.loc.gov/standards/premis/premis.xsd"
        ),
    })

    # Lê e normaliza o CSV
    headers, rows = _read_rows(in_csv)

    if not rows:
        # CSV vazio: grava apenas o <premis/> sem filhos e encerra
        write_pretty_xml(premis_root, out_xml)
        return

    # Processa cada linha do CSV
    for pairs in rows:

        # Ignora linhas onde TODOS os valores estão vazios
        if not any(v for _, v in pairs):
            continue

        # Lê o valor da coluna "entity" para determinar o tipo de entidade.
        # Se a coluna não existir ou estiver vazia, assume "object".
        d = {str(k).strip(): v for k, v in pairs}
        entity = str(d.get("entity", "object")).strip().lower()

        if entity == "object":
            # Constrói um <object> se houver dados mínimos
            if _has_min_object(pairs):
                build_object(premis_root, pairs)

        elif entity == "event":
            # Constrói um <event> se houver dados mínimos
            if _has_min_event(pairs):
                build_event(premis_root, pairs)

        elif entity == "agent":
            # Constrói um <agent> se houver dados mínimos
            if _has_min_agent(pairs):
                build_agent(premis_root, pairs)

        elif entity == "rights":
            # Constrói um <rights> se houver dados mínimos
            if _has_min_rights(pairs):
                build_rights(premis_root, pairs)

        else:
            # Entidade desconhecida: trata como <object> se houver dados mínimos
            # (comportamento de segurança para não perder dados)
            if _has_min_object(pairs):
                build_object(premis_root, pairs)

    # Grava o XML final com indentação legível
    write_pretty_xml(premis_root, out_xml)


if __name__ == "__main__":
    main()
