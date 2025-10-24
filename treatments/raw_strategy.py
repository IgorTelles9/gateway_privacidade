from typing import Dict, Any, Optional
from .base_strategy import TreatmentStrategy

class RawStrategy(TreatmentStrategy):
    """ Estratégia de tratamento que permite o encaminhamento dos dados brutos. """

    def execute(self, payload: Dict[str, Any], policy_params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        return payload