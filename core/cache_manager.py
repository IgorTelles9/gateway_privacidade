import redis
import json
from typing import Optional, Dict, Any, List
import os
from dotenv import load_dotenv
import time
load_dotenv()
redis_host = os.getenv("REDIS_HOST")
redis_port = int(os.getenv("REDIS_PORT"))
CACHE_MAX_AGE = int(os.getenv("CACHE_TTL_TIME"))
AGGREGATION_QUEUE_KEY = os.getenv("AGGREGATION_TASK_QUEUE")

class CacheManager:
    def __init__(self):
        try:
            self.redis_client = redis.Redis(
                host=redis_host,
                port=redis_port,
                decode_responses=True,
                db=0
            )
            self.redis_client.ping()
            print("Conexão com Redis estabelecida com sucesso!")
        except redis.exceptions.ConnectionError as e:
            print(f"Erro ao conectar ao Redis: {e}")
            exit(1)
    
    def get_policy(self, dispositivo_id: str, titular_id: str) -> Optional[Dict[str, Any]]:
        """ Busca no cache uma política de privacidade para o dispositivo. """
        key = f"policy:{dispositivo_id}:{titular_id}"
        policy = self.redis_client.get(key)
        if policy:
            print(f"Política de privacidade encontrada no cache para o dispositivo {dispositivo_id} para o titular {titular_id}")
            return json.loads(policy)
        print(f"Política de privacidade não encontrada no cache para o dispositivo {dispositivo_id}")
        return None
    
    def set_policy(self, dispositivo_id: str, titular_id: str, policy: Dict[str, Any]):
        """ Cacheia uma política de privacidade para o dispositivo. """
        key = f"policy:{dispositivo_id}:{titular_id}"
        self.redis_client.setex(key, CACHE_MAX_AGE, json.dumps(policy))
        print(f"Política de privacidade cacheada para o dispositivo {dispositivo_id}")
    
    def invalidate_policy(self, dispositivo_id: str, titular_id: str):
        """ Invalida a política de privacidade do dispositivo. """
        key = f"policy:{dispositivo_id}:{titular_id}"
        deleted_count =self.redis_client.delete(key)
        if deleted_count > 0:
            print(f"Política de privacidade invalidada para o dispositivo {dispositivo_id}")
    
    def add_data_point(self, dispositivo_id: str, titular_id: str, data_point: Any):
        """Adiciona um novo ponto de dado a uma lista para agregação futura."""
        data_key = f"data:{dispositivo_id}:{titular_id}"
        self.redis_client.lpush(data_key, json.dumps(data_point))
        print(f"Ponto de dado adicionado para agregação no dispositivo {dispositivo_id} para o titular {titular_id}.")

    def get_and_clear_data_points(self, dispositivo_id: str, titular_id: str) -> List[Any]:
        """Busca todos os pontos de dados de um dispositivo para um titular e limpa a lista."""
        data_key = f"data:{dispositivo_id}:{titular_id}"
        # A operação 'pipeline' garante que as duas operações (get e delete)
        # sejam executadas de forma atômica, evitando race conditions.
        pipe = self.redis_client.pipeline()
        pipe.lrange(data_key, 0, -1) # Pega todos os elementos da lista
        pipe.delete(data_key)       # Apaga a lista
        results, _ = pipe.execute()
        
        return [json.loads(item) for item in results]
    
    def schedule_aggregation_task(self, device_id: str, titular_id: str, due_timestamp: float):
        """ 
        Agenda uma tarefa de agregação de dados para um dispositivo. 
        """
        self.redis_client.zadd(AGGREGATION_QUEUE_KEY, {f"{device_id}:{titular_id}": due_timestamp})
        print(f"Tarefa de agregação agendada para o dispositivo {device_id}.")

    def get_due_aggregation_tasks(self) -> List[str]:
        """ Retorna as tarefas de agregação que estão vencidas. """
        now = time.time()
        due_tasks = self.redis_client.zrangebyscore(AGGREGATION_QUEUE_KEY, 0, now)
        if due_tasks:
            self.redis_client.zrem(AGGREGATION_QUEUE_KEY, *due_tasks)
        return [task.split(":") for task in due_tasks]

# Singleton
cache_manager = CacheManager()