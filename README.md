## Documentação: Gateway de Privacidade (GP)

### 1\. Visão Geral

O Gateway de Privacidade (GP) é o componente de execução (*enforcement*) do arcabouço de software. Ele atua como um *firewall* de privacidade, posicionando-se entre os dispositivos IoT e os serviços de backend do ecossistema.

Sua responsabilidade primária é interceptar 100% dos dados brutos gerados pelos dispositivos e aplicar as políticas de privacidade e consentimento em tempo real, antes que esses dados sejam encaminhados para qualquer outro serviço.

O GP foi projetado para ser:

  * **Reativo:** Responde instantaneamente a mudanças de consentimento (revogações, concessões) publicadas pelo Módulo de Gerenciamento de Consentimento (MGC).
  * **Performático:** Utiliza um cache de alta velocidade (Redis) para tomar decisões de privacidade com latência quase nula, sem a necessidade de consultar o MGC a cada dado recebido.
  * **Com Estado (*Stateful*):** É capaz de executar políticas de privacidade complexas e temporais, como agregação de dados (ex: "enviar média a cada 10 minutos").
  * **Extensível:** Construído sobre o *Strategy Pattern*, permitindo que novos tratamentos de dados (anonimização, ofuscação, etc.) sejam adicionados sem alterar a lógica central do gateway.

### 2\. Arquitetura e Tecnologias

O GP é um serviço Python independente, construído com foco em resiliência e processamento assíncrono.

  * **Linguagem:** **Python 12**
  * **Mensageria (Core):** **Paho-MQTT**, usado para:
    1.  Receber dados brutos dos dispositivos.
    2.  Receber notificações de invalidação de cache do MGC.
    3.  Publicar dados processados e em conformidade.
  * **Cache e Gerenciamento de Estado:** **Redis**, usado para:
    1.  Armazenar em cache as políticas de privacidade ativas (substituindo o dicionário em memória).
    2.  Acumular dados para processamento temporal (ex: listas de dados para `AVG`).
    3.  Gerenciar a fila de tarefas do Scheduler (via *Sorted Sets*).
  * **Cliente HTTP:** **Requests**, para se comunicar com a API RESTful do MGC quando uma política não está no cache.
  * **Paralelismo:** **Threading**, para rodar o loop principal de ingestão de dados (MQTT) e o loop de processamento temporal (Scheduler) em paralelo.

A arquitetura do código-fonte foi projetada para uma clara separação de responsabilidades (POO):

```
/gateway_privacidade
|-- core/                     # O "cérebro" e orquestração do Gateway
|   |-- __init__.py
|   |-- gateway.py            # Classe PrivacyGateway (Orquestrador principal)
|   |-- cache_manager.py      # Abstração de toda a lógica de comunicação com o Redis
|   |-- policy_parser.py      # Lógica para "traduzir" a chave_politica (ex: AVG:none:10M)
|   `-- scheduler.py          # Lógica do worker de processamento temporal (thread separada)
|
|-- treatments/               # Implementação do Strategy Pattern para tratamentos
|   |-- __init__.py
|   |-- base_strategy.py      # Classe Abstrata: TreatmentStrategy
|   |-- base_accumulated.py   # Classe Abstrata: AccumulatedStrategy (sua contribuição)
|   |-- raw_strategy.py       # Estratégia concreta: RAW
|   |-- gaussian_noise_strategy.py # Estratégia concreta: GNOISE
|   |-- average_strategy.py   # Estratégia concreta: AVG
|   `-- factory.py            # Fábrica para selecionar a estratégia correta
|
|-- apis/                     # (Implícito) Abstração para clientes de API
|   `-- mgc_api.py            # Classe MGCAPI que encapsula chamadas HTTP
|
|-- .venv/                    # Ambiente virtual
|-- main.py                   # Ponto de entrada (instancia e inicia o Gateway)
`-- .env                      # Configurações (hosts, tópicos, credenciais)
```

### 3\. Padrões de Projeto e Lógica Central

