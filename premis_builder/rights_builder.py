# rights_builder.py
# -----------------------------------------------------------------------------
# Constrói o elemento <rights> do PREMIS 3.0 a partir de uma linha do CSV.
#
# Um <rights> (mais precisamente um <rightsStatement> dentro de <rights>)
# descreve as permissões e restrições de acesso e uso de um objeto digital.
# A base dos direitos pode ser:
#   - copyright   → direitos autorais
#   - license     → licença de uso
#   - statute     → legislação aplicável
#   - other       → outra base (ex.: política institucional)
#
# Campos do CSV reconhecidos por este módulo (prefixo "rt."):
#   rt.rightsStatementIdentifierType / Value → identificador da declaração
#   rt.rightsBasis                → base dos direitos (copyright/license/statute/other)
#   rt.copyrightInformation.*     → detalhes de direito autoral
#   rt.licenseInformation.*       → detalhes de licença
#   rt.statuteInformation.*       → detalhes de legislação
#   rt.otherRightsInformation.*   → outra base de direitos
#   rt.rightsGranted.*            → atos autorizados (access, read, replicate, etc.)
#   rt.linkingObjectIdentifier.*  → objetos aos quais esta declaração se aplica
#   rt.linkingAgentIdentifier.*   → agentes vinculados (credenciado, credenciador, etc.)
#   rt.rightsExtension            → extensão customizada (repetível)
# -----------------------------------------------------------------------------

from .utils import add, add_text, collect_blocks, collect_multival, emit_roles


