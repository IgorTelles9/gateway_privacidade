from typing import Dict, Any, Optional
from .base_strategy import TreatmentStrategy

class BlockStrategy(TreatmentStrategy):
    """ Estratégia de tratamento que bloqueia o encaminhamento dos dados. """

    def execute(self, payload: Dict[str, Any], policy_params: Dict[str, Any], dispositivo_id: str) -> Optional[Dict[str, Any]]:
        return None