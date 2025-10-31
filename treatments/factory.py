from typing import Optional, Union
from .base_strategy import TreatmentStrategy
from .raw_strategy import RawStrategy
from .gaussian_noise_strategy import GaussianNoiseStrategy
from .average_strategy import AverageStrategy
from .base_accumulated_strategy import AccumulatedStrategy

STRATEGY_MAP = {
    "RAW": RawStrategy,
    "GNOISE": GaussianNoiseStrategy,
    "AVG": AverageStrategy,
}

ACCUMULATED_STRATEGY_LIST = ["AVG"]

def get_treatment_strategy(strategy_name: str) -> Optional[Union[TreatmentStrategy | AccumulatedStrategy]]:
    """ Retorna a estratégia de tratamento correspondente ao nome fornecido. """
    strategy_class = STRATEGY_MAP.get(strategy_name.upper())
    if strategy_class:
        return strategy_class()
    return None

def is_accumulated_strategy(strategy_name: str) -> bool:
    """ Verifica se a estratégia é de agregação de dados. """
    return strategy_name.upper() in ACCUMULATED_STRATEGY_LIST