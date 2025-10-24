from typing import Any, Dict, Optional
import numpy as np
from .base_strategy import TreatmentStrategy

class GaussianNoiseStrategy(TreatmentStrategy):
    """ Estratégia de tratamento que adiciona ruído gaussiano aos dados. """

    def execute(self, payload: Dict[str, Any], policy_params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        try:
            sigma = float(policy_params.get("sigma", 1.0))
        except:
            sigma = 1.0

        processed_payload = {}
        for key, value in payload.items():
            if isinstance(value, (int, float)):
                noise = np.random.normal(0, sigma)
                processed_payload[key] = value + noise
            else:
                processed_payload[key] = value
        return processed_payload