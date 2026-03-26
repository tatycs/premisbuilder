from .utils import add, add_text, collect_blocks, collect_multival, emit_roles, normalize_dt, NS, EXT_NS_PREFIX
import xml.etree.ElementTree as ET

# event_builder.py
# -----------------------------------------------------------------------------
# Constrói o elemento <event> do PREMIS 3.0 a partir de uma linha do CSV.
#
# Um <event> registra uma ação que aconteceu com um ou mais objetos digitais
# durante seu ciclo de vida de preservação. Exemplos de eventos:
#   - captura (ingestion), envio, assinatura, verificação de integridade,
#     migração de formato, acesso autorizado, etc.
#
# Campos do CSV reconhecidos por este módulo (prefixo "ev."):
#   ev.eventIdentifierType / ev.eventIdentifierValue → identificador do evento
#   ev.eventType          → tipo do evento (vocabulário controlado ou livre)
#   ev.eventDateTime      → data/hora ISO 8601 do evento
#   ev.eventDetail        → descrição textual (repetível)
#   ev.eventDetailExtension → extensão da descrição (repetível)
#   ev.eventOutcome       → resultado: success | failure | etc. (repetível)
#   ev.eventOutcomeDetailNote      → nota sobre o resultado (repetível)
#   ev.eventOutcomeDetailExtension → extensão da nota (repetível)
#   ev.linkingAgentIdentifier.*    → agentes que participaram (repetível, com roles)
#   ev.linkingObjectIdentifier.*   → objetos envolvidos no evento (repetível, com roles)
# -----------------------------------------------------------------------------


