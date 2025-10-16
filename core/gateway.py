import paho.mqtt.client as mqtt
import json
import requests
import time
from typing import Dict, Any, Optional
from dotenv import load_dotenv
import os
from apis import MGCAPI
from core.cache_manager import cache_manager
load_dotenv()

MQTT_HOST = os.getenv("MQTT_HOST")
MQTT_PORT = int(os.getenv("MQTT_PORT"))
NOTIFICATIONS_TOPIC = os.getenv("TOPICO_NOTIFICACOES_MGC")
RECEIVED_DATA_TOPIC  = os.getenv("TOPICO_DADOS_DISPOSITIVOS")
SEND_DATA_TOPIC = os.getenv("TOPICO_DADOS_PROCESSADOS")
CACHE_MAX_AGE = int(os.getenv("CACHE_TTL_TIME"))

politicas_cache: Dict[str, Dict[str, Any]] = {}

class PrivacyGateway:
    def __init__(self):
        self.mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        self.mqtt_client.on_connect = self.on_connect
        self.mqtt_client.on_message = self.on_message
        self.mgc = MGCAPI()
    
    def on_connect(self, client, userdata, flags, reason_code, properties):
        """Callback executado quando a conexão com o broker é estabelecida."""
        if reason_code == 0:
            print("Conectado ao Broker MQTT com sucesso!")
            # Inscreve-se no tópico de notificações do MGC
            client.subscribe(NOTIFICATIONS_TOPIC)
            print(f" -> Inscrito no tópico de notificações: {NOTIFICATIONS_TOPIC}")
            # Inscreve-se nos tópicos de dados dos dispositivos
            client.subscribe(RECEIVED_DATA_TOPIC)
            print(f" -> Inscrito no tópico de dados: {RECEIVED_DATA_TOPIC}")
        else:
            print(f"Falha ao conectar ao broker, código de retorno: {reason_code}")
    
    def on_message(self, client, userdata, msg):
        """Callback executado para cada mensagem recebida."""
        print(f"\nMensagem recebida no tópico '{msg.topic}'")
        
        # Direciona a mensagem para a função de tratamento correta
        if msg.topic == NOTIFICATIONS_TOPIC:
            self.handle_notification(msg.payload)
        elif msg.topic.startswith(RECEIVED_DATA_TOPIC.split("/")[0]):
            self.handle_received_data(msg.topic, msg.payload)
    
    def handle_notification(self, payload):
        """Trata as mensagens de invalidação de cache vindas do MGC."""
        try:
            notificacao = json.loads(payload)
            dispositivo_id = notificacao.get("dispositivo_id") 
            if dispositivo_id:
                print(f"Notificação recebida!")
                cache_manager.invalidate_policy(dispositivo_id)
        except json.JSONDecodeError:
            print("Erro ao decodificar notificação do MGC.")
    
    def handle_received_data(self, topic, payload):
        """Processa os dados recebidos de um dispositivo IoT."""
        try:
            # Extrai o ID do dispositivo do tópico
            dispositivo_id = topic.split('/')[1]
            dados = json.loads(payload)
            titular_id = dados.get("titular_id")
            if not titular_id:
                print("Erro: Dados do dispositivo não contêm titular_id.")
                return

            print(f"Processando dados do dispositivo '{dispositivo_id}': {dados}")

            politica = self._get_or_fetch_policy(dispositivo_id, titular_id)
            if politica:
                chave_politica = politica.get("opcao_tratamento", {}).get("chave_politica")
                # TODO: Executar tratamento
            
                # Logica boba temporaria para testes
                if chave_politica and "RAW" in chave_politica:
                    print(f"DADOS PERMITIDOS. Encaminhando...")
                    # Encaminha o dado para o tópico de dados processados
                    self.mqtt_client.publish(f"{SEND_DATA_TOPIC}/{dispositivo_id}", payload)
                else:
                    print(f"DADOS BLOQUEADOS pela política '{chave_politica}'.")
            else:
                print(f"Nenhuma política de privacidade encontrada para o dispositivo {dispositivo_id}.")
            
        except (IndexError, json.JSONDecodeError):
            print("Erro ao processar dados do dispositivo. Tópico ou payload mal formatado.")
    
    def _get_or_fetch_policy(self, dispositivo_id: str, titular_id: str) -> Optional[Dict[str, Any]]:
        """ Busca no cache ou no MGC uma política de privacidade para o dispositivo. """
        politica = cache_manager.get_policy(dispositivo_id)
        if not politica:
            politica = self.mgc.get_politica_privacidade(dispositivo_id, titular_id)
            if politica:
                cache_manager.set_policy(dispositivo_id, politica)
        return politica

    def start(self):
        """Inicia o cliente MQTT e o loop de escuta."""
        print("Iniciando o Gateway de Privacidade...")
        try:
            self.mqtt_client.connect(MQTT_HOST, MQTT_PORT, 60)
            # loop_forever() é uma chamada bloqueante que mantém o cliente rodando e ouvindo por mensagens.
            self.mqtt_client.loop_forever()
        except ConnectionRefusedError:
            print("Erro fatal: Conexão com o broker MQTT foi recusada. Verifique o host e a porta.")
        except KeyboardInterrupt:
            print("\nGateway de Privacidade encerrado pelo usuário.")
            self.mqtt_client.disconnect()