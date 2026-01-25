from dotenv import load_dotenv
from typing import Optional, Dict, Any
import os
load_dotenv()
base_url = os.getenv("MGC_API_URL")
import requests

class MGCAPI:
    def __init__(self):
        self.base_url = base_url

    def get_politica_privacidade(self, titular_id: str, dispositivo_id: str) -> Optional[Dict[str, Any]]:
        try:
            url = f"{self.base_url}/consentimentos/titular/{titular_id}/dispositivo/{dispositivo_id}"
            response = requests.get(url, timeout=5)
            response.raise_for_status() # Lança um erro para status HTTP 4xx/5xx
            consentimento = response.json()
            if consentimento is None:
                return None
            return consentimento
        except requests.RequestException as e:
            print(f"Erro ao buscar políticas de privacidade para o titular {titular_id}: {e}")
            return None