from abc import ABC, abstractmethod
from typing import Dict, Any, Optional

class TreatmentStrategy(ABC):
    """ Class abstrata para todas as estratégias de tratamento. """

    @abstractmethod
    def execute(self, payload: Dict[str, Any], policy_params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """ 
        Executa o tratamento de dados.
        Args:
            payload: Dados recebidos do dispositivo IoT.
            policy: Um dicionário com os parâmetros extraídos da chave_politica.
        Returns:
            - Um dicionário com os dados processados, se os dados devem ser encaminhados.
            - None, se os dados devem ser bloqueados ou estão sendo acumulados para processamento posterior.
        """
        pass