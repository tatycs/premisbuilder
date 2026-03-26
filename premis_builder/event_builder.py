from .utils import add, add_text, collect_blocks, collect_multival, emit_roles, normalize_dt, NS, EXT_NS_PREFIX
import xml.etree.ElementTree as ET

def build_event(root, pairs):
    ev = add(root, 'event')

    # 2.1 eventIdentifier (M)
    eid = add(ev, 'eventIdentifier')
    add_text(eid, 'eventIdentifierType',
             next((v for k, v in pairs
                   if k == 'ev.eventIdentifierType' and str(v).strip()), ""))
    add_text(eid, 'eventIdentifierValue',
             next((v for k, v in pairs
                   if k == 'ev.eventIdentifierValue' and str(v).strip()), ""))

    # 2.2 eventType (M) e eventDateTime (M)
    add_text(ev, 'eventType',
             next((v for k, v in pairs
                   if k == 'ev.eventType' and str(v).strip()), ""))
    add_text(ev, 'eventDateTime',
             normalize_dt(next((v for k, v in pairs
                                if k == 'ev.eventDateTime' and str(v).strip()), "")))

    # 2.4 eventDetailInformation (PREMIS 3.0):
    # eventDetail e eventDetailExtension devem ficar dentro de <premis:eventDetailInformation>.
    details = collect_multival(pairs, 'ev.eventDetail')
    exts = collect_multival(pairs, 'ev.eventDetailExtension')

    if details or exts:
        edi = add(ev, 'eventDetailInformation')

        # Um evento pode ter vários eventDetail
        for d in details:
            add_text(edi, 'eventDetail', d)

        # E vários eventDetailExtension
        for x in exts:
            add_text(edi, 'eventDetailExtension', x)

    # 2.5 eventOutcomeInformation (permite múltiplos outcomes)
    outs = collect_multival(pairs, 'ev.eventOutcome') or [""]
    notes = collect_multival(pairs, 'ev.eventOutcomeDetailNote')
    oedx  = collect_multival(pairs, 'ev.eventOutcomeDetailExtension')
    for i, o in enumerate(outs):
        eoi = add(ev, 'eventOutcomeInformation')
        add_text(eoi, 'eventOutcome', o)
        if notes or oedx:
            eod = add(eoi, 'eventOutcomeDetail')
            for n in notes if i == 0 else []:
                add_text(eod, 'eventOutcomeDetailNote', n)
            for x in oedx if i == 0 else []:
                el = add(eod, 'eventOutcomeDetailExtension'); el.text = x

    # 2.6 linkingAgentIdentifier (R), com roles repetíveis
    agents = collect_blocks(pairs, [
        'ev.linkingAgentIdentifierType',
        'ev.linkingAgentIdentifierValue',
        'ev.linkingAgentRole',
    ], accumulate_last=True)
    for b in agents:
        lai = add(ev, 'linkingAgentIdentifier')
        add_text(lai, 'linkingAgentIdentifierType', b['ev.linkingAgentIdentifierType'])
        add_text(lai, 'linkingAgentIdentifierValue', b['ev.linkingAgentIdentifierValue'])
        emit_roles(lai, 'linkingAgentRole', b['ev.linkingAgentRole'])

    # 2.7 linkingObjectIdentifier (R), com roles repetíveis
    lo = collect_blocks(pairs, [
        'ev.linkingObjectIdentifierType',
        'ev.linkingObjectIdentifierValue',
        'ev.linkingObjectIdentifierRole',
    ], accumulate_last=True)
    for b in lo:
        loi = add(ev, 'linkingObjectIdentifier')
        add_text(loi, 'linkingObjectIdentifierType', b['ev.linkingObjectIdentifierType'])
        add_text(loi, 'linkingObjectIdentifierValue', b['ev.linkingObjectIdentifierValue'])
        emit_roles(loi, 'linkingObjectRole', b['ev.linkingObjectIdentifierRole'])

    return ev
