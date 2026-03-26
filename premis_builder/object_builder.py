# object_builder.py
# -----------------------------------------------------------------------------
# Constrói o elemento <object> do PREMIS 3.0 a partir de uma linha do CSV.
#
# No PREMIS 3.0, um <object> pode representar três tipos de entidade digital,
# definidos pelo atributo xsi:type:
#   premis:file              → arquivo individual (ex.: um PDF)
#   premis:representation    → conjunto de arquivos que formam um objeto lógico
#   premis:intellectualEntity → entidade intelectual (ex.: um processo, um livro)
#
# Política adotada neste módulo:
#   - Um contêiner XML só é criado se houver ao menos um valor preenchido
#     para algum de seus filhos (evita tags vazias no XML).
#   - Campos repetíveis em um mesmo bloco são acumulados com " | " pelo
#     coletor (accumulate_keys) e depois "explodidos" em múltiplos elementos.
#   - Para grupos (Type/Value/Sequence), os três campos são acumulados juntos
#     e fatiados por pipe para emitir múltiplos contêineres alinhados.
#
# Campos do CSV reconhecidos por este módulo (prefixo "ob."):
#   ob.objectIdentifierType / Value    → identificador do objeto (M, R)
#   ob.xsi_type / ob.objectCategory   → tipo do objeto PREMIS
#   ob.preservationLevel.*            → nível de preservação (O, R)
#   ob.significantProperties.*        → propriedades significativas (O, R)
#   ob.compositionLevel               → nível de composição (O)
#   ob.messageDigestAlgorithm/Digest/Originator → fixidade/hash (O, R)
#   ob.size                           → tamanho em bytes (O)
#   ob.formatDesignation.* / ob.formatRegistry.* → formato do arquivo (O, R)
#   ob.creatingApplication.*          → aplicação criadora (O, R)
#   ob.inhibitors.*                   → inibidores de acesso (O, R)
#   ob.originalName                   → nome original do arquivo (O)
#   ob.storage.*                      → localização de armazenamento (O, R)
#   ob.signatureEncoding / signer / … → informações de assinatura (O, R)
#   ob.environmentFunction.*          → função do ambiente (O, R)
#   ob.environmentDesignation.*       → designação do ambiente (O, R)
#   ob.environmentRegistry.*          → registro do ambiente (O, R)
#   ob.environmentExtension           → extensão do ambiente (O, R)
#   ob.relationshipType / SubType / … → relacionamentos com outros objetos (O, R)
#   ob.linkingEventIdentifierType / Value   → eventos vinculados (O, R)
#   ob.linkingRightsStatementIdentifier.* → direitos vinculados (O, R)
#   ob.ext.*                          → extensões customizadas (O, R)
# -----------------------------------------------------------------------------

import xml.etree.ElementTree as ET
from .utils import (
    add, add_text, collect_blocks, collect_multival, emit_roles, normalize_dt,
    NS, EXT_NS_PREFIX, split_pipe
)