A funcionalidade do GP é baseada em três padrões de projeto principais que trabalham em conjunto.

#### a. Strategy Pattern (Padrão de Estratégia)

Esta é a espinha dorsal da lógica de tratamento de dados. Em vez de um `if/elif/else` monolítico no gateway, nós delegamos a responsabilidade do *como* fazer um tratamento para classes de estratégia específicas.

1.  **Interface Base (`TreatmentStrategy`):** Define um contrato comum com um método `execute()`.
2.  **Interface de Acumulação (`AccumulatedStrategy`):** Uma especialização (sua ideia) que herda da base e adiciona um contrato `calculate_aggregated_data()`, separando a lógica de ingestão da lógica de cálculo.
3.  **Estratégias Concretas (`RawStrategy`, `AverageStrategy`):** Classes que implementam as interfaces.
      * `RawStrategy.execute()`: Simplesmente retorna o payload original.
      * `AverageStrategy.execute()`: Adiciona o dado ao Redis e retorna `None`.
      * `AverageStrategy.calculate_aggregated_data()`: Recebe uma lista de dados do Redis e retorna a média.
4.  **Fábrica (`treatments.factory`):** O `Scheduler` e o `Gateway` usam a fábrica (`get_treatment_strategy()`) para obter a instância da estratégia correta com base na `chave_politica`, sem nunca precisarem saber os detalhes da implementação.

#### b. Gerenciamento de Estado com Redis (`CacheManager`)

O `core/cache_manager.py` é o único módulo que "sabe falar" com o Redis. Ele gerencia três tipos distintos de dados:

1.  **Políticas (Cache de Curto Prazo):**
      * **Chave:** `policy:{titular_id}:{dispositivo_id}`
      * **Tipo:** `String` (contendo um JSON da política)
      * **Lógica:** Armazenado com `SETEX` (TTL automático), invalidado pela notificação "push" do MGC.
2.  **Dados Acumulados (Buffer Temporal):**
      * **Chave:** `data:{titular_id}:{dispositivo_id}`
      * **Tipo:** `List`
      * **Lógica:** `AverageStrategy` usa `LPUSH` para adicionar dados. O `Scheduler` usa `LRANGE` e `DEL` para consumir a lista atomicamente.
3.  **Fila de Tarefas (Agendamento):**
      * **Chave:** `tasks:aggregation_due` (definida no `.env`)
      * **Tipo:** `Sorted Set` (Conjunto Ordenado)
      * **Lógica:** O `Scheduler` agenda tarefas com `ZADD`, usando o `timestamp` de execução como "score". Ele consome a fila usando `ZRANGEBYSCORE(0, now)`, pegando todas as tarefas vencidas de uma só vez.

#### c. Processamento Assíncrono (Scheduler)

O GP opera em duas *threads* (linhas de execução) principais para evitar bloqueios:

1.  **Thread Principal (Ingestão de Dados):** O `mqtt_client.loop_forever()` é bloqueante e roda no *foreground*. Sua única função é receber mensagens (dados ou notificações) o mais rápido possível e delegá-las.
2.  **Thread do Scheduler (Processamento Temporal):** O `Scheduler` é uma subclasse de `threading.Thread`. Ele roda em *background* (`self.daemon = True`) em um loop `while` separado.
      * A cada 2 segundos (ou outro intervalo), ele consulta o Redis por tarefas vencidas (`get_due_aggregation_tasks`).
      * Se encontrar tarefas, ele executa a lógica de agregação completa: busca a política, busca os dados acumulados, chama a estratégia (`calculate_aggregated_data`), publica o resultado no MQTT e se reagenda na fila de tarefas.

Isso garante que um cálculo de média de 10.000 pontos de dados não impeça o Gateway de receber novos dados de outros dispositivos.

### 4\. Fluxos de Dados Detalhados

#### Fluxo A: Dado em Tempo Real (Ex: Política `RAW`)