def build_rights(root, pairs):
    """
    Constrói um elemento <rights> PREMIS 3.0 (contendo um <rightsStatement>)
    e o adiciona a 'root'.

    Parâmetros:
        root  — elemento XML pai (normalmente o <premis> raiz)
        pairs — lista de tuplas (cabeçalho, valor) de uma linha do CSV

    Retorna o elemento <rights> criado.
    """

    # <rights> é o contêiner externo; <rightsStatement> é onde ficam os dados
    rt = add(root, 'rights')
    rs = add(rt, 'rightsStatement')

    # -------------------------------------------------------------------------
    # 4.1 rightsStatementIdentifier (M) — Obrigatório
    # Identifica unicamente esta declaração de direitos.
    # -------------------------------------------------------------------------
    rsi = add(rs, 'rightsStatementIdentifier')
    add_text(rsi, 'rightsStatementIdentifierType',
             next((v for k, v in pairs if k == 'rt.rightsStatementIdentifierType' and str(v).strip()), ""))
    add_text(rsi, 'rightsStatementIdentifierValue',
             next((v for k, v in pairs if k == 'rt.rightsStatementIdentifierValue' and str(v).strip()), ""))

    # -------------------------------------------------------------------------
    # 4.2 rightsBasis (M) — Obrigatório
    # Indica a base legal/institucional dos direitos declarados.
    # Valores típicos: copyright, license, statute, other.
    # -------------------------------------------------------------------------
    add_text(rs, 'rightsBasis',
             next((v for k, v in pairs if k == 'rt.rightsBasis' and str(v).strip()), ""))

    # -------------------------------------------------------------------------
    # 4.3 copyrightInformation (O) — Opcional
    # Criado somente se houver ao menos um campo de copyright preenchido.
    # Contém status, jurisdição, data de determinação, notas e documentação.
    # -------------------------------------------------------------------------
    cs = next((v for k, v in pairs if k == 'rt.copyrightInformation.copyrightStatus'                  and str(v).strip()), "")
    cj = next((v for k, v in pairs if k == 'rt.copyrightInformation.copyrightJurisdiction'             and str(v).strip()), "")
    cd = next((v for k, v in pairs if k == 'rt.copyrightInformation.copyrightStatusDeterminationDate'  and str(v).strip()), "")
    cn = next((v for k, v in pairs if k == 'rt.copyrightInformation.copyrightNote'                     and str(v).strip()), "")
    ct = next((v for k, v in pairs if k == 'rt.copyrightInformation.copyrightDocumentationIdentifierType' and str(v).strip()), "")

    if cs or cj or cd or cn or ct:
        ci = add(rs, 'copyrightInformation')
        add_text(ci, 'copyrightStatus',                   cs)
        add_text(ci, 'copyrightJurisdiction',             cj)
        add_text(ci, 'copyrightStatusDeterminationDate',  cd)

        # copyrightNote é repetível
        for n in collect_multival(pairs, 'rt.copyrightInformation.copyrightNote'):
            add_text(ci, 'copyrightNote', n)

        # copyrightDocumentationIdentifier: pode haver múltiplos documentos comprobatórios
        docs = collect_blocks(pairs, [
            'rt.copyrightInformation.copyrightDocumentationIdentifierType',
            'rt.copyrightInformation.copyrightDocumentationIdentifierValue',
            'rt.copyrightInformation.copyrightDocumentationRole',
        ])
        for b in docs:
            cdi = add(ci, 'copyrightDocumentationIdentifier')
            add_text(cdi, 'copyrightDocumentationIdentifierType',  b['rt.copyrightInformation.copyrightDocumentationIdentifierType'])
            add_text(cdi, 'copyrightDocumentationIdentifierValue', b['rt.copyrightInformation.copyrightDocumentationIdentifierValue'])
            add_text(cdi, 'copyrightDocumentationRole',            b['rt.copyrightInformation.copyrightDocumentationRole'])

        # Datas de vigência dos direitos autorais (início e fim)
        cad_s = next((v for k, v in pairs if k == 'rt.copyrightInformation.copyrightApplicableDates.startDate' and str(v).strip()), "")
        cad_e = next((v for k, v in pairs if k == 'rt.copyrightInformation.copyrightApplicableDates.endDate'   and str(v).strip()), "")
        if cad_s or cad_e:
            cad = add(ci, 'copyrightApplicableDates')
            add_text(cad, 'startDate', cad_s)
            add_text(cad, 'endDate',   cad_e)

    # -------------------------------------------------------------------------
    # 4.4 licenseInformation (O) — Opcional
    # Criado somente se houver dados de licença preenchidos.
    # Contém identificadores de documentos da licença, termos e notas.
    # -------------------------------------------------------------------------
    lt = next((v for k, v in pairs if k == 'rt.licenseInformation.licenseTerms'                       and str(v).strip()), "")
    ld = next((v for k, v in pairs if k == 'rt.licenseInformation.licenseDocumentationIdentifierType' and str(v).strip()), "")
    ln = collect_multival(pairs, 'rt.licenseInformation.licenseNote')

    if lt or ld or ln:
        li = add(rs, 'licenseInformation')

        # Documentos que comprovam ou descrevem a licença
        ldis = collect_blocks(pairs, [
            'rt.licenseInformation.licenseDocumentationIdentifierType',
            'rt.licenseInformation.licenseDocumentationIdentifierValue',
            'rt.licenseInformation.licenseDocumentationRole',
        ])
        for b in ldis:
            ldi = add(li, 'licenseDocumentationIdentifier')
            add_text(ldi, 'licenseDocumentationIdentifierType',  b['rt.licenseInformation.licenseDocumentationIdentifierType'])
            add_text(ldi, 'licenseDocumentationIdentifierValue', b['rt.licenseInformation.licenseDocumentationIdentifierValue'])
            add_text(ldi, 'licenseDocumentationRole',            b['rt.licenseInformation.licenseDocumentationRole'])

        add_text(li, 'licenseTerms', lt)

        # licenseNote é repetível
        for n in ln:
            add_text(li, 'licenseNote', n)

        # Datas de vigência da licença
        lad_s = next((v for k, v in pairs if k == 'rt.licenseInformation.licenseApplicableDates.startDate' and str(v).strip()), "")
        lad_e = next((v for k, v in pairs if k == 'rt.licenseInformation.licenseApplicableDates.endDate'   and str(v).strip()), "")
        if lad_s or lad_e:
            lad = add(li, 'licenseApplicableDates')
            add_text(lad, 'startDate', lad_s)
            add_text(lad, 'endDate',   lad_e)

    # -------------------------------------------------------------------------
    # 4.5 statuteInformation (O, R) — Opcional e repetível
    # Registra a legislação (lei, decreto, portaria etc.) que fundamenta os
    # direitos. Pode haver múltiplos estatutos. O último campo (notes) é
    # acumulável via accumulate_last=True.
    # -------------------------------------------------------------------------
    stats = collect_blocks(pairs, [
        'rt.statuteInformation.statuteJurisdiction',
        'rt.statuteInformation.statuteCitation',
        'rt.statuteInformation.statuteInformationDeterminationDate',
        'rt.statuteInformation.statuteNote',
        'rt.statuteInformation.statuteDocumentationIdentifierType',
        'rt.statuteInformation.statuteDocumentationIdentifierValue',
        'rt.statuteInformation.statuteDocumentationRole',
        'rt.statuteInformation.statuteApplicableDates.startDate',
        'rt.statuteInformation.statuteApplicableDates.endDate',
    ], accumulate_last=True)  # acumula notas separadas por pipe

    for b in stats:
        si = add(rs, 'statuteInformation')
        add_text(si, 'statuteJurisdiction',                   b['rt.statuteInformation.statuteJurisdiction'])
        add_text(si, 'statuteCitation',                       b['rt.statuteInformation.statuteCitation'])
        add_text(si, 'statuteInformationDeterminationDate',   b['rt.statuteInformation.statuteInformationDeterminationDate'])

        # statuteNote acumulado: divide pelo pipe e emite múltiplos elementos
        if b['rt.statuteInformation.statuteNote']:
            for n in b['rt.statuteInformation.statuteNote'].split(' | '):
                add_text(si, 'statuteNote', n.strip())

        # Documento comprobatório do estatuto (opcional)
        if b['rt.statuteInformation.statuteDocumentationIdentifierType'] and \
           b['rt.statuteInformation.statuteDocumentationIdentifierValue']:
            sdi = add(si, 'statuteDocumentationIdentifier')
            add_text(sdi, 'statuteDocumentationIdentifierType',  b['rt.statuteInformation.statuteDocumentationIdentifierType'])
            add_text(sdi, 'statuteDocumentationIdentifierValue', b['rt.statuteInformation.statuteDocumentationIdentifierValue'])
            add_text(sdi, 'statuteDocumentationRole',            b['rt.statuteInformation.statuteDocumentationRole'])

        # Datas de vigência do estatuto
        if b['rt.statuteInformation.statuteApplicableDates.startDate'] or \
           b['rt.statuteInformation.statuteApplicableDates.endDate']:
            sad = add(si, 'statuteApplicableDates')
            add_text(sad, 'startDate', b['rt.statuteInformation.statuteApplicableDates.startDate'])
            add_text(sad, 'endDate',   b['rt.statuteInformation.statuteApplicableDates.endDate'])

    # -------------------------------------------------------------------------
    # 4.6 otherRightsInformation (O) — Opcional
    # Usado quando a base dos direitos é "other" (ex.: política institucional).
    # Criado somente se houver ao menos um campo preenchido.
    # -------------------------------------------------------------------------
    orb = next((v for k, v in pairs if k == 'rt.otherRightsInformation.otherRightsBasis'                          and str(v).strip()), "")
    ort = next((v for k, v in pairs if k == 'rt.otherRightsInformation.otherRightsDocumentationIdentifierType'    and str(v).strip()), "")

    if orb or ort:
        ori = add(rs, 'otherRightsInformation')
        add_text(ori, 'otherRightsBasis', orb)

        # Datas de vigência da política/outro direito
        ord_s = next((v for k, v in pairs if k == 'rt.otherRightsInformation.otherRightsApplicableDates.startDate' and str(v).strip()), "")
        ord_e = next((v for k, v in pairs if k == 'rt.otherRightsInformation.otherRightsApplicableDates.endDate'   and str(v).strip()), "")
        if ord_s or ord_e:
            ordx = add(ori, 'otherRightsApplicableDates')
            add_text(ordx, 'startDate', ord_s)
            add_text(ordx, 'endDate',   ord_e)

        # Notas livres sobre a política (repetível)
        for n in collect_multival(pairs, 'rt.otherRightsInformation.otherRightsNote'):
            add_text(ori, 'otherRightsNote', n)

        # Documentos que comprovam a política
        odis = collect_blocks(pairs, [
            'rt.otherRightsInformation.otherRightsDocumentationIdentifierType',
            'rt.otherRightsInformation.otherRightsDocumentationIdentifierValue',
            'rt.otherRightsInformation.otherRightsDocumentationRole',
        ])
        for b in odis:
            odi = add(ori, 'otherRightsDocumentationIdentifier')
            add_text(odi, 'otherRightsDocumentationIdentifierType',  b['rt.otherRightsInformation.otherRightsDocumentationIdentifierType'])
            add_text(odi, 'otherRightsDocumentationIdentifierValue', b['rt.otherRightsInformation.otherRightsDocumentationIdentifierValue'])
            add_text(odi, 'otherRightsDocumentationRole',            b['rt.otherRightsInformation.otherRightsDocumentationRole'])

    # -------------------------------------------------------------------------
    # 4.7 rightsGranted (O, R) — Opcional e repetível
    # Descreve os atos permitidos (ex.: acesso, leitura, reprodução) e suas
    # restrições. Pode incluir períodos de vigência do ato ou da restrição.
    # O campo "restriction" e "rightsGrantedNote" são repetíveis (accumulate_last).
    # -------------------------------------------------------------------------
    grants = collect_blocks(pairs, [
        'rt.rightsGranted.act',
        'rt.rightsGranted.restriction',
        'rt.rightsGranted.termOfGrant.startDate',
        'rt.rightsGranted.termOfGrant.endDate',
        'rt.rightsGranted.termOfRestriction.startDate',
        'rt.rightsGranted.termOfRestriction.endDate',
        'rt.rightsGranted.rightsGrantedNote',
    ], accumulate_last=True)  # acumula notas e restrições por pipe

    for b in grants:
        rg = add(rs, 'rightsGranted')
        add_text(rg, 'act', b['rt.rightsGranted.act'])

        # "restriction" pode ter múltiplos valores (ex.: "Acesso restrito | Uso educacional")
        emit_roles(rg, 'restriction', b['rt.rightsGranted.restriction'])

        # Período de vigência do ato autorizado
        if b['rt.rightsGranted.termOfGrant.startDate'] or b['rt.rightsGranted.termOfGrant.endDate']:
            tg = add(rg, 'termOfGrant')
            add_text(tg, 'startDate', b['rt.rightsGranted.termOfGrant.startDate'])
            add_text(tg, 'endDate',   b['rt.rightsGranted.termOfGrant.endDate'])

        # Período de vigência da restrição
        if b['rt.rightsGranted.termOfRestriction.startDate'] or b['rt.rightsGranted.termOfRestriction.endDate']:
            tr = add(rg, 'termOfRestriction')
            add_text(tr, 'startDate', b['rt.rightsGranted.termOfRestriction.startDate'])
            add_text(tr, 'endDate',   b['rt.rightsGranted.termOfRestriction.endDate'])

        # Notas sobre o ato autorizado (repetível)
        emit_roles(rg, 'rightsGrantedNote', b['rt.rightsGranted.rightsGrantedNote'])

    # -------------------------------------------------------------------------
    # 4.8 linkingObjectIdentifier (O, R) — Opcional e repetível
    # Aponta para os objetos digitais aos quais esta declaração de direitos
    # se aplica. O role indica o papel do objeto (ex.: "subjectOfPolicy").
    # -------------------------------------------------------------------------
    lois = collect_blocks(pairs, [
        'rt.linkingObjectIdentifierType',
        'rt.linkingObjectIdentifierValue',
        'rt.linkingObjectRole',
    ], accumulate_last=True)

    for b in lois:
        loi = add(rs, 'linkingObjectIdentifier')
        add_text(loi, 'linkingObjectIdentifierType',  b['rt.linkingObjectIdentifierType'])
        add_text(loi, 'linkingObjectIdentifierValue', b['rt.linkingObjectIdentifierValue'])
        emit_roles(loi, 'linkingObjectRole', b['rt.linkingObjectRole'])

    # -------------------------------------------------------------------------
    # 4.9 linkingAgentIdentifier (O, R) — Opcional e repetível
    # Vincula agentes relacionados a esta declaração de direitos.
    # Exemplos de roles: "credenciado" (quem recebeu o direito),
    #                    "credenciador" (quem concedeu o direito).
    # -------------------------------------------------------------------------
    lais = collect_blocks(pairs, [
        'rt.linkingAgentIdentifierType',
        'rt.linkingAgentIdentifierValue',
        'rt.linkingAgentRole',
    ], accumulate_last=True)

    for b in lais:
        lai = add(rs, 'linkingAgentIdentifier')
        add_text(lai, 'linkingAgentIdentifierType',  b['rt.linkingAgentIdentifierType'])
        add_text(lai, 'linkingAgentIdentifierValue', b['rt.linkingAgentIdentifierValue'])
        emit_roles(lai, 'linkingAgentRole', b['rt.linkingAgentRole'])

    # -------------------------------------------------------------------------
    # 4.10 rightsExtension (O, R) — Opcional e repetível
    # Campo de extensão para metadados de direitos fora do padrão PREMIS.
    # Cada extensão é encapsulada em um <rightsExtension> dentro de <rights>
    # (note que fica em <rights>, não em <rightsStatement>).
    # -------------------------------------------------------------------------
    for x in collect_multival(pairs, 'rt.rightsExtension'):
        rext = add(rt, 'rightsExtension')
        el = add(rext, 'rightsExtension')
        el.text = x

    return rt
