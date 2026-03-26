# object_builder.py
# -----------------------------------------------------------------------------
# Constrói <object> do PREMIS 3.0 a partir de uma linha do CSV (lista de pares).
# Política adotada (acordada no projeto):
# - Se QUALQUER campo de um bloco estiver preenchido, o contêiner do bloco é gerado.
# - Dentro do bloco, subcontêineres (ex.: <formatDesignation/>, <formatRegistry/>)
#   só são criados quando houver valores para seus filhos.
# - Campos repetíveis em um mesmo bloco são acumulados com " | " no coletor
#   (accumulate_keys) e "explodidos" depois (emitindo múltiplos elementos).
# - Para grupos (Type/Value/Sequence), acumulamos os três e fatiamos por " | "
#   para emitir múltiplos contêineres alinhados.
# -----------------------------------------------------------------------------

import xml.etree.ElementTree as ET
from .utils import (
    add, add_text, collect_blocks, collect_multival, emit_roles, normalize_dt,
    NS, EXT_NS_PREFIX, split_pipe
)

def build_object(root, pairs):
    """
    Constrói um <object> seguindo a hierarquia PREMIS 3.0.
    'pairs' é uma lista de (header, value) vindos do CSV para uma única linha.
    """

    # Normaliza chaves (remove espaços, garante consistência de cabeçalhos)
    pairs = [(str(k).strip(), v) for (k, v) in pairs]

    # Cria o contêiner de objeto
    obj = add(root, 'object')

    # -------------------------------------------------------------------------
    # 1.1 objectIdentifier (M, R)
    # Coletamos pares Type/Value. Se nada vier, tentamos um fallback simples.
    # -------------------------------------------------------------------------
    oids = collect_blocks(pairs, [
        'ob.objectIdentifierType',
        'ob.objectIdentifierValue',
    ])
    if not oids:
        t = next((v for k, v in pairs if k == 'ob.objectIdentifierType' and str(v).strip()), "")
        v = next((v for k, v in pairs if k == 'ob.objectIdentifierValue' and str(v).strip()), "")
        if t and v:
            oids = [{'ob.objectIdentifierType': t, 'ob.objectIdentifierValue': v}]
    for b in oids:
        oid = add(obj, 'objectIdentifier')
        add_text(oid, 'objectIdentifierType', b['ob.objectIdentifierType'])
        add_text(oid, 'objectIdentifierValue', b['ob.objectIdentifierValue'])

     # -------------------------------------------------------------------------
    # 1.2 xsi:type em função de ob.xsi_type (preferencial) ou ob.objectCategory (legado)
    # -------------------------------------------------------------------------
    # Preferência: coluna explícita ob.xsi_type no CSV
    xsi_from_csv = next(
        (v for k, v in pairs if k == 'ob.xsi_type' and str(v).strip()),
        ""
    )

    # Compatibilidade: se não houver ob.xsi_type, tentar derivar de ob.objectCategory
    if not xsi_from_csv:
        cat = next(
            (v for k, v in pairs if k == 'ob.objectCategory' and str(v).strip()),
            ""
        )
        if cat:
            cat_norm = str(cat).strip().lower().replace(" ", "").replace("_", "")
            if cat_norm == "file":
                xsi_from_csv = "premis:file"
            elif cat_norm == "representation":
                xsi_from_csv = "premis:representation"
            elif cat_norm in ("intellectualentity",):
                xsi_from_csv = "premis:intellectualEntity"

    # Normaliza e aplica xsi:type se tivermos algum valor
    if xsi_from_csv:
        xsi_norm = str(xsi_from_csv).strip()
        # Se vier só "file" ou "intellectualEntity", prefixa "premis:"
        if ":" not in xsi_norm:
            xsi_norm = f"premis:{xsi_norm}"
        obj.set(f"{{{NS['xsi']}}}type", xsi_norm)

    # -------------------------------------------------------------------------
    # 1.3 preservationLevel (O, R)
    # Rationale é repetível no mesmo preservationLevel (accumulate_keys).
    # DateAssigned é NR; normalizamos datas para ISO quando possível.
    # -------------------------------------------------------------------------
    pls = collect_blocks(
        pairs,
        [
            'ob.preservationLevelType',
            'ob.preservationLevelValue',
            'ob.preservationLevelRole',
            'ob.preservationLevelRationale',     # repetível
            'ob.preservationLevelDateAssigned',  # NR
        ],
        accumulate_keys={'ob.preservationLevelRationale'}
    )
    for b in pls:
        pl = add(obj, 'preservationLevel')
        add_text(pl, 'preservationLevelType',  b['ob.preservationLevelType'])
        add_text(pl, 'preservationLevelValue', b['ob.preservationLevelValue'])
        add_text(pl, 'preservationLevelRole',  b['ob.preservationLevelRole'])
        # Vários rationales -> múltiplos <preservationLevelRationale>
        emit_roles(pl, 'preservationLevelRationale', b['ob.preservationLevelRationale'])
        add_text(pl, 'preservationLevelDateAssigned', normalize_dt(b['ob.preservationLevelDateAssigned']))

    # -------------------------------------------------------------------------
    # 1.4 significantProperties (O, R)
    # Extensions são repetíveis dentro do mesmo bloco.
    # -------------------------------------------------------------------------
    sprops = collect_blocks(
        pairs,
        [
            'ob.significantPropertiesType',
            'ob.significantPropertiesValue',
            'ob.significantPropertiesExtension',  # repetível
        ],
        accumulate_keys={'ob.significantPropertiesExtension'}
    )
    for b in sprops:
        sp = add(obj, 'significantProperties')
        add_text(sp, 'significantPropertiesType',  b['ob.significantPropertiesType'])
        add_text(sp, 'significantPropertiesValue', b['ob.significantPropertiesValue'])
        emit_roles(sp, 'significantPropertiesExtension', b['ob.significantPropertiesExtension'])

    # -------------------------------------------------------------------------
    # 1.5 objectCharacteristics (M, R para File/Bitstream)
    # Criamos sob demanda para evitar <objectCharacteristics/> vazio em IE.
    # -------------------------------------------------------------------------
    oc = None
    def ensure_oc():
        """Cria <objectCharacteristics> apenas quando necessário."""
        nonlocal oc
        if oc is None:
            oc = add(obj, 'objectCharacteristics')

    # 1.5.1 compositionLevel (O)
    comp = next((v for k, v in pairs if k == 'ob.compositionLevel' and str(v).strip()), "")
    if comp:
        ensure_oc()
        add_text(oc, 'compositionLevel', comp)

    # 1.5.2 fixity (O, R)
    # Preferimos cabeçalhos dentro de 'ob.fixity.*'; mantemos fallback "achatado".
    fixities = collect_blocks(pairs, [
        'ob.fixity.messageDigestAlgorithm',
        'ob.fixity.messageDigest',
        'ob.fixity.messageDigestOriginator',
    ])
    if not fixities:
        fixities = collect_blocks(pairs, [
            'ob.messageDigestAlgorithm',
            'ob.messageDigest',
            'ob.messageDigestOriginator',
        ])
    for b in fixities:
        if any((b.get(k) or '').strip() for k in b):
            ensure_oc()
            fx = add(oc, 'fixity')
            add_text(fx, 'messageDigestAlgorithm', b.get('ob.fixity.messageDigestAlgorithm') or b.get('ob.messageDigestAlgorithm'))
            add_text(fx, 'messageDigest',          b.get('ob.fixity.messageDigest')         or b.get('ob.messageDigest'))
            add_text(fx, 'messageDigestOriginator',b.get('ob.fixity.messageDigestOriginator') or b.get('ob.messageDigestOriginator'))

    # 1.5.3 size (O)
    sv = next((v for k, v in pairs if k in ('ob.size', 'ob.objectCharacteristics.size') and str(v).strip()), "")
    if sv:
        ensure_oc()
        add_text(oc, 'size', sv)

    # 1.5.4 format (M, R) + formatNote (O, R)
    # CSV usa cabeçalhos "achatados": ob.formatDesignation.*, ob.formatRegistry.*, ob.formatNote
    formats = collect_blocks(
        pairs,
        [
            'ob.formatDesignation.formatName',
            'ob.formatDesignation.formatVersion',
            'ob.formatRegistry.formatRegistryName',
            'ob.formatRegistry.formatRegistryKey',
            'ob.formatRegistry.formatRegistryRole',
            'ob.formatNote',  # repetível
        ],
        accumulate_keys={'ob.formatNote'}
    )
    for b in formats or [{}]:
        # Só cria <format> se houver ao menos um valor no bloco
        if not any((b.get(k) or '').strip() for k in b):
            continue
        ensure_oc()
        fmt = add(oc, 'format')

        # <formatDesignation> apenas se name/version existirem
        has_fd = any((b.get(k) or '').strip() for k in (
            'ob.formatDesignation.formatName',
            'ob.formatDesignation.formatVersion',
        ))
        if has_fd:
            fd = add(fmt, 'formatDesignation')
            add_text(fd, 'formatName',    b.get('ob.formatDesignation.formatName'))
            add_text(fd, 'formatVersion', b.get('ob.formatDesignation.formatVersion'))

        # <formatRegistry> apenas se name/key/role existirem
        if any((b.get(k) or '').strip() for k in (
            'ob.formatRegistry.formatRegistryName',
            'ob.formatRegistry.formatRegistryKey',
            'ob.formatRegistry.formatRegistryRole',
        )):
            fr = add(fmt, 'formatRegistry')
            add_text(fr, 'formatRegistryName', b.get('ob.formatRegistry.formatRegistryName'))
            add_text(fr, 'formatRegistryKey',  b.get('ob.formatRegistry.formatRegistryKey'))
            add_text(fr, 'formatRegistryRole', b.get('ob.formatRegistry.formatRegistryRole'))

        # formatNote repetível (acumulada no coletor)
        emit_roles(fmt, 'formatNote', b.get('ob.formatNote'))

    # 1.5.5 creatingApplication (O, R) + creatingApplicationExtension (O, R)
    apps = collect_blocks(
        pairs,
        [
            'ob.creatingApplicationName',
            'ob.creatingApplicationVersion',
            'ob.dateCreatedByApplication',
            'ob.creatingApplicationExtension',  # repetível
        ],
        accumulate_keys={'ob.creatingApplicationExtension'}
    )
    for b in apps:
        ensure_oc()
        ca = add(oc, 'creatingApplication')
        add_text(ca, 'creatingApplicationName',    b['ob.creatingApplicationName'])
        add_text(ca, 'creatingApplicationVersion', b['ob.creatingApplicationVersion'])
        add_text(ca, 'dateCreatedByApplication',   normalize_dt(b['ob.dateCreatedByApplication']))
        emit_roles(ca, 'creatingApplicationExtension', b['ob.creatingApplicationExtension'])

    # 1.5.6 inhibitors (O, R) + inhibitorTarget (O, R)
    inhibs = collect_blocks(
        pairs,
        [
            'ob.inhibitors.inhibitorType',
            'ob.inhibitors.inhibitorKey',
            'ob.inhibitors.inhibitorTarget',  # repetível
        ],
        accumulate_keys={'ob.inhibitors.inhibitorTarget'}
    )
    for b in inhibs:
        ensure_oc()
        inh = add(oc, 'inhibitors')
        add_text(inh, 'inhibitorType', b['ob.inhibitors.inhibitorType'])
        emit_roles(inh, 'inhibitorTarget', b['ob.inhibitors.inhibitorTarget'])
        add_text(inh, 'inhibitorKey', b['ob.inhibitors.inhibitorKey'])

    # 1.5.7 objectCharacteristicsExtension (O, R)
    for x in collect_multival(pairs, 'ob.objectCharacteristicsExtension'):
        ensure_oc()
        add_text(oc, 'objectCharacteristicsExtension', x)

    # -------------------------------------------------------------------------
    # 1.6 originalName (O)
    # -------------------------------------------------------------------------
    add_text(obj, 'originalName', next((v for k, v in pairs if k == 'ob.originalName' and str(v).strip()), ""))

    # -------------------------------------------------------------------------
    # 1.7 storage (O, R) — contentLocation (O, NR) + storageMedium (O, NR)
    # -------------------------------------------------------------------------
    stores = collect_blocks(pairs, [
        'ob.storage.contentLocationType',
        'ob.storage.contentLocationValue',
        'ob.storage.storageMedium',
    ])
    for b in stores:
        st = add(obj, 'storage')
        cl = add(st, 'contentLocation')
        add_text(cl, 'contentLocationType',  b['ob.storage.contentLocationType'])
        add_text(cl, 'contentLocationValue', b['ob.storage.contentLocationValue'])
        add_text(st, 'storageMedium',        b['ob.storage.storageMedium'])

    # -------------------------------------------------------------------------
    # 1.8 signatureInformation (O, R) / signature (O, R) / signatureProperties (O, R)
    # -------------------------------------------------------------------------
    sigs = collect_blocks(
        pairs,
        [
            'ob.signatureEncoding',
            'ob.signer',
            'ob.signatureMethod',
            'ob.signatureValue',
            'ob.signatureValidationRules',
            'ob.signatureProperties',  # repetível
        ],
        accumulate_keys={'ob.signature.signatureProperties'}
    )
    if sigs:
        si = add(obj, 'signatureInformation')
        for b in sigs:
            sg = add(si, 'signature')
            add_text(sg, 'signatureEncoding',        b['ob.signatureEncoding'])
            add_text(sg, 'signer',                   b['ob.signer'])
            add_text(sg, 'signatureMethod',          b['ob.signatureMethod'])
            add_text(sg, 'signatureValue',           b['ob.signatureValue'])
            add_text(sg, 'signatureValidationRules', b['ob.signatureValidationRules'])
            emit_roles(sg, 'signatureProperties',    b['ob.signatureProperties'])

    # -------------------------------------------------------------------------
    # 1.9 environmentFunction (O, R)
    # -------------------------------------------------------------------------
    efuncs = collect_blocks(pairs, [
        'ob.environmentFunctionType',
        'ob.environmentFunctionLevel',
    ])
    for b in efuncs:
        ef = add(obj, 'environmentFunction')
        add_text(ef, 'environmentFunctionType',  b['ob.environmentFunctionType'])
        add_text(ef, 'environmentFunctionLevel', b['ob.environmentFunctionLevel'])

    # -------------------------------------------------------------------------
    # 1.10 environmentDesignation (O, R)
    # Notas e extensões são repetíveis no mesmo bloco.
    # -------------------------------------------------------------------------
    eds = collect_blocks(
        pairs,
        [
            'ob.environmentName',
            'ob.environmentVersion',
            'ob.environmentOrigin',
            'ob.environmentDesignationNote',       # repetível
            'ob.environmentDesignationExtension',  # repetível
        ],
        accumulate_keys={'ob.environmentDesignationNote', 'ob.environmentDesignationExtension'}
    )
    for b in eds:
        if not any((b.get(k) or '').strip() for k in b):
            continue
        ed = add(obj, 'environmentDesignation')
        add_text(ed, 'environmentName',    b['ob.environmentName'])
        add_text(ed, 'environmentVersion', b['ob.environmentVersion'])
        add_text(ed, 'environmentOrigin',  b['ob.environmentOrigin'])
        emit_roles(ed, 'environmentDesignationNote',      b['ob.environmentDesignationNote'])
        emit_roles(ed, 'environmentDesignationExtension', b['ob.environmentDesignationExtension'])

    # -------------------------------------------------------------------------
    # 1.11 environmentRegistry (O, R)
    # -------------------------------------------------------------------------
    eregs = collect_blocks(pairs, [
        'ob.environmentRegistryName',
        'ob.environmentRegistryKey',
        'ob.environmentRegistryRole',
    ])
    for b in eregs:
        if not any((b.get(k) or '').strip() for k in b):
            continue
        er = add(obj, 'environmentRegistry')
        add_text(er, 'environmentRegistryName', b['ob.environmentRegistryName'])
        add_text(er, 'environmentRegistryKey',  b['ob.environmentRegistryKey'])
        add_text(er, 'environmentRegistryRole', b['ob.environmentRegistryRole'])

    # -------------------------------------------------------------------------
    # 1.12 environmentExtension (O, R)
    # -------------------------------------------------------------------------
    for x in collect_multival(pairs, 'ob.environmentExtension'):
        add_text(obj, 'environmentExtension', x)

    # -------------------------------------------------------------------------
    # 1.13 relationship (O, R)
    # Suporta múltiplos relatedObjectIdentifier/relatedEventIdentifier no MESMO
    # <relationship>, acumulando os três campos (Type/Value/Sequence) e "explodindo"
    # por pipe ("|") para emitir contêineres alinhados.
    # -------------------------------------------------------------------------
    rels = collect_blocks(
        pairs,
        [
            'ob.relationshipType',
            'ob.relationshipSubType',

            # relatedObjectIdentifier (M, R)
            'ob.relatedObjectIdentifierType',
            'ob.relatedObjectIdentifierValue',
            'ob.relatedObjectSequence',

            # relatedEventIdentifier (O, R)
            'ob.relatedEventIdentifierType',
            'ob.relatedEventIdentifierValue',
            'ob.relatedEventSequence',

            # relatedEnvironmentPurpose (O, R) – simples repetível
            'ob.relatedEnvironmentPurpose',

            # relatedEnvironmentCharacteristic (O, NR)
            'ob.relatedEnvironmentCharacteristic',
        ],
        accumulate_keys={
            'ob.relatedObjectIdentifierType',
            'ob.relatedObjectIdentifierValue',
            'ob.relatedObjectSequence',
            'ob.relatedEventIdentifierType',
            'ob.relatedEventIdentifierValue',
            'ob.relatedEventSequence',
            'ob.relatedEnvironmentPurpose',
        }
    )
    for b in rels:
        rel = add(obj, 'relationship')
        add_text(rel, 'relationshipType',    b['ob.relationshipType'])
        add_text(rel, 'relationshipSubType', b['ob.relationshipSubType'])

        # relatedObjectIdentifier (M, R) — explode pelos pipes
        ro_types  = split_pipe(b.get('ob.relatedObjectIdentifierType', ''))
        ro_values = split_pipe(b.get('ob.relatedObjectIdentifierValue', ''))
        ro_seqs   = split_pipe(b.get('ob.relatedObjectSequence', ''))
        for i in range(min(len(ro_types), len(ro_values))):
            ro = add(rel, 'relatedObjectIdentifier')
            add_text(ro, 'relatedObjectIdentifierType',  ro_types[i])
            add_text(ro, 'relatedObjectIdentifierValue', ro_values[i])
            if i < len(ro_seqs):
                add_text(ro, 'relatedObjectSequence', ro_seqs[i])

        # relatedEventIdentifier (O, R) — explode pelos pipes
        re_types  = split_pipe(b.get('ob.relatedEventIdentifierType', ''))
        re_values = split_pipe(b.get('ob.relatedEventIdentifierValue', ''))
        re_seqs   = split_pipe(b.get('ob.relatedEventSequence', ''))
        for i in range(min(len(re_types), len(re_values))):
            rei = add(rel, 'relatedEventIdentifier')
            add_text(rei, 'relatedEventIdentifierType',  re_types[i])
            add_text(rei, 'relatedEventIdentifierValue', re_values[i])
            if i < len(re_seqs):
                add_text(rei, 'relatedEventSequence', re_seqs[i])

        # relatedEnvironmentPurpose (O, R)
        for p in split_pipe(b.get('ob.relatedEnvironmentPurpose', '')):
            add_text(rel, 'relatedEnvironmentPurpose', p)

        # relatedEnvironmentCharacteristic (O, NR)
        add_text(rel, 'relatedEnvironmentCharacteristic', b['ob.relatedEnvironmentCharacteristic'])

    # -------------------------------------------------------------------------
    # 1.14 linkingEventIdentifier (O, R)
    # -------------------------------------------------------------------------
    leis = collect_blocks(pairs, [
        'ob.linkingEventIdentifierType',
        'ob.linkingEventIdentifierValue',
    ])
    for b in leis:
        lei = add(obj, 'linkingEventIdentifier')
        add_text(lei, 'linkingEventIdentifierType',  b['ob.linkingEventIdentifierType'])
        add_text(lei, 'linkingEventIdentifierValue', b['ob.linkingEventIdentifierValue'])

    # -------------------------------------------------------------------------
    # 1.15 linkingRightsStatementIdentifier (O, R)
    # -------------------------------------------------------------------------
    lrs = collect_blocks(pairs, [
        'ob.linkingRightsStatementIdentifierType',
        'ob.linkingRightsStatementIdentifierValue',
    ])
    for b in lrs:
        lr = add(obj, 'linkingRightsStatementIdentifier')
        add_text(lr, 'linkingRightsStatementIdentifierType',  b['ob.linkingRightsStatementIdentifierType'])
        add_text(lr, 'linkingRightsStatementIdentifierValue', b['ob.linkingRightsStatementIdentifierValue'])

    # -------------------------------------------------------------------------
    # EXTENSÕES: ob.ext.* → <extension> com prefixo 'ext-edocs'
    # (cada chave ob.ext.X vira <ext-edocs.ext.X>text</ext-edocs.ext.X>)
    # -------------------------------------------------------------------------
    ext_present = any((k.startswith('ob.ext.') and str(v).strip()) for k, v in pairs)
    if ext_present:
        ext = add(obj, 'extension')
        for k, v in pairs:
            if not k.startswith('ob.ext.'):
                continue
            val = str(v).strip()
            if not val:
                continue
            local = k[len('ob.ext.'):]
            el = ET.SubElement(ext, f'{EXT_NS_PREFIX}.ext.{local}')
            el.text = val

    return obj