1.  Dispositivo publica no tópico `dispositivos/1/dados`.
2.  GP (`on_message`) recebe.
3.  `handle_received_data` é chamado.
4.  `_get_or_fetch_policy` busca a política no `CacheManager`.
      * *Cache Miss:* `MGCAPI.get_politica_privacidade()` é chamado, busca na API do MGC, e o resultado é salvo no Redis pelo `CacheManager.set_policy()`.
      * *Cache Hit:* `CacheManager.get_policy()` retorna o JSON da política.
5.  `_apply_policy` é chamado com a política.
6.  `parse_policy_key` traduz a `chave_politica`.
7.  `get_treatment_strategy("RAW")` retorna uma instância de `RawStrategy`.
8.  `RawStrategy.execute()` é chamado e retorna o payload original.
9.  Como o `execute()` retornou dados, o GP os publica no tópico `dados_processados/1`.

#### Fluxo B: Dado Agregado (Ex: Política `AVG:none:10M:10M`)

1.  **Ingestão do Dado (Thread Principal):**

    1.  Dispositivo publica no tópico `dispositivos/1/dados`.
    2.  `handle_received_data` -\> `_get_or_fetch_policy` (Busca/salva a política `AVG`).
    3.  *(Na 1ª vez)* `_kickstart_aggregation_task` é chamado. Ele vê que a política é `AVG`, calcula `agora + 10 minutos` e chama `cache_manager.schedule_aggregation_task()`, adicionando a tarefa à fila do Redis.
    4.  `_apply_policy` -\> `get_treatment_strategy("AVG")` -\> `AverageStrategy.execute()` é chamado.
    5.  `AverageStrategy` chama `cache_manager.add_data_point()` para salvar o dado na lista do Redis.
    6.  `AverageStrategy.execute()` retorna `None`.
    7.  O GP vê `None` e **não publica nada**. O fluxo de ingestão termina aqui.

2.  **Processamento da Média (Thread do Scheduler):**

    1.  *(10 minutos depois)* A `Scheduler.run()` acorda.
    2.  `cache_manager.get_due_aggregation_tasks()` consulta o Redis (`ZRANGEBYSCORE`) e encontra a tarefa `1:1`.
    3.  `_process_aggregation_task` é chamado.
    4.  `cache_manager.get_and_clear_data_points()` busca a lista de dados e a apaga.
    5.  `get_treatment_strategy("AVG")` é chamado.
    6.  `AverageStrategy.calculate_aggregated_data()` é chamado com a lista de dados, calcula a média e a retorna.
    7.  O Scheduler publica o resultado (a média) no tópico `dados_processados/1/avg`.
    8.  `_reschedule_aggregation_task` é chamado. Ele lê o intervalo "10M" da política, calcula `agora + 10 minutos` e chama `cache_manager.schedule_aggregation_task()`, colocando a tarefa de volta na fila para o próximo ciclo.

### 5\. Configuração e Execução

1.  **Variáveis de Ambiente:** Crie um arquivo `.env` na raiz do projeto com as seguintes variáveis:
      * `MQTT_HOST`, `MQTT_PORT` (do broker MQTT)
      * `MGC_API_URL` (da API do MGC)
      * `TOPICO_NOTIFICACOES_MGC` (ex: `politicas/atualizacoes`)
      * `TOPICO_DADOS_DISPOSITIVOS` (ex: `dispositivos/+/dados`)
      * `TOPICO_DADOS_PROCESSADOS` (ex: `dados_processados`)
      * `CACHE_TTL_TIME` (em segundos, ex: `900`)
      * `AGGREGATION_QUEUE_KEY` (ex: `tasks:aggregation_due`)
2.  **Instalação:** `uv pip install -r requirements.txt` (assumindo a existência do arquivo).
3.  **Serviços de Dependência:** Garanta que o **MGC**, o **Redis** (container Docker) e o **Broker MQTT** (local) estejam em execução.
4.  **Execução:** Execute `python main.py` para iniciar o Gateway de Privacidade.