def build_object(root, pairs):
    """
    Constrói um elemento <object> PREMIS 3.0 e o adiciona a 'root'.

    Parâmetros:
        root  — elemento XML pai (normalmente o <premis> raiz)
        pairs — lista de tuplas (cabeçalho, valor) de uma linha do CSV

    Retorna o elemento <object> criado.
    """

    # Normaliza os cabeçalhos: remove espaços extras para evitar erros de comparação
    pairs = [(str(k).strip(), v) for (k, v) in pairs]

    # Cria o contêiner <object> dentro do elemento raiz
    obj = add(root, 'object')

    # =========================================================================
    # 1.1  objectIdentifier (M, R) — Obrigatório e repetível
    # =========================================================================
    # Identifica unicamente o objeto. Um mesmo objeto pode ter múltiplos
    # identificadores (ex.: ID interno + UUID + DOI).
    # Tentamos coletar blocos (Type, Value) via collect_blocks; se o coletor
    # não encontrar nada (colunas não repetidas), usamos um fallback simples.
    oids = collect_blocks(pairs, [
        'ob.objectIdentifierType',
        'ob.objectIdentifierValue',
    ])
    if not oids:
        # Fallback: busca o primeiro valor não-vazio de cada campo individualmente
        t = next((v for k, v in pairs if k == 'ob.objectIdentifierType'  and str(v).strip()), "")
        v = next((v for k, v in pairs if k == 'ob.objectIdentifierValue' and str(v).strip()), "")
        if t and v:
            oids = [{'ob.objectIdentifierType': t, 'ob.objectIdentifierValue': v}]

    for b in oids:
        oid = add(obj, 'objectIdentifier')
        add_text(oid, 'objectIdentifierType',  b['ob.objectIdentifierType'])
        add_text(oid, 'objectIdentifierValue', b['ob.objectIdentifierValue'])

    # =========================================================================
    # 1.2  xsi:type — Tipo do objeto PREMIS (atributo, não elemento filho)
    # =========================================================================
    # Define se o objeto é um file, representation ou intellectualEntity.
    # Preferência: coluna explícita "ob.xsi_type" no CSV.
    # Compatibilidade: se não houver ob.xsi_type, deriva de "ob.objectCategory"
    # (coluna usada em versões anteriores do modelo de dados).
    xsi_from_csv = next(
        (v for k, v in pairs if k == 'ob.xsi_type' and str(v).strip()),
        ""
    )

    if not xsi_from_csv:
        # Tenta derivar o tipo a partir da categoria legada
        cat = next(
            (v for k, v in pairs if k == 'ob.objectCategory' and str(v).strip()),
            ""
        )
        if cat:
            # Normaliza para comparação: remove espaços, maiúsculas e underscores
            cat_norm = str(cat).strip().lower().replace(" ", "").replace("_", "")
            if cat_norm == "file":
                xsi_from_csv = "premis:file"
            elif cat_norm == "representation":
                xsi_from_csv = "premis:representation"
            elif cat_norm in ("intellectualentity",):
                xsi_from_csv = "premis:intellectualEntity"

    if xsi_from_csv:
        xsi_norm = str(xsi_from_csv).strip()
        # Se o usuário informou só "file" sem prefixo, adiciona "premis:"
        if ":" not in xsi_norm:
            xsi_norm = f"premis:{xsi_norm}"
        # Define o atributo xsi:type no elemento <object>
        obj.set(f"{{{NS['xsi']}}}type", xsi_norm)

    # =========================================================================
    # 1.3  preservationLevel (O, R) — Opcional e repetível
    # =========================================================================
    # Descreve a estratégia de preservação aplicada ao objeto.
    # "Rationale" é repetível dentro do mesmo nível → acumulamos com pipe.
    # "DateAssigned" não é repetível → normalizamos a data para ISO.
    pls = collect_blocks(
        pairs,
        [
            'ob.preservationLevelType',
            'ob.preservationLevelValue',
            'ob.preservationLevelRole',
            'ob.preservationLevelRationale',    # repetível: acumula com pipe
            'ob.preservationLevelDateAssigned', # não repetível: data ISO
        ],
        accumulate_keys={'ob.preservationLevelRationale'}
    )
    for b in pls:
        pl = add(obj, 'preservationLevel')
        add_text(pl, 'preservationLevelType',  b['ob.preservationLevelType'])
        add_text(pl, 'preservationLevelValue', b['ob.preservationLevelValue'])
        add_text(pl, 'preservationLevelRole',  b['ob.preservationLevelRole'])
        # Múltiplos rationales → múltiplos elementos <preservationLevelRationale>
        emit_roles(pl, 'preservationLevelRationale', b['ob.preservationLevelRationale'])
        add_text(pl, 'preservationLevelDateAssigned',
                 normalize_dt(b['ob.preservationLevelDateAssigned']))

    # =========================================================================
    # 1.4  significantProperties (O, R) — Opcional e repetível
    # =========================================================================
    # Características do objeto que devem ser mantidas ao longo do tempo
    # para garantir sua autenticidade e usabilidade (ex.: resolução de imagem,
    # número de páginas, fontes de texto, etc.).
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

    # =========================================================================
    # 1.5  objectCharacteristics (M para file/bitstream, O para IE)
    # =========================================================================
    # Agrupa as características técnicas do objeto digital.
    # Usamos "criação sob demanda" (lazy): o elemento <objectCharacteristics>
    # só é criado quando há ao menos um filho para inserir nele.
    # Isso evita gerar <objectCharacteristics/> vazio em entidades intelectuais.
    oc = None

    def ensure_oc():
        """
        Garante que o elemento <objectCharacteristics> exista.
        Cria-o na primeira chamada; nas chamadas seguintes, reutiliza o mesmo.
        """
        nonlocal oc
        if oc is None:
            oc = add(obj, 'objectCharacteristics')

    # -------------------------------------------------------------------------
    # 1.5.1  compositionLevel (O) — Opcional, não repetível
    # -------------------------------------------------------------------------
    # Indica o nível de encapsulamento do arquivo (0 = não comprimido/encapsulado,
    # 1 = um nível de compressão, etc.).
    comp = next((v for k, v in pairs
                 if k == 'ob.compositionLevel' and str(v).strip()), "")
    if comp:
        ensure_oc()
        add_text(oc, 'compositionLevel', comp)

    # -------------------------------------------------------------------------
    # 1.5.2  fixity (O, R) — Opcional e repetível
    # -------------------------------------------------------------------------
    # Registra o hash (digest) do arquivo para verificação de integridade.
    # Suporta dois padrões de cabeçalho no CSV:
    #   Novo: ob.fixity.messageDigestAlgorithm, ob.fixity.messageDigest, ...
    #   Antigo (flat): ob.messageDigestAlgorithm, ob.messageDigest, ...
    fixities = collect_blocks(pairs, [
        'ob.fixity.messageDigestAlgorithm',
        'ob.fixity.messageDigest',
        'ob.fixity.messageDigestOriginator',
    ])
    if not fixities:
        # Fallback: tenta os cabeçalhos "achatados" (versão anterior do modelo)
        fixities = collect_blocks(pairs, [
            'ob.messageDigestAlgorithm',
            'ob.messageDigest',
            'ob.messageDigestOriginator',
        ])

    for b in fixities:
        if any((b.get(k) or '').strip() for k in b):  # só cria se houver dado
            ensure_oc()
            fx = add(oc, 'fixity')
            # Tenta o cabeçalho novo; se vazio, usa o antigo (compatibilidade)
            add_text(fx, 'messageDigestAlgorithm',
                     b.get('ob.fixity.messageDigestAlgorithm') or b.get('ob.messageDigestAlgorithm'))
            add_text(fx, 'messageDigest',
                     b.get('ob.fixity.messageDigest')          or b.get('ob.messageDigest'))
            add_text(fx, 'messageDigestOriginator',
                     b.get('ob.fixity.messageDigestOriginator') or b.get('ob.messageDigestOriginator'))

    # -------------------------------------------------------------------------
    # 1.5.3  size (O) — Opcional, não repetível
    # -------------------------------------------------------------------------
    # Tamanho do arquivo em bytes. Aceita os dois nomes de coluna
    # (ob.size e ob.objectCharacteristics.size) para compatibilidade.
    sv = next((v for k, v in pairs
               if k in ('ob.size', 'ob.objectCharacteristics.size') and str(v).strip()), "")
    if sv:
        ensure_oc()
        add_text(oc, 'size', sv)

    # -------------------------------------------------------------------------
    # 1.5.4  format (M para file, R) — Obrigatório para arquivos, repetível
    # -------------------------------------------------------------------------
    # Descreve o formato do arquivo digital. Pode conter:
    #   <formatDesignation>: nome e versão do formato (ex.: PDF 1.7)
    #   <formatRegistry>:    referência a um registro externo (ex.: PRONOM)
    #   <formatNote>:        notas livres sobre o formato (repetível)
    formats = collect_blocks(
        pairs,
        [
            'ob.formatDesignation.formatName',
            'ob.formatDesignation.formatVersion',
            'ob.formatRegistry.formatRegistryName',
            'ob.formatRegistry.formatRegistryKey',
            'ob.formatRegistry.formatRegistryRole',
            'ob.formatNote',  # repetível: acumula com pipe
        ],
        accumulate_keys={'ob.formatNote'}
    )
    for b in formats or [{}]:
        # Só cria <format> se houver ao menos um valor no bloco
        if not any((b.get(k) or '').strip() for k in b):
            continue
        ensure_oc()
        fmt = add(oc, 'format')

        # <formatDesignation> só é criado se houver nome ou versão
        has_fd = any((b.get(k) or '').strip() for k in (
            'ob.formatDesignation.formatName',
            'ob.formatDesignation.formatVersion',
        ))
        if has_fd:
            fd = add(fmt, 'formatDesignation')
            add_text(fd, 'formatName',    b.get('ob.formatDesignation.formatName'))
            add_text(fd, 'formatVersion', b.get('ob.formatDesignation.formatVersion'))

        # <formatRegistry> só é criado se houver nome, chave ou papel
        if any((b.get(k) or '').strip() for k in (
            'ob.formatRegistry.formatRegistryName',
            'ob.formatRegistry.formatRegistryKey',
            'ob.formatRegistry.formatRegistryRole',
        )):
            fr = add(fmt, 'formatRegistry')
            add_text(fr, 'formatRegistryName', b.get('ob.formatRegistry.formatRegistryName'))
            add_text(fr, 'formatRegistryKey',  b.get('ob.formatRegistry.formatRegistryKey'))
            add_text(fr, 'formatRegistryRole', b.get('ob.formatRegistry.formatRegistryRole'))

        # Notas sobre o formato (acumuladas com pipe → múltiplos elementos)
        emit_roles(fmt, 'formatNote', b.get('ob.formatNote'))

    # -------------------------------------------------------------------------
    # 1.5.5  creatingApplication (O, R) — Opcional e repetível
    # -------------------------------------------------------------------------
    # Registra a aplicação que criou o arquivo digital.
    # "creatingApplicationExtension" é repetível dentro do mesmo bloco.
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
        # normalize_dt converte datas de planilha para ISO 8601
        add_text(ca, 'dateCreatedByApplication',   normalize_dt(b['ob.dateCreatedByApplication']))
        emit_roles(ca, 'creatingApplicationExtension', b['ob.creatingApplicationExtension'])

    # -------------------------------------------------------------------------
    # 1.5.6  inhibitors (O, R) — Opcional e repetível
    # -------------------------------------------------------------------------
    # Registra mecanismos que bloqueiam ou limitam o acesso ao objeto
    # (ex.: criptografia, DRM, senha). "inhibitorTarget" é repetível.
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

    # -------------------------------------------------------------------------
    # 1.5.7  objectCharacteristicsExtension (O, R) — Opcional e repetível
    # -------------------------------------------------------------------------
    # Campo de extensão para características técnicas que não cabem nos campos
    # padrão do PREMIS (ex.: metadados técnicos de áudio, vídeo, etc.).
    for x in collect_multival(pairs, 'ob.objectCharacteristicsExtension'):
        ensure_oc()
        add_text(oc, 'objectCharacteristicsExtension', x)

    # =========================================================================
    # 1.6  originalName (O) — Opcional, não repetível
    # =========================================================================
    # Nome original do arquivo antes de qualquer renomeação durante a ingestão.
    # Importante para rastrear a proveniência do objeto.
    add_text(obj, 'originalName',
             next((v for k, v in pairs
                   if k == 'ob.originalName' and str(v).strip()), ""))

    # =========================================================================
    # 1.7  storage (O, R) — Opcional e repetível
    # =========================================================================
    # Indica onde o objeto está armazenado fisicamente ou logicamente.
    # Pode haver múltiplos locais (ex.: cópia local + backup em nuvem).
    # <contentLocation> fica dentro de <storage>.
    stores = collect_blocks(pairs, [
        'ob.storage.contentLocationType',    # tipo: URL, filepath, etc.
        'ob.storage.contentLocationValue',   # o endereço/caminho em si
        'ob.storage.storageMedium',          # meio: disco, fita, nuvem, etc.
    ])
    for b in stores:
        st = add(obj, 'storage')
        cl = add(st, 'contentLocation')
        add_text(cl, 'contentLocationType',  b['ob.storage.contentLocationType'])
        add_text(cl, 'contentLocationValue', b['ob.storage.contentLocationValue'])
        add_text(st, 'storageMedium',        b['ob.storage.storageMedium'])

    # =========================================================================
    # 1.8  signatureInformation (O, R) — Opcional e repetível
    # =========================================================================
    # Registra assinaturas digitais ou eletrônicas aplicadas ao objeto.
    # <signatureInformation> agrupa uma ou mais <signature>.
    # "signatureProperties" é repetível dentro da mesma assinatura.
    sigs = collect_blocks(
        pairs,
        [
            'ob.signatureEncoding',          # codificação: PKCS#7, XML-Sig, etc.
            'ob.signer',                     # quem assinou
            'ob.signatureMethod',            # algoritmo de assinatura
            'ob.signatureValue',             # valor da assinatura (hash cifrado)
            'ob.signatureValidationRules',   # regras para validar
            'ob.signatureProperties',        # propriedades adicionais (repetível)
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

    # =========================================================================
    # 1.9  environmentFunction (O, R) — Opcional e repetível
    # =========================================================================
    # Descreve a função de um ambiente de software/hardware necessário para
    # renderizar ou executar o objeto (ex.: "requires", "renders").
    efuncs = collect_blocks(pairs, [
        'ob.environmentFunctionType',   # tipo de função
        'ob.environmentFunctionLevel',  # nível/prioridade
    ])
    for b in efuncs:
        ef = add(obj, 'environmentFunction')
        add_text(ef, 'environmentFunctionType',  b['ob.environmentFunctionType'])
        add_text(ef, 'environmentFunctionLevel', b['ob.environmentFunctionLevel'])

    # =========================================================================
    # 1.10  environmentDesignation (O, R) — Opcional e repetível
    # =========================================================================
    # Identifica o software ou hardware necessário para usar o objeto
    # (ex.: Adobe Acrobat Reader 9.0 para abrir um PDF 1.7).
    # Notas e extensões são repetíveis dentro do mesmo bloco.
    eds = collect_blocks(
        pairs,
        [
            'ob.environmentName',
            'ob.environmentVersion',
            'ob.environmentOrigin',
            'ob.environmentDesignationNote',       # repetível
            'ob.environmentDesignationExtension',  # repetível
        ],
        accumulate_keys={
            'ob.environmentDesignationNote',
            'ob.environmentDesignationExtension',
        }
    )
    for b in eds:
        # Só cria o elemento se houver ao menos um campo com valor
        if not any((b.get(k) or '').strip() for k in b):
            continue
        ed = add(obj, 'environmentDesignation')
        add_text(ed, 'environmentName',    b['ob.environmentName'])
        add_text(ed, 'environmentVersion', b['ob.environmentVersion'])
        add_text(ed, 'environmentOrigin',  b['ob.environmentOrigin'])
        emit_roles(ed, 'environmentDesignationNote',      b['ob.environmentDesignationNote'])
        emit_roles(ed, 'environmentDesignationExtension', b['ob.environmentDesignationExtension'])

    # =========================================================================
    # 1.11  environmentRegistry (O, R) — Opcional e repetível
    # =========================================================================
    # Referencia um registro externo que descreve o ambiente necessário
    # (ex.: um identificador PRONOM para o formato).
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

    # =========================================================================
    # 1.12  environmentExtension (O, R) — Opcional e repetível
    # =========================================================================
    # Campo de extensão para informações de ambiente que não cabem nos campos
    # padrão do PREMIS.
    for x in collect_multival(pairs, 'ob.environmentExtension'):
        add_text(obj, 'environmentExtension', x)

    # =========================================================================
    # 1.13  relationship (O, R) — Opcional e repetível
    # =========================================================================
    # Descreve relacionamentos deste objeto com outros objetos ou eventos.
    # Exemplos:
    #   - structural / includes    → processo inclui um documento
    #   - structural / isIncludedIn → documento está incluso em processo
    #   - reference / documents    → termo de entranhamento documenta um documento
    #   - derivation / isDerivedFrom → derivado de outro objeto
    #
    # Desafio: um <relationship> pode ter MÚLTIPLOS relatedObjectIdentifier e
    # relatedEventIdentifier. Para representar isso no CSV sem explodir em
    # muitas colunas, usamos pipes (" | ") para separar os valores na mesma célula.
    # Os campos Type, Value e Sequence são acumulados juntos e depois "explodidos"
    # alinhadamente (1º tipo com 1º valor, 2º tipo com 2º valor, etc.).
    rels = collect_blocks(
        pairs,
        [
            'ob.relationshipType',
            'ob.relationshipSubType',

            # Objetos relacionados (M, R dentro de <relationship>)
            'ob.relatedObjectIdentifierType',
            'ob.relatedObjectIdentifierValue',
            'ob.relatedObjectSequence',

            # Eventos relacionados (O, R dentro de <relationship>)
            'ob.relatedEventIdentifierType',
            'ob.relatedEventIdentifierValue',
            'ob.relatedEventSequence',

            # Propósito do ambiente relacionado (O, R)
            'ob.relatedEnvironmentPurpose',

            # Característica do ambiente relacionado (O, NR)
            'ob.relatedEnvironmentCharacteristic',
        ],
        accumulate_keys={
            # Estes campos acumulam com pipe para suportar múltiplos relacionamentos
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

        # --- relatedObjectIdentifier (M, R) ---
        # Divide os valores acumulados por pipe e emite um elemento por par (Type, Value)
        ro_types  = split_pipe(b.get('ob.relatedObjectIdentifierType',  ''))
        ro_values = split_pipe(b.get('ob.relatedObjectIdentifierValue', ''))
        ro_seqs   = split_pipe(b.get('ob.relatedObjectSequence',        ''))
        for i in range(min(len(ro_types), len(ro_values))):
            ro = add(rel, 'relatedObjectIdentifier')
            add_text(ro, 'relatedObjectIdentifierType',  ro_types[i])
            add_text(ro, 'relatedObjectIdentifierValue', ro_values[i])
            if i < len(ro_seqs):
                add_text(ro, 'relatedObjectSequence', ro_seqs[i])

        # --- relatedEventIdentifier (O, R) ---
        # Mesmo padrão: divide por pipe e alinha Type, Value e Sequence
        re_types  = split_pipe(b.get('ob.relatedEventIdentifierType',  ''))
        re_values = split_pipe(b.get('ob.relatedEventIdentifierValue', ''))
        re_seqs   = split_pipe(b.get('ob.relatedEventSequence',        ''))
        for i in range(min(len(re_types), len(re_values))):
            rei = add(rel, 'relatedEventIdentifier')
            add_text(rei, 'relatedEventIdentifierType',  re_types[i])
            add_text(rei, 'relatedEventIdentifierValue', re_values[i])
            if i < len(re_seqs):
                add_text(rei, 'relatedEventSequence', re_seqs[i])

        # --- relatedEnvironmentPurpose (O, R) ---
        for p in split_pipe(b.get('ob.relatedEnvironmentPurpose', '')):
            add_text(rel, 'relatedEnvironmentPurpose', p)

        # --- relatedEnvironmentCharacteristic (O, NR) ---
        add_text(rel, 'relatedEnvironmentCharacteristic',
                 b['ob.relatedEnvironmentCharacteristic'])

    # =========================================================================
    # 1.14  linkingEventIdentifier (O, R) — Opcional e repetível
    # =========================================================================
    # Aponta para os eventos associados a este objeto.
    # Permite navegar do objeto para seus eventos sem varrer todo o XML.
    leis = collect_blocks(pairs, [
        'ob.linkingEventIdentifierType',
        'ob.linkingEventIdentifierValue',
    ])
    for b in leis:
        lei = add(obj, 'linkingEventIdentifier')
        add_text(lei, 'linkingEventIdentifierType',  b['ob.linkingEventIdentifierType'])
        add_text(lei, 'linkingEventIdentifierValue', b['ob.linkingEventIdentifierValue'])

    # =========================================================================
    # 1.15  linkingRightsStatementIdentifier (O, R) — Opcional e repetível
    # =========================================================================
    # Aponta para as declarações de direitos que se aplicam a este objeto.
    lrs = collect_blocks(pairs, [
        'ob.linkingRightsStatementIdentifierType',
        'ob.linkingRightsStatementIdentifierValue',
    ])
    for b in lrs:
        lr = add(obj, 'linkingRightsStatementIdentifier')
        add_text(lr, 'linkingRightsStatementIdentifierType',  b['ob.linkingRightsStatementIdentifierType'])
        add_text(lr, 'linkingRightsStatementIdentifierValue', b['ob.linkingRightsStatementIdentifierValue'])

    # =========================================================================
    # Extensões customizadas: ob.ext.* → <extension>
    # =========================================================================
    # Qualquer coluna com prefixo "ob.ext." é tratada como extensão customizada.
    # Cada campo "ob.ext.NOME" vira um elemento <ext-edocs.ext.NOME> dentro
    # de um contêiner <extension>.
    #
    # Exemplo: ob.ext.resumo → <ext-edocs.ext.resumo>texto</ext-edocs.ext.resumo>
    #
    # Nota: este elemento NÃO usa namespace XML — o prefixo "ext-edocs" é
    # parte literal do nome da tag, por convenção do projeto.
    ext_present = any(
        (k.startswith('ob.ext.') and str(v).strip())
        for k, v in pairs
    )
    if ext_present:
        ext = add(obj, 'extension')
        for k, v in pairs:
            if not k.startswith('ob.ext.'):
                continue
            val = str(v).strip()
            if not val:
                continue
            # Remove o prefixo "ob.ext." para obter o nome local da tag
            local = k[len('ob.ext.'):]
            el = ET.SubElement(ext, f'{EXT_NS_PREFIX}.ext.{local}')
            el.text = val

    return obj
