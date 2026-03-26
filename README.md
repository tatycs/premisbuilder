# PREMIS Builder

Ferramenta para gerar arquivos XML no padrão **PREMIS 3.0** a partir de planilhas CSV.

## Por que usar?

O [PREMIS](https://www.loc.gov/standards/premis/) é o padrão internacional de metadados para preservação digital. Embora seja poderoso, criar XML PREMIS manualmente é complexo e propenso a erros. Este programa permite que arquivistas, bibliotecários e pesquisadores criem registros PREMIS usando uma planilha simples — sem precisar escrever XML diretamente.

## Requisitos

- Python 3.9 ou superior
- Sem dependências externas (usa apenas bibliotecas padrão do Python)

## Como usar

```bash
python premis_builder_cli.py entrada.csv saida.xml
```

**Exemplo:**
```bash
python premis_builder_cli.py examples/exemplo.csv saida.xml
```

## Estrutura do CSV

Cada linha do CSV representa uma entidade PREMIS. A coluna `entity` define o tipo:

| Valor      | Entidade PREMIS       |
|------------|-----------------------|
| `object`   | Objeto digital        |
| `event`    | Evento de preservação |
| `agent`    | Agente                |
| `rights`   | Direitos              |

### Prefixos de colunas

| Prefixo | Entidade  |
|---------|-----------|
| `ob.`   | object    |
| `ev.`   | event     |
| `ag.`   | agent     |
| `rt.`   | rights    |

### Principais campos por entidade

#### Object (`ob.`)
| Campo | Descrição |
|-------|-----------|
| `ob.objectIdentifierType` | Tipo do identificador (ex: `documentoID`) |
| `ob.objectIdentifierValue` | Valor do identificador |
| `ob.xsi_type` | Tipo PREMIS: `premis:file`, `premis:representation`, `premis:intellectualEntity` |
| `ob.formatDesignation.formatName` | Nome do formato (ex: `PDF`) |
| `ob.formatDesignation.formatVersion` | Versão do formato (ex: `1.7`) |
| `ob.messageDigestAlgorithm` | Algoritmo de hash (ex: `SHA-512`) |
| `ob.messageDigest` | Valor do hash |
| `ob.size` | Tamanho em bytes |
| `ob.originalName` | Nome original do arquivo |
| `ob.storage.contentLocationType` | Tipo de localização (ex: `URL`) |
| `ob.storage.contentLocationValue` | Endereço/caminho do objeto |
| `ob.relationshipType` | Tipo de relacionamento (ex: `structural`, `reference`) |
| `ob.relationshipSubType` | Subtipo (ex: `includes`, `isIncludedIn`, `documents`) |
| `ob.relatedObjectIdentifierType` | Tipo do identificador do objeto relacionado |
| `ob.relatedObjectIdentifierValue` | Valor do identificador do objeto relacionado |

#### Event (`ev.`)
| Campo | Descrição |
|-------|-----------|
| `ev.eventIdentifierType` | Tipo do identificador |
| `ev.eventIdentifierValue` | Valor do identificador |
| `ev.eventType` | Tipo do evento (ex: `capture`, `sign`, `send`) |
| `ev.eventDateTime` | Data e hora (ISO 8601) |
| `ev.eventDetail` | Descrição do evento |
| `ev.eventOutcome` | Resultado (`success`, `failure`) |
| `ev.eventOutcomeDetailNote` | Nota sobre o resultado |
| `ev.linkingAgentIdentifierType` | Tipo do agente vinculado |
| `ev.linkingAgentIdentifierValue` | Valor do agente vinculado |
| `ev.linkingAgentRole` | Papel do agente (ex: `executor`, `signer`) |
| `ev.linkingObjectIdentifierType` | Tipo do objeto vinculado |
| `ev.linkingObjectIdentifierValue` | Valor do objeto vinculado |

#### Agent (`ag.`)
| Campo | Descrição |
|-------|-----------|
| `ag.agentIdentifierType` | Tipo do identificador |
| `ag.agentIdentifierValue` | Valor do identificador |
| `ag.agentName` | Nome do agente |
| `ag.agentType` | Tipo: `person`, `organization`, `software` |

#### Rights (`rt.`)
| Campo | Descrição |
|-------|-----------|
| `rt.rightsStatementIdentifierType` | Tipo do identificador |
| `rt.rightsStatementIdentifierValue` | Valor do identificador |
| `rt.rightsBasis` | Base dos direitos (ex: `other`, `license`, `statute`) |
| `rt.rightsGranted.act` | Ato autorizado (ex: `access`, `read`) |
| `rt.rightsGranted.restriction` | Restrição aplicada |
| `rt.linkingObjectIdentifierType` | Tipo do objeto ao qual se aplica |
| `rt.linkingObjectIdentifierValue` | Valor do objeto ao qual se aplica |

### Campos repetíveis

Campos repetíveis podem ser representados de duas formas:

1. **Colunas repetidas** com o mesmo nome no cabeçalho
2. **Separados por pipe** (`|`) em uma única célula: `valor1 | valor2 | valor3`

## Exemplo

Veja o arquivo [`examples/exemplo.csv`](examples/exemplo.csv) com um caso completo incluindo objetos, eventos, agentes e direitos.

## Estrutura do projeto

```
premisbuilder/
├── premis_builder_cli.py       # Ponto de entrada (linha de comando)
└── premis_builder/             # Pacote principal
    ├── __init__.py
    ├── cli.py                  # Leitura do CSV e orquestração
    ├── utils.py                # Funções auxiliares e namespaces
    ├── object_builder.py       # Construção de <object>
    ├── event_builder.py        # Construção de <event>
    ├── agent_builder.py        # Construção de <agent>
    └── rights_builder.py       # Construção de <rights>
```

## Referências

- [PREMIS Data Dictionary for Preservation Metadata](https://www.loc.gov/standards/premis/)
- [PREMIS Ontology](https://id.loc.gov/ontologies/premis-3-0-0.html)
