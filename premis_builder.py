#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
premis_builder.py

✅ Suporte explícito a colunas REPETIDAS com o MESMO NOME (sem .1/.2):
- Lê CSV com csv.reader para preservar nomes duplicados.
- Em EVENTOS, varre da esquerda p/ direita e instancia 0..N containers:
  * linkingAgentIdentifier: (Type, Value, Role) em sequência repetida
  * linkingObjectIdentifier: (Type, Value, Role) em sequência repetida (Role opcional)
- Emite cada container quando houver os mínimos obrigatórios (Type+Value).
- Mantém demais campos (eventDetail*, eventOutcome*, etc.) pegando o PRIMEIRO valor não-vazio.
- Em OBJETO, mantém objectCharacteristics (fixity/size/format/creatingApplication),
  relationship (inclui relatedObjectIdentifier e relatedEventIdentifier) e linkingEventIdentifier.
- Não força "local" para tipos.

Observação: Para objetos e direitos/agentes, ainda usamos mapeamento por chave única
(a maioria dos seus campos não se repete com nomes idênticos). Se você
repetir exatamente os mesmos nomes também nesses blocos, posso estender o mesmo
scanner por sequência para eles.
"""

import sys, csv, re
import xml.etree.ElementTree as ET
from datetime import datetime

NS = {'premis': 'http://www.loc.gov/premis/v3'}
ET.register_namespace('', NS['premis'])
EXT_NS_PREFIX = 'ext-edocs'

# ---------------- utils ----------------

def add_text(parent, tag, text):
    if text is None:
        return None
    s = str(text).strip()
    if not s:
        return None
    el = ET.SubElement(parent, f'{{{NS["premis"]}}}{tag}')
    el.text = s
    return el

def normalize_datetime(s):
    s = (s or '').strip()
    if not s:
        return ''
    if re.match(r'^\d{4}-\d{2}-\d{2}T', s):
        return s
    if re.search(r'[+-]\d{2}:\d{2}$', s):
        return s
    for fmt in ('%d/%m/%Y %H:%M:%S','%d/%m/%Y %H:%M','%Y-%m-%d %H:%M:%S','%Y-%m-%d %H:%M','%d/%m/%Y'):
        try:
            dt = datetime.strptime(s, fmt)
            if fmt == '%d/%m/%Y':
                dt = dt.replace(hour=0, minute=0, second=0)
            return dt.strftime('%Y-%m-%dT%H:%M:%S')
        except Exception:
            continue
    return s

def first_nonempty(pairs, key_name):
    """Retorna o primeiro valor não-vazio para 'key_name' escaneando à esquerda."""
    for k, v in pairs:
        if k == key_name and str(v).strip():
            return str(v).strip()
    return ""

def collect_repeating_triplets(pairs, t_key, v_key, r_key=None):
    """
    Varre a sequência (pairs = [(colname, value), ...]) e coleta containers repetidos:
    - Se r_key for None: (Type, Value) obrigatórios, sem role
    - Se r_key existir: (Type, Value) obrigatórios e Role opcional
    Assume que as colunas se repetem no mesmo padrão de nomes (sem .1/.2), p.ex.:
      t_key, v_key, r_key, t_key, v_key, r_key, ...
    """
    items = []
    cur_t, cur_v, cur_r = "", "", ""
    needed = {t_key, v_key} | ({r_key} if r_key else set())

    for k, v in pairs:
        if k not in (t_key, v_key) and (r_key is None or k != r_key):
            continue
        val = str(v).strip()

        if k == t_key:
            # Se já temos Type+Value (um container completo), emite e inicia novo
            if cur_t and cur_v:
                items.append((cur_t, cur_v, cur_r))
                cur_t, cur_v, cur_r = "", "", ""
            cur_t = val or cur_t  # respeita valores não-vazios
        elif k == v_key:
            if cur_t and cur_v and (cur_r or r_key is None):
                # começa um novo container se o atual já estava completo e este 'Value' provavelmente é do próximo
                items.append((cur_t, cur_v, cur_r))
                cur_t, cur_v, cur_r = "", "", ""
            cur_v = val or cur_v
        elif r_key and k == r_key:
            cur_r = val or cur_r

    # Flush final
    if cur_t and cur_v:
        items.append((cur_t, cur_v, cur_r))

    # Remove entradas vazias/duplicadas preservando ordem
    seen = set()
    out = []
    for t, v, r in items:
        key = (t, v, r) if r_key else (t, v)
        if key in seen:
            continue
        seen.add(key)
        out.append((t, v, r))
    return out

# --------------- builders ---------------

def build_event(premis_root, pairs):
    ev = ET.SubElement(premis_root, f'{{{NS["premis"]}}}event')

    add_text(ev, 'eventIdentifierType', first_nonempty(pairs, 'ev.eventIdentifierType'))
    add_text(ev, 'eventIdentifierValue', first_nonempty(pairs, 'ev.eventIdentifierValue'))
    add_text(ev, 'eventType', first_nonempty(pairs, 'ev.eventType'))
    add_text(ev, 'eventDateTime', normalize_datetime(first_nonempty(pairs, 'ev.eventDateTime')))

    # eventDetailInformation (detail + extensions)
    detail = first_nonempty(pairs, 'ev.eventDetail')
    if detail or first_nonempty(pairs, 'ev.eventDetailExtension'):
        edi = None
        if detail:
            add_text(ev, 'eventDetail', detail)  # PREMIS 3: eventDetail é direto (não container) no schema XML, mas DD mostra sob eventDetailInformation
        ext = [v for k, v in pairs if k == 'ev.eventDetailExtension' and str(v).strip()]
        if ext:
            # Representamos extensões em <extension>
            ext_el = ev.find(f'{{{NS["premis"]}}}extension')
            if ext_el is None:
                ext_el = ET.SubElement(ev, f'{{{NS["premis"]}}}extension')
            for e in ext:
                el = ET.SubElement(ext_el, f'{EXT_NS_PREFIX}.eventDetailExtension')
                el.text = str(e).strip()

    # eventOutcomeInformation (0..n) – aqui simplificamos para 1 outcome + extensões detalhadas
    outcome = first_nonempty(pairs, 'ev.eventOutcome')
    if outcome or first_nonempty(pairs, 'ev.eventOutcomeDetailNote') or first_nonempty(pairs, 'ev.eventOutcomeDetailExtension'):
        eoi = ET.SubElement(ev, f'{{{NS["premis"]}}}eventOutcomeInformation')
        add_text(eoi, 'eventOutcome', outcome)
        note = first_nonempty(pairs, 'ev.eventOutcomeDetailNote')
        ext2 = [v for k, v in pairs if k == 'ev.eventOutcomeDetailExtension' and str(v).strip()]
        if note or ext2:
            eod = ET.SubElement(eoi, f'{{{NS["premis"]}}}eventOutcomeDetail')
            add_text(eod, 'eventOutcomeDetailNote', note)
            for e in ext2:
                edx = ET.SubElement(eod, f'{{{NS["premis"]}}}eventOutcomeDetailExtension')
                edx.text = str(e).strip()

    # linkingAgentIdentifier (O, R): repetir sequências Type/Value/Role
    agents = collect_repeating_triplets(
        pairs,
        'ev.linkingAgentIdentifierType',
        'ev.linkingAgentIdentifierValue',
        'ev.linkingAgentRole'
    )
    for typ, valv, role in agents:
        lai = ET.SubElement(ev, f'{{{NS["premis"]}}}linkingAgentIdentifier')
        add_text(lai, 'linkingAgentIdentifierType', typ)
        add_text(lai, 'linkingAgentIdentifierValue', valv)
        add_text(lai, 'linkingAgentRole', role)

    # linkingObjectIdentifier (O, R): repetir sequências Type/Value/Role (role opcional)
    objs = collect_repeating_triplets(
        pairs,
        'ev.linkingObjectIdentifierType',
        'ev.linkingObjectIdentifierValue',
        'ev.linkingObjectIdentifierRole'
    )
    for typ, valv, role in objs:
        loi = ET.SubElement(ev, f'{{{NS["premis"]}}}linkingObjectIdentifier')
        add_text(loi, 'linkingObjectIdentifierType', typ)
        add_text(loi, 'linkingObjectIdentifierValue', valv)
        # PREMIS tem linkingObjectRole (opcional); só emite se veio:
        if role:
            add_text(loi, 'linkingObjectRole', role)

    return ev

def build_object(premis_root, pairs):
    # Para objetos, usamos first_nonempty para chaves únicas
    def f(key): return first_nonempty(pairs, key)

    obj = ET.SubElement(premis_root, f'{{{NS["premis"]}}}object')
    add_text(obj, 'objectIdentifierType', f('ob.objectIdentifierType'))
    add_text(obj, 'objectIdentifierValue', f('ob.objectIdentifierValue'))
    add_text(obj, 'objectCategory', f('ob.objectCategory'))
    add_text(obj, 'originalName', f('ob.originalName'))

    # objectCharacteristics
    oc = ET.SubElement(obj, f'{{{NS["premis"]}}}objectCharacteristics')
    alg = f('ob.messageDigestAlgorithm') or f('ob.objectCharacteristics.fixity.messageDigestAlgorithm')
    dig = f('ob.messageDigest') or f('ob.objectCharacteristics.fixity.messageDigest')
    org = f('ob.messageDigestOriginator') or f('ob.objectCharacteristics.fixity.messageDigestOriginator')
    if alg and dig:
        fx = ET.SubElement(oc, f'{{{NS["premis"]}}}fixity')
        add_text(fx, 'messageDigestAlgorithm', alg)
        add_text(fx, 'messageDigest', dig)
        add_text(fx, 'messageDigestOriginator', org)
    size = f('ob.objectCharacteristics.size') or f('ob.size')
    add_text(oc, 'size', size)

    # format
    fmt_name = f('ob.format.formatDesignation.formatName')
    fmt_ver  = f('ob.format.formatDesignation.formatVersion')
    if fmt_name or fmt_ver:
        fmt = ET.SubElement(oc, f'{{{NS["premis"]}}}format')
        fd  = ET.SubElement(fmt, f'{{{NS["premis"]}}}formatDesignation')
        add_text(fd, 'formatName', fmt_name)
        add_text(fd, 'formatVersion', fmt_ver)
        reg_name = f('ob.format.formatRegistry.formatRegistryName')
        reg_key  = f('ob.format.formatRegistry.formatRegistryKey')
        reg_role = f('ob.format.formatRegistry.formatRegistryRole')
        if reg_name or reg_key or reg_role:
            fr = ET.SubElement(fmt, f'{{{NS["premis"]}}}formatRegistry')
            add_text(fr, 'formatRegistryName', reg_name)
            add_text(fr, 'formatRegistryKey', reg_key)
            add_text(fr, 'formatRegistryRole', reg_role)

    # creatingApplication
    ca_name = f('ob.creatingApplication.creatingApplicationName')
    ca_ver  = f('ob.creatingApplication.creatingApplicationVersion')
    ca_date = normalize_datetime(f('ob.creatingApplication.dateCreatedByApplication'))
    ca_ext  = f('ob.creatingApplication.creatingApplicationExtension')
    if ca_name or ca_ver or ca_date or ca_ext:
        ca = ET.SubElement(oc, f'{{{NS["premis"]}}}creatingApplication')
        add_text(ca, 'creatingApplicationName', ca_name)
        add_text(ca, 'creatingApplicationVersion', ca_ver)
        add_text(ca, 'dateCreatedByApplication', ca_date)
        add_text(ca, 'creatingApplicationExtension', ca_ext)

    # relationship (1 por linha)
    rel_type = f('ob.relationship.relationshipType') or f('ob.relationshipType')
    rel_sub  = f('ob.relationship.relationshipSubType') or f('ob.relationshipSubType')
    if rel_type or rel_sub:
        rel = ET.SubElement(obj, f'{{{NS["premis"]}}}relationship')
        add_text(rel, 'relationshipType', rel_type)
        add_text(rel, 'relationshipSubType', rel_sub)

        # relatedObjectIdentifier (base + sufixos se houver)
        ro_t = f('ob.relationship.relatedObjectIdentifier.relatedObjectIdentifierType') or f('ob.relatedObjectIdentifierType')
        ro_v = f('ob.relationship.relatedObjectIdentifier.relatedObjectIdentifierValue') or f('ob.relatedObjectIdentifierValue')
        ro_s = f('ob.relationship.relatedObjectIdentifier.relatedObjectSequence') or f('ob.relatedObjectSequence')
        if ro_t and ro_v:
            ro = ET.SubElement(rel, f'{{{NS["premis"]}}}relatedObjectIdentifier')
            add_text(ro, 'relatedObjectIdentifierType', ro_t)
            add_text(ro, 'relatedObjectIdentifierValue', ro_v)
            add_text(ro, 'relatedObjectSequence', ro_s)

        # relatedEventIdentifier (base)
        re_t = f('ob.relationship.relatedEventIdentifier.relatedEventIdentifierType') or f('ob.relatedEventIdentifierType')
        re_v = f('ob.relationship.relatedEventIdentifier.relatedEventIdentifierValue') or f('ob.relatedEventIdentifierValue')
        re_s = f('ob.relationship.relatedEventIdentifier.relatedEventSequence') or f('ob.relatedEventSequence')
        if re_t and re_v:
            rei = ET.SubElement(rel, f'{{{NS["premis"]}}}relatedEventIdentifier')
            add_text(rei, 'relatedEventIdentifierType', re_t)
            add_text(rei, 'relatedEventIdentifierValue', re_v)
            add_text(rei, 'relatedEventSequence', re_s)

    # linkingEventIdentifier (0..n) – aqui tratamos base única; se você repetir nomes idênticos, posso estender o scanner
    let = f('ob.linkingEventIdentifierType') or f('ob.linkingEventIdentifier.linkingEventIdentifierType')
    lev = f('ob.linkingEventIdentifierValue') or f('ob.linkingEventIdentifier.linkingEventIdentifierValue')
    if let and lev:
        lei = ET.SubElement(obj, f'{{{NS["premis"]}}}linkingEventIdentifier')
        add_text(lei, 'linkingEventIdentifierType', let)
        add_text(lei, 'linkingEventIdentifierValue', lev)

    # extensões ob.ext.* e ob.ext-edocs.*  (primeiro valor encontrado de cada chave)
    for k, v in pairs:
        if not str(v).strip():
            continue
        if k.startswith('ob.ext.') or k.startswith('ob.ext-edocs.'):
            ext = obj.find(f'{{{NS["premis"]}}}extension')
            if ext is None:
                ext = ET.SubElement(obj, f'{{{NS["premis"]}}}extension')
            el = ET.SubElement(ext, f'{EXT_NS_PREFIX}.{k.split(".",1)[1]}')
            el.text = str(v).strip()

    return obj

def build_agent(premis_root, pairs):
    def f(key): return first_nonempty(pairs, key)
    ag = ET.SubElement(premis_root, f'{{{NS["premis"]}}}agent')
    add_text(ag, 'agentIdentifierType', f('ag.agentIdentifierType'))
    add_text(ag, 'agentIdentifierValue', f('ag.agentIdentifierValue'))
    add_text(ag, 'agentName', f('ag.agentName'))
    add_text(ag, 'agentType', f('ag.agentType'))
    return ag

def build_rights(premis_root, pairs):
    def f(key): return first_nonempty(pairs, key)
    rt = ET.SubElement(premis_root, f'{{{NS["premis"]}}}rights')
    rsi = ET.SubElement(rt, f'{{{NS["premis"]}}}rightsStatementIdentifier')
    add_text(rsi, 'rightsStatementIdentifierType', f('rt.rightsStatementIdentifierType'))
    add_text(rsi, 'rightsStatementIdentifierValue', f('rt.rightsStatementIdentifierValue'))
    add_text(rt, 'rightsBasis', f('rt.rightsBasis'))
    act = f('rt.act'); restr = f('rt.restriction')
    if act or restr:
        rg = ET.SubElement(rt, f'{{{NS["premis"]}}}rightsGranted')
        add_text(rg, 'act', act); add_text(rg, 'restriction', restr)
    lo_t = f('rt.linkingObjectIdentifierType'); lo_v = f('rt.linkingObjectIdentifierValue')
    if lo_t and lo_v:
        loi = ET.SubElement(rt, f'{{{NS["premis"]}}}linkingObjectIdentifier')
        add_text(loi, 'linkingObjectIdentifierType', lo_t)
        add_text(loi, 'linkingObjectIdentifierValue', lo_v)
    return rt

# --------------- main ---------------

def main():
    if len(sys.argv) < 3:
        print("Uso: python premis_builder_v2.8.py input.csv output.xml")
        sys.exit(1)

    csv_path = sys.argv[1]
    out_xml  = sys.argv[2]

    with open(csv_path, 'r', encoding='utf-8', newline='') as f:
        reader = csv.reader(f)
        headers = next(reader)

        premis = ET.Element(f'{{{NS["premis"]}}}premis')

        for row in reader:
            # pairs preserva todas as colunas, inclusive nomes repetidos
            pairs = list(zip(headers, row))
            entity = first_nonempty(pairs, 'entity').lower()

            if entity == 'event':
                build_event(premis, pairs)
            elif entity == 'object':
                build_object(premis, pairs)
            elif entity == 'agent':
                build_agent(premis, pairs)
            elif entity == 'rights':
                build_rights(premis, pairs)
            else:
                # ignora linhas sem entity conhecida
                continue

    tree = ET.ElementTree(premis)
    try:
        ET.indent(tree, space="  ", level=0)
    except Exception:
        pass
    tree.write(out_xml, encoding='utf-8', xml_declaration=True)

if __name__ == '__main__':
    main()
