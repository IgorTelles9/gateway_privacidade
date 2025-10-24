from typing import Any, Dict, Optional, List
from .base_accumulated_strategy import AccumulatedStrategy
from core.cache_manager import cache_manager

class AverageStrategy(AccumulatedStrategy):
    """ Estratégia de tratamento que calcula a média dos dados. """

    def execute(self, payload: Dict[str, Any], policy_params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        device_id = payload.get("dispositivo_id")
        data_point_value = payload.get("value")
        titular_id = payload.get("titular_id")
        if not isinstance(data_point_value, (int, float)):
            print(f"Erro: Valor do ponto de dado não é um número para o dispositivo {device_id}.")
            return None
        cache_manager.add_data_point(device_id, titular_id, data_point_value)
        print(f"Ponto de dado adicionado para agregação no dispositivo {device_id}.")
        return None

    def calculate_aggregated_data(self, data_points: List[Any]) -> Any:
        return sum(data_points) / len(data_points)