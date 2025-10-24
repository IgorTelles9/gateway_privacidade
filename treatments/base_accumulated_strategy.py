from abc import abstractmethod
from typing import List, Any
from .base_strategy import TreatmentStrategy

class AccumulatedStrategy(TreatmentStrategy):
    """ Class abstrata para todas as estratégias de tratamento que acumulam dados. """

    @abstractmethod
    def calculate_aggregated_data(self, data_points: List[Any]) -> Any:
        """ 
        Calcula os dados agregados a partir dos pontos de dado.
        Args:
            data_points: Uma lista de pontos de dado.
        Returns:
            - Um dicionário com os dados agregados.
        """
        pass