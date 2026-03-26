from .utils import add, add_text, collect_blocks, collect_multival, emit_roles

def build_agent(root, pairs):
    ag = add(root, 'agent')

    aids = collect_blocks(pairs, [
        'ag.agentIdentifierType',
        'ag.agentIdentifierValue',
    ])
    if not aids:
        t = next((v for k,v in pairs if k=='ag.agentIdentifierType' and str(v).strip()), "")
        v = next((v for k,v in pairs if k=='ag.agentIdentifierValue' and str(v).strip()), "")
        if t and v:
            aids = [{'ag.agentIdentifierType': t, 'ag.agentIdentifierValue': v}]
    for b in aids:
        aid = add(ag, 'agentIdentifier')
        add_text(aid, 'agentIdentifierType', b['ag.agentIdentifierType'])
        add_text(aid, 'agentIdentifierValue', b['ag.agentIdentifierValue'])

    for n in collect_multival(pairs, 'ag.agentName'):
        add_text(ag, 'agentName', n)

    add_text(ag, 'agentType', next((v for k,v in pairs if k=='ag.agentType' and str(v).strip()), ""))
    add_text(ag, 'agentVersion', next((v for k,v in pairs if k=='ag.agentVersion' and str(v).strip()), ""))

    for n in collect_multival(pairs, 'ag.agentNote'):
        add_text(ag, 'agentNote', n)
    for x in collect_multival(pairs, 'ag.agentExtension'):
        add_text(ag, 'agentExtension', x)

    leis = collect_blocks(pairs, [
        'ag.linkingEventIdentifier.linkingEventIdentifierType',
        'ag.linkingEventIdentifier.linkingEventIdentifierValue',
    ])
    for b in leis:
        lei = add(ag, 'linkingEventIdentifier')
        add_text(lei, 'linkingEventIdentifierType', b['ag.linkingEventIdentifier.linkingEventIdentifierType'])
        add_text(lei, 'linkingEventIdentifierValue', b['ag.linkingEventIdentifier.linkingEventIdentifierValue'])

    lrs = collect_blocks(pairs, [
        'ag.linkingRightsStatementIdentifier.linkingRightsStatementIdentifierType',
        'ag.linkingRightsStatementIdentifier.linkingRightsStatementIdentifierValue',
    ])
    for b in lrs:
        lr = add(ag, 'linkingRightsStatementIdentifier')
        add_text(lr, 'linkingRightsStatementIdentifierType', b['ag.linkingRightsStatementIdentifier.linkingRightsStatementIdentifierType'])
        add_text(lr, 'linkingRightsStatementIdentifierValue', b['ag.linkingRightsStatementIdentifier.linkingRightsStatementIdentifierValue'])

    leis = collect_blocks(pairs, [
        'ag.linkingEnvironmentIdentifier.linkingEnvironmentIdentifierType',
        'ag.linkingEnvironmentIdentifier.linkingEnvironmentIdentifierValue',
        'ag.linkingEnvironmentIdentifier.linkingEnvironmentRole',
    ], accumulate_last=True)
    for b in leis:
        le = add(ag, 'linkingEnvironmentIdentifier')
        add_text(le, 'linkingEnvironmentIdentifierType', b['ag.linkingEnvironmentIdentifier.linkingEnvironmentIdentifierType'])
        add_text(le, 'linkingEnvironmentIdentifierValue', b['ag.linkingEnvironmentIdentifier.linkingEnvironmentIdentifierValue'])
        emit_roles(le, 'linkingEnvironmentRole', b['ag.linkingEnvironmentIdentifier.linkingEnvironmentRole'])

    return ag
