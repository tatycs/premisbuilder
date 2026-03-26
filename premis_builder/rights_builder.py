from .utils import add, add_text, collect_blocks, collect_multival, emit_roles

def build_rights(root, pairs):
    rt = add(root, 'rights')
    rs = add(rt, 'rightsStatement')

    rsi = add(rs, 'rightsStatementIdentifier')
    add_text(rsi, 'rightsStatementIdentifierType', next((v for k,v in pairs if k=='rt.rightsStatementIdentifierType' and str(v).strip()), ""))
    add_text(rsi, 'rightsStatementIdentifierValue', next((v for k,v in pairs if k=='rt.rightsStatementIdentifierValue' and str(v).strip()), ""))

    add_text(rs, 'rightsBasis', next((v for k,v in pairs if k=='rt.rightsBasis' and str(v).strip()), ""))

    cs = next((v for k,v in pairs if k=='rt.copyrightInformation.copyrightStatus' and str(v).strip()), "")
    cj = next((v for k,v in pairs if k=='rt.copyrightInformation.copyrightJurisdiction' and str(v).strip()), "")
    if cs or cj or next((v for k,v in pairs if k=='rt.copyrightInformation.copyrightStatusDeterminationDate' and str(v).strip()), "") or \
       next((v for k,v in pairs if k=='rt.copyrightInformation.copyrightNote' and str(v).strip()), "") or \
       next((v for k,v in pairs if k=='rt.copyrightInformation.copyrightDocumentationIdentifierType' and str(v).strip()), ""):
        ci = add(rs, 'copyrightInformation')
        add_text(ci, 'copyrightStatus', cs)
        add_text(ci, 'copyrightJurisdiction', cj)
        add_text(ci, 'copyrightStatusDeterminationDate', next((v for k,v in pairs if k=='rt.copyrightInformation.copyrightStatusDeterminationDate' and str(v).strip()), ""))
        for n in collect_multival(pairs, 'rt.copyrightInformation.copyrightNote'):
            add_text(ci, 'copyrightNote', n)
        docs = collect_blocks(pairs, [
            'rt.copyrightInformation.copyrightDocumentationIdentifierType',
            'rt.copyrightInformation.copyrightDocumentationIdentifierValue',
            'rt.copyrightInformation.copyrightDocumentationRole',
        ])
        for b in docs:
            cdi = add(ci, 'copyrightDocumentationIdentifier')
            add_text(cdi, 'copyrightDocumentationIdentifierType', b['rt.copyrightInformation.copyrightDocumentationIdentifierType'])
            add_text(cdi, 'copyrightDocumentationIdentifierValue', b['rt.copyrightInformation.copyrightDocumentationIdentifierValue'])
            add_text(cdi, 'copyrightDocumentationRole', b['rt.copyrightInformation.copyrightDocumentationRole'])
        cad_s = next((v for k,v in pairs if k=='rt.copyrightInformation.copyrightApplicableDates.startDate' and str(v).strip()), "")
        cad_e = next((v for k,v in pairs if k=='rt.copyrightInformation.copyrightApplicableDates.endDate' and str(v).strip()), "")
        if cad_s or cad_e:
            cad = add(ci, 'copyrightApplicableDates')
            add_text(cad, 'startDate', cad_s)
            add_text(cad, 'endDate', cad_e)

    if next((v for k,v in pairs if k=='rt.licenseInformation.licenseTerms' and str(v).strip()), "") or \
       next((v for k,v in pairs if k=='rt.licenseInformation.licenseDocumentationIdentifierType' and str(v).strip()), "") or \
       collect_multival(pairs, 'rt.licenseInformation.licenseNote'):
        li = add(rs, 'licenseInformation')
        ldis = collect_blocks(pairs, [
            'rt.licenseInformation.licenseDocumentationIdentifierType',
            'rt.licenseInformation.licenseDocumentationIdentifierValue',
            'rt.licenseInformation.licenseDocumentationRole',
        ])
        for b in ldis:
            ldi = add(li, 'licenseDocumentationIdentifier')
            add_text(ldi, 'licenseDocumentationIdentifierType', b['rt.licenseInformation.licenseDocumentationIdentifierType'])
            add_text(ldi, 'licenseDocumentationIdentifierValue', b['rt.licenseInformation.licenseDocumentationIdentifierValue'])
            add_text(ldi, 'licenseDocumentationRole', b['rt.licenseInformation.licenseDocumentationRole'])
        add_text(li, 'licenseTerms', next((v for k,v in pairs if k=='rt.licenseInformation.licenseTerms' and str(v).strip()), ""))
        for n in collect_multival(pairs, 'rt.licenseInformation.licenseNote'):
            add_text(li, 'licenseNote', n)
        lad_s = next((v for k,v in pairs if k=='rt.licenseInformation.licenseApplicableDates.startDate' and str(v).strip()), "")
        lad_e = next((v for k,v in pairs if k=='rt.licenseInformation.licenseApplicableDates.endDate' and str(v).strip()), "")
        if lad_s or lad_e:
            lad = add(li, 'licenseApplicableDates')
            add_text(lad, 'startDate', lad_s)
            add_text(lad, 'endDate', lad_e)

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
    ], accumulate_last=True)
    for b in stats:
        si = add(rs, 'statuteInformation')
        add_text(si, 'statuteJurisdiction', b['rt.statuteInformation.statuteJurisdiction'])
        add_text(si, 'statuteCitation', b['rt.statuteInformation.statuteCitation'])
        add_text(si, 'statuteInformationDeterminationDate', b['rt.statuteInformation.statuteInformationDeterminationDate'])
        if b['rt.statuteInformation.statuteNote']:
            for n in b['rt.statuteInformation.statuteNote'].split(' | '):
                add_text(si, 'statuteNote', n.strip())
        if b['rt.statuteInformation.statuteDocumentationIdentifierType'] and b['rt.statuteInformation.statuteDocumentationIdentifierValue']:
            sdi = add(si, 'statuteDocumentationIdentifier')
            add_text(sdi, 'statuteDocumentationIdentifierType', b['rt.statuteInformation.statuteDocumentationIdentifierType'])
            add_text(sdi, 'statuteDocumentationIdentifierValue', b['rt.statuteInformation.statuteDocumentationIdentifierValue'])
            add_text(sdi, 'statuteDocumentationRole', b['rt.statuteInformation.statuteDocumentationRole'])
        if b['rt.statuteInformation.statuteApplicableDates.startDate'] or b['rt.statuteInformation.statuteApplicableDates.endDate']:
            sad = add(si, 'statuteApplicableDates')
            add_text(sad, 'startDate', b['rt.statuteInformation.statuteApplicableDates.startDate'])
            add_text(sad, 'endDate', b['rt.statuteInformation.statuteApplicableDates.endDate'])

    if next((v for k,v in pairs if k=='rt.otherRightsInformation.otherRightsBasis' and str(v).strip()), "") or \
       next((v for k,v in pairs if k=='rt.otherRightsInformation.otherRightsDocumentationIdentifierType' and str(v).strip()), ""):
        ori = add(rs, 'otherRightsInformation')
        add_text(ori, 'otherRightsBasis', next((v for k,v in pairs if k=='rt.otherRightsInformation.otherRightsBasis' and str(v).strip()), ""))
        ord_s = next((v for k,v in pairs if k=='rt.otherRightsInformation.otherRightsApplicableDates.startDate' and str(v).strip()), "")
        ord_e = next((v for k,v in pairs if k=='rt.otherRightsInformation.otherRightsApplicableDates.endDate' and str(v).strip()), "")
        if ord_s or ord_e:
            ordx = add(ori, 'otherRightsApplicableDates')
            add_text(ordx, 'startDate', ord_s)
            add_text(ordx, 'endDate', ord_e)
        for n in collect_multival(pairs, 'rt.otherRightsInformation.otherRightsNote'):
            add_text(ori, 'otherRightsNote', n)
        odis = collect_blocks(pairs, [
            'rt.otherRightsInformation.otherRightsDocumentationIdentifierType',
            'rt.otherRightsInformation.otherRightsDocumentationIdentifierValue',
            'rt.otherRightsInformation.otherRightsDocumentationRole',
        ])
        for b in odis:
            odi = add(ori, 'otherRightsDocumentationIdentifier')
            add_text(odi, 'otherRightsDocumentationIdentifierType', b['rt.otherRightsInformation.otherRightsDocumentationIdentifierType'])
            add_text(odi, 'otherRightsDocumentationIdentifierValue', b['rt.otherRightsInformation.otherRightsDocumentationIdentifierValue'])
            add_text(odi, 'otherRightsDocumentationRole', b['rt.otherRightsInformation.otherRightsDocumentationRole'])

    grants = collect_blocks(pairs, [
        'rt.rightsGranted.act',
        'rt.rightsGranted.restriction',
        'rt.rightsGranted.termOfGrant.startDate',
        'rt.rightsGranted.termOfGrant.endDate',
        'rt.rightsGranted.termOfRestriction.startDate',
        'rt.rightsGranted.termOfRestriction.endDate',
        'rt.rightsGranted.rightsGrantedNote',
    ], accumulate_last=True)
    for b in grants:
        rg = add(rs, 'rightsGranted')
        add_text(rg, 'act', b['rt.rightsGranted.act'])
        emit_roles(rg, 'restriction', b['rt.rightsGranted.restriction'])
        if b['rt.rightsGranted.termOfGrant.startDate'] or b['rt.rightsGranted.termOfGrant.endDate']:
            tg = add(rg, 'termOfGrant')
            add_text(tg, 'startDate', b['rt.rightsGranted.termOfGrant.startDate'])
            add_text(tg, 'endDate', b['rt.rightsGranted.termOfGrant.endDate'])
        if b['rt.rightsGranted.termOfRestriction.startDate'] or b['rt.rightsGranted.termOfRestriction.endDate']:
            tr = add(rg, 'termOfRestriction')
            add_text(tr, 'startDate', b['rt.rightsGranted.termOfRestriction.startDate'])
            add_text(tr, 'endDate', b['rt.rightsGranted.termOfRestriction.endDate'])
        emit_roles(rg, 'rightsGrantedNote', b['rt.rightsGranted.rightsGrantedNote'])

    lois = collect_blocks(pairs, [
        'rt.linkingObjectIdentifierType',
        'rt.linkingObjectIdentifierValue',
        'rt.linkingObjectRole',
    ], accumulate_last=True)
    for b in lois:
        loi = add(rs, 'linkingObjectIdentifier')
        add_text(loi, 'linkingObjectIdentifierType', b['rt.linkingObjectIdentifierType'])
        add_text(loi, 'linkingObjectIdentifierValue', b['rt.linkingObjectIdentifierValue'])
        emit_roles(loi, 'linkingObjectRole', b['rt.linkingObjectRole'])

    lais = collect_blocks(pairs, [
        'rt.linkingAgentIdentifierType',
        'rt.linkingAgentIdentifierValue',
        'rt.linkingAgentRole',
    ], accumulate_last=True)
    for b in lais:
        lai = add(rs, 'linkingAgentIdentifier')
        add_text(lai, 'linkingAgentIdentifierType', b['rt.linkingAgentIdentifierType'])
        add_text(lai, 'linkingAgentIdentifierValue', b['rt.linkingAgentIdentifierValue'])
        emit_roles(lai, 'linkingAgentRole', b['rt.linkingAgentRole'])

    for x in collect_multival(pairs, 'rt.rightsExtension'):
        rext = add(rt, 'rightsExtension')
        el = add(rext, 'rightsExtension')
        el.text = x

    return rt
