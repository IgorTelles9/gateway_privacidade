from typing import Dict, Any
import re

def parse_policy_key(policy_key: str) -> Dict[str, Any]:
    """
    Analisa a chave_politica completa no formato AÇÃO[:PARAMETROS[:JANELA[:INTERVALO]]].
    Retorna um dicionário estruturado com os componentes da política.
    """
    default = {
        "action": None,
        "params": {},
        "window": None,
        "interval": None
    }
    if not policy_key:
        return default
    parts = policy_key.split(":")
    default["action"] = parts[0]
    if len(parts) >= 2:
        default["params"] = _parser_params(parts[1])
    if len(parts) >= 3:
        default["window"] = int(parts[2])
    if len(parts) >= 4:
        default["interval"] = int(parts[3])
    return default


def _parser_params(params_str: str) -> Dict[str, Any]:
    """ 
    Converte uma string de parâmetros em um dicionário.
    Exemplo: "sigma=0.1,threshold=0.5" -> {"sigma": 0.1, "threshold": 0.5}
    """
    params = {}
    for item in params_str.split(","):
        key, value = item.split("=")
        try:
            value = float(value)
        except:
            value = str(value)
        params[key.strip()] = value
    return params

def parse_time_string(time_str: str) -> int:
    if not isinstance(time_str, str):
        return None
    match = re.match(r'(\d+)([SMH])$', time_str.upper())
    if not match:
        return None
    value = int(match.group(1))
    unit = match.group(2)
    if unit == "S":
        return value
    elif unit == "M":
        return value * 60
    elif unit == "H":
        return value * 3600
    return None