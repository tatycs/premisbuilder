# agent_builder.py
# -----------------------------------------------------------------------------
# Constrói o elemento <agent> do PREMIS 3.0 a partir de uma linha do CSV.
#
# Um <agent> representa qualquer entidade que participa de eventos de
# preservação: pode ser uma pessoa, uma organização ou um sistema/software.
#
# Campos do CSV reconhecidos por este módulo (prefixo "ag."):
#   ag.agentIdentifierType / ag.agentIdentifierValue  → identificador do agente
#   ag.agentName          → nome(s) do agente (repetível)
#   ag.agentType          → tipo: person | organization | software | hardware
#   ag.agentVersion       → versão (útil para software)
#   ag.agentNote          → nota(s) livre(s) sobre o agente (repetível)
#   ag.agentExtension     → extensão(ões) customizadas (repetível)
#   ag.linkingEventIdentifier.*           → eventos em que o agente participou
#   ag.linkingRightsStatementIdentifier.* → declarações de direito associadas
#   ag.linkingEnvironmentIdentifier.*     → ambientes vinculados (com roles)
# -----------------------------------------------------------------------------

from .utils import add, add_text, collect_blocks, collect_multival, emit_roles


def build_agent(root, pairs):
    """
    Constrói um elemento <agent> PREMIS 3.0 e o adiciona a 'root'.

    Parâmetros:
        root  — elemento XML pai (normalmente o <premis> raiz)
        pairs — lista de tuplas (cabeçalho, valor) de uma linha do CSV

    Retorna o elemento <agent> criado.
    """

    # Cria o contêiner <agent> dentro do elemento raiz
    ag = add(root, 'agent')

    # -------------------------------------------------------------------------
    # 3.1 agentIdentifier (M, R) — Obrigatório e repetível
    # Identifica unicamente o agente. Pode haver mais de um identificador
    # (ex.: identificador interno + identificador externo).
    # Tentamos primeiro coletar blocos Type+Value via collect_blocks;
    # se não houver colunas repetidas, fazemos um fallback com next().
    # -------------------------------------------------------------------------
    aids = collect_blocks(pairs, [
        'ag.agentIdentifierType',
        'ag.agentIdentifierValue',
    ])
    if not aids:
        # Fallback: lê diretamente o primeiro valor não-vazio de cada campo
        t = next((v for k, v in pairs if k == 'ag.agentIdentifierType' and str(v).strip()), "")
        v = next((v for k, v in pairs if k == 'ag.agentIdentifierValue' and str(v).strip()), "")
        if t and v:
            aids = [{'ag.agentIdentifierType': t, 'ag.agentIdentifierValue': v}]

    for b in aids:
        aid = add(ag, 'agentIdentifier')
        add_text(aid, 'agentIdentifierType',  b['ag.agentIdentifierType'])
        add_text(aid, 'agentIdentifierValue', b['ag.agentIdentifierValue'])

    # -------------------------------------------------------------------------
    # 3.2 agentName (O, R) — Opcional e repetível
    # Nome pelo qual o agente é conhecido. Um agente pode ter mais de um nome
    # (ex.: nome completo e nome abreviado). collect_multival coleta todas as
    # ocorrências da coluna "ag.agentName" na linha do CSV.
    # -------------------------------------------------------------------------
    for n in collect_multival(pairs, 'ag.agentName'):
        add_text(ag, 'agentName', n)

    # -------------------------------------------------------------------------
    # 3.3 agentType (O) — Opcional, não repetível
    # Classifica o agente: person, organization, software, hardware, etc.
    # -------------------------------------------------------------------------
    add_text(ag, 'agentType',
             next((v for k, v in pairs if k == 'ag.agentType' and str(v).strip()), ""))

    # -------------------------------------------------------------------------
    # 3.4 agentVersion (O) — Opcional, não repetível
    # Versão do agente — especialmente útil para software (ex.: "7.2.0").
    # -------------------------------------------------------------------------
    add_text(ag, 'agentVersion',
             next((v for k, v in pairs if k == 'ag.agentVersion' and str(v).strip()), ""))

    # -------------------------------------------------------------------------
    # 3.5 agentNote (O, R) — Opcional e repetível
    # Notas livres sobre o agente (ex.: departamento, cargo, observações).
    # -------------------------------------------------------------------------
    for n in collect_multival(pairs, 'ag.agentNote'):
        add_text(ag, 'agentNote', n)

    # -------------------------------------------------------------------------
    # 3.6 agentExtension (O, R) — Opcional e repetível
    # Campo de extensão para metadados que não cabem nos campos padrão PREMIS.
    # -------------------------------------------------------------------------
    for x in collect_multival(pairs, 'ag.agentExtension'):
        add_text(ag, 'agentExtension', x)

    # -------------------------------------------------------------------------
    # 3.7 linkingEventIdentifier (O, R) — Opcional e repetível
    # Aponta para os eventos em que este agente participou.
    # Permite navegar do agente para seus eventos sem varrer todo o XML.
    # -------------------------------------------------------------------------
    leis = collect_blocks(pairs, [
        'ag.linkingEventIdentifier.linkingEventIdentifierType',
        'ag.linkingEventIdentifier.linkingEventIdentifierValue',
    ])
    for b in leis:
        lei = add(ag, 'linkingEventIdentifier')
        add_text(lei, 'linkingEventIdentifierType',
                 b['ag.linkingEventIdentifier.linkingEventIdentifierType'])
        add_text(lei, 'linkingEventIdentifierValue',
                 b['ag.linkingEventIdentifier.linkingEventIdentifierValue'])

    # -------------------------------------------------------------------------
    # 3.8 linkingRightsStatementIdentifier (O, R) — Opcional e repetível
    # Aponta para declarações de direitos associadas a este agente.
    # -------------------------------------------------------------------------
    lrs = collect_blocks(pairs, [
        'ag.linkingRightsStatementIdentifier.linkingRightsStatementIdentifierType',
        'ag.linkingRightsStatementIdentifier.linkingRightsStatementIdentifierValue',
    ])
    for b in lrs:
        lr = add(ag, 'linkingRightsStatementIdentifier')
        add_text(lr, 'linkingRightsStatementIdentifierType',
                 b['ag.linkingRightsStatementIdentifier.linkingRightsStatementIdentifierType'])
        add_text(lr, 'linkingRightsStatementIdentifierValue',
                 b['ag.linkingRightsStatementIdentifier.linkingRightsStatementIdentifierValue'])

    # -------------------------------------------------------------------------
    # 3.9 linkingEnvironmentIdentifier (O, R) — Opcional e repetível
    # Vincula o agente a um ambiente de software/hardware.
    # O role (papel) é repetível dentro do mesmo vínculo, por isso usamos
    # accumulate_last=True para acumular múltiplos roles separados por pipe.
    # -------------------------------------------------------------------------
    leis = collect_blocks(pairs, [
        'ag.linkingEnvironmentIdentifier.linkingEnvironmentIdentifierType',
        'ag.linkingEnvironmentIdentifier.linkingEnvironmentIdentifierValue',
        'ag.linkingEnvironmentIdentifier.linkingEnvironmentRole',
    ], accumulate_last=True)  # acumula roles: "executor | validator"
    for b in leis:
        le = add(ag, 'linkingEnvironmentIdentifier')
        add_text(le, 'linkingEnvironmentIdentifierType',
                 b['ag.linkingEnvironmentIdentifier.linkingEnvironmentIdentifierType'])
        add_text(le, 'linkingEnvironmentIdentifierValue',
                 b['ag.linkingEnvironmentIdentifier.linkingEnvironmentIdentifierValue'])
        # emit_roles divide a string acumulada em múltiplos elementos <linkingEnvironmentRole>
        emit_roles(le, 'linkingEnvironmentRole',
                   b['ag.linkingEnvironmentIdentifier.linkingEnvironmentRole'])

    return ag
