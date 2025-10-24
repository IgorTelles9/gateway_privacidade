import threading
import time
from typing import Any, Dict, List, Optional
import paho.mqtt.client as mqtt
import json
from core.cache_manager import cache_manager
from core.policy_parser import parse_policy_key, parse_time_string
import os
from dotenv import load_dotenv
load_dotenv()
SEND_DATA_TOPIC = os.getenv("TOPICO_DADOS_PROCESSADOS")
from apis import MGCAPI
from treatments.factory import get_treatment_strategy

class Scheduler(threading.Thread):
    def __init__(self, mqtt_client: mqtt.Client):
        super().__init__()
        self.daemon = True
        self._stop_event = threading.Event()
        self.mqtt_client = mqtt_client
        print("Scheduler de agregação de dados iniciado.")\
    
    def stop(self):
        self._stop_event.set()

    def run(self):
        while not self._stop_event.is_set():
            due_tasks = cache_manager.get_due_aggregation_tasks()
            if due_tasks:
                for device_id, titular_id in due_tasks:
                    self._process_aggregation_task(device_id, titular_id)
            time.sleep(2)
    
    def _process_aggregation_task(self, device_id: str, titular_id: str):
        """ Processa uma tarefa de agregação de dados para um dispositivo. """
        policy = self._get_or_fetch_policy(device_id, titular_id)
        if not policy:
            print(f"Nenhuma política de privacidade encontrada para o dispositivo {device_id}.")
            return
        chave_politica = policy.get("opcao_tratamento", {}).get("chave_politica")
        data_points = cache_manager.get_and_clear_data_points(device_id, titular_id)
        if not data_points:
            print(f"Nenhum ponto de dado encontrado para o dispositivo {device_id}.")
            return
        parsed_policy = parse_policy_key(chave_politica)
        if not parsed_policy["action"]:
            print(f"Erro: Dados do dispositivo não contêm ação de tratamento.")
            return
        strategy = get_treatment_strategy(parsed_policy["action"])
        if not strategy:
            print(f"Estratégia de tratamento não encontrada para a chave_politica '{policy.get('opcao_tratamento', {}).get('chave_politica')}'.")
            return
        aggregated_data = strategy.calculate_aggregated_data(data_points)
        if not aggregated_data:
            print(f"Erro ao calcular os dados agregados para o dispositivo {device_id}.")
            return
        result = {
            "dispositivo_id": device_id,
            "titular_id": titular_id,
            "value": aggregated_data
        }
        topic = f"{SEND_DATA_TOPIC}/{device_id}"
        self.mqtt_client.publish(topic, json.dumps(result))
        print(f"Dados agregados encaminhados para o tópico de dados processados: {topic}")
        self._reschedule_aggregation_task(device_id, titular_id, parsed_policy)
    
    def _reschedule_aggregation_task(self, device_id: str, titular_id: str, parsed_policy: Dict[str, Any]):
        interval = parsed_policy["interval"]
        if not interval:
            print(f"Erro: Dados do dispositivo não contêm intervalo de agregação.")
            return
        interval_seconds = parse_time_string(interval)
        if not interval_seconds:
            print(f"Erro: Dados do dispositivo não contêm intervalo de agregação válido.")
            return
        due_timestamp = time.time() + interval_seconds
        cache_manager.schedule_aggregation_task(device_id, titular_id, due_timestamp)
        print(f"Tarefa de agregação agendada para o dispositivo {device_id} para o titular {titular_id}.")

    def _get_or_fetch_policy(self, dispositivo_id: str, titular_id: str) -> Optional[Dict[str, Any]]:
        """ Busca no cache ou no MGC uma política de privacidade para o dispositivo. """
        politica = cache_manager.get_policy(dispositivo_id, titular_id)
        if not politica:
            mgc = MGCAPI()
            politica = mgc.get_politica_privacidade(dispositivo_id, titular_id)
            if politica:
                cache_manager.set_policy(dispositivo_id, titular_id, politica)
        return politica