def build_event(root, pairs):
    """
    Constrói um elemento <event> PREMIS 3.0 e o adiciona a 'root'.

    Parâmetros:
        root  — elemento XML pai (normalmente o <premis> raiz)
        pairs — lista de tuplas (cabeçalho, valor) de uma linha do CSV

    Retorna o elemento <event> criado.
    """

    # Cria o contêiner <event> dentro do elemento raiz
    ev = add(root, 'event')

    # -------------------------------------------------------------------------
    # 2.1 eventIdentifier (M) — Obrigatório
    # Identifica unicamente este evento. O tipo define o esquema do identificador
    # (ex.: "eventID", "UUID") e o valor é o identificador em si.
    # -------------------------------------------------------------------------
    eid = add(ev, 'eventIdentifier')
    add_text(eid, 'eventIdentifierType',
             next((v for k, v in pairs
                   if k == 'ev.eventIdentifierType' and str(v).strip()), ""))
    add_text(eid, 'eventIdentifierValue',
             next((v for k, v in pairs
                   if k == 'ev.eventIdentifierValue' and str(v).strip()), ""))

    # -------------------------------------------------------------------------
    # 2.2 eventType (M) — Obrigatório
    # Classifica o evento. Recomenda-se usar vocabulários controlados como
    # o Library of Congress Preservation Events vocabulary.
    # Exemplos: capture, ingestion, migration, fixityCheck, sign, send, etc.
    # -------------------------------------------------------------------------
    add_text(ev, 'eventType',
             next((v for k, v in pairs
                   if k == 'ev.eventType' and str(v).strip()), ""))

    # -------------------------------------------------------------------------
    # 2.3 eventDateTime (M) — Obrigatório
    # Data e hora do evento em formato ISO 8601.
    # normalize_dt() converte formatos comuns (dd/mm/aaaa, etc.) para ISO.
    # -------------------------------------------------------------------------
    add_text(ev, 'eventDateTime',
             normalize_dt(next((v for k, v in pairs
                                if k == 'ev.eventDateTime' and str(v).strip()), "")))

    # -------------------------------------------------------------------------
    # 2.4 eventDetailInformation (O, R) — Opcional e repetível
    # Agrupa a descrição detalhada do evento e suas extensões.
    # No PREMIS 3.0, eventDetail e eventDetailExtension ficam DENTRO deste
    # contêiner (mudança em relação ao PREMIS 2.x).
    # O contêiner só é criado se houver ao menos um valor preenchido.
    # -------------------------------------------------------------------------
    details = collect_multival(pairs, 'ev.eventDetail')           # descrições textuais
    exts    = collect_multival(pairs, 'ev.eventDetailExtension')  # extensões

    if details or exts:
        edi = add(ev, 'eventDetailInformation')

        # Emite um <eventDetail> para cada descrição coletada
        for d in details:
            add_text(edi, 'eventDetail', d)

        # Emite um <eventDetailExtension> para cada extensão coletada
        for x in exts:
            add_text(edi, 'eventDetailExtension', x)

    # -------------------------------------------------------------------------
    # 2.5 eventOutcomeInformation (O, R) — Opcional e repetível
    # Registra o resultado do evento e detalhes sobre ele.
    # Um evento pode ter múltiplos outcomes (ex.: sucesso parcial + falha).
    # Se não houver nenhum outcome no CSV, cria um contêiner vazio ([""])
    # para garantir a estrutura mínima do XML.
    # Notas e extensões do detalhe são anexadas apenas ao PRIMEIRO outcome
    # para evitar duplicação.
    # -------------------------------------------------------------------------
    outs  = collect_multival(pairs, 'ev.eventOutcome') or [""]  # ao menos um outcome
    notes = collect_multival(pairs, 'ev.eventOutcomeDetailNote')
    oedx  = collect_multival(pairs, 'ev.eventOutcomeDetailExtension')

    for i, o in enumerate(outs):
        eoi = add(ev, 'eventOutcomeInformation')
        add_text(eoi, 'eventOutcome', o)

        # <eventOutcomeDetail> só é criado se houver nota ou extensão
        if notes or oedx:
            eod = add(eoi, 'eventOutcomeDetail')
            # Notas e extensões são atribuídas apenas ao primeiro outcome (i == 0)
            for n in (notes if i == 0 else []):
                add_text(eod, 'eventOutcomeDetailNote', n)
            for x in (oedx if i == 0 else []):
                el = add(eod, 'eventOutcomeDetailExtension')
                el.text = x

    # -------------------------------------------------------------------------
    # 2.6 linkingAgentIdentifier (O, R) — Opcional e repetível
    # Vincula agentes que participaram deste evento.
    # O campo "role" é repetível dentro de um mesmo agente (ex.: um agente
    # pode ser simultaneamente "executor" e "validator"), por isso usamos
    # accumulate_last=True para acumular múltiplos roles separados por pipe.
    # -------------------------------------------------------------------------
    agents = collect_blocks(pairs, [
        'ev.linkingAgentIdentifierType',
        'ev.linkingAgentIdentifierValue',
        'ev.linkingAgentRole',
    ], accumulate_last=True)  # acumula roles: "executor | validator"

    for b in agents:
        lai = add(ev, 'linkingAgentIdentifier')
        add_text(lai, 'linkingAgentIdentifierType',  b['ev.linkingAgentIdentifierType'])
        add_text(lai, 'linkingAgentIdentifierValue', b['ev.linkingAgentIdentifierValue'])
        # emit_roles divide "executor | validator" em múltiplos <linkingAgentRole>
        emit_roles(lai, 'linkingAgentRole', b['ev.linkingAgentRole'])

    # -------------------------------------------------------------------------
    # 2.7 linkingObjectIdentifier (O, R) — Opcional e repetível
    # Vincula os objetos digitais envolvidos neste evento.
    # O role indica o papel do objeto (ex.: "original", "derivative", "outcome").
    # -------------------------------------------------------------------------
    lo = collect_blocks(pairs, [
        'ev.linkingObjectIdentifierType',
        'ev.linkingObjectIdentifierValue',
        'ev.linkingObjectIdentifierRole',
    ], accumulate_last=True)  # acumula roles do objeto

    for b in lo:
        loi = add(ev, 'linkingObjectIdentifier')
        add_text(loi, 'linkingObjectIdentifierType',  b['ev.linkingObjectIdentifierType'])
        add_text(loi, 'linkingObjectIdentifierValue', b['ev.linkingObjectIdentifierValue'])
        # Nota: o nome do elemento XML é "linkingObjectRole", mas a chave do CSV
        # é "ev.linkingObjectIdentifierRole" — mantemos a chave do CSV para
        # compatibilidade com planilhas já existentes.
        emit_roles(loi, 'linkingObjectRole', b['ev.linkingObjectIdentifierRole'])

    return ev
