"""Mapeamento de códigos de origem/destino do Portal para os nomes de rota
usados no padrão do cliente, conforme planilha fornecida pelo cliente.
"""
import re

# Código de origem (numérico ou PBRVx) -> nome padrão do cliente
ORIGEM_MAP = {
    "279725": "F. Viamão (RS)",
    "280304": "BALL Jacareí (SP)",
    "289877": "BALL Três Rios (RJ)",
    "294026": "CAN PACK Itumbiara (GO)",
    "307331": "BALL Frutal (MG)",
    "320622": "BALL Recife (PE)",
    "327858": "BALL Extrema (MG)",
    "PBRV4": "Sete Lagoas (MG) Latas Minas",
}

# Código de destino (PBRxx) -> nome padrão do cliente
DESTINO_MAP = {
    "PBR02": "F. Estancia",
    "PBR04": "F. Camaçari",
    "PBR08": "F. Teresina",
    "PBR11": "F. Maranhão",
    "PBR16": "F. Jacareí",
    "PBR17": "F. Juatuba",
    "PBR18": "F. Itapissuma",
    "PBR19": "F. Nova Rio",
    "PBR21": "F. Lages",
    "PBR23": "F. Jagariúna",
}

_CODE_RE = re.compile(r"([A-Za-z]*\d+[A-Za-z]*\d*)")


def _extract_code(raw: str) -> str:
    """Extrai o código (ex.: '279725' ou 'PBR02') do texto bruto lido no site.
    Aceita formatos como '279725', 'PBR02', '[PBR23]' ou '[PBR23] FAB. JAGUARIUNA - ...'."""
    if not raw:
        return ""
    texto = raw.strip()
    # Se vier entre colchetes, ex.: "[PBR23] FAB. JAGUARIUNA - ..." pega o conteúdo dos colchetes
    colchetes = re.match(r"^\[([^\]]+)\]", texto)
    if colchetes:
        texto = colchetes.group(1)
    match = _CODE_RE.match(texto.strip())
    return match.group(1).upper() if match else texto.strip().upper()


def normalize_origem(raw: str) -> str:
    """Converte o código de origem lido no Portal para o nome padrão do cliente.
    Se o código não estiver mapeado, mantém o texto original."""
    codigo = _extract_code(raw)
    return ORIGEM_MAP.get(codigo, raw.strip() if raw else raw)


def normalize_destino(raw: str) -> str:
    """Converte o código de destino lido no Portal para o nome padrão do cliente.
    Se o código não estiver mapeado, mantém o texto original."""
    codigo = _extract_code(raw)
    return DESTINO_MAP.get(codigo, raw.strip() if raw else raw)
