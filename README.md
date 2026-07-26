# Hermes Job Hunter

Base executável para um agente de triagem de vagas integrado ao Hermes Agent
por MCP. A primeira versão implementa configuração validada, fonte simulada,
filtro temporal de 48 horas, filtros determinísticos, deduplicação em SQLite,
relatórios locais e execução isolada em Docker.

O provedor principal já está configurado como NVIDIA Build/NIM, usando o modelo
`z-ai/glm-5.2`.

LinkedIn, Gupy, análise semântica do currículo, PDF ATS e Telegram ainda não
fazem parte desta primeira entrega.

## Requisitos

- Docker Engine com Docker Compose v2; ou
- Python 3.12+ para executar o núcleo localmente.

## Teste rápido sem Docker

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e .
python -m unittest discover -s tests -v
python -m job_hunter.main scan --source mock --dry-run
```

No PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .
python -m unittest discover -s tests -v
python -m job_hunter.main scan --source mock --dry-run
```

Os resultados de teste ficam separados em:

```text
workspace/state/vagas-dry-run.db
workspace/outputs/dry-run/
```

Para simular uma execução persistente de produção, ainda usando a fonte mock:

```bash
python -m job_hunter.main scan --source mock --commit
```

Esse comando não acessa plataformas, não envia Telegram e não se candidata a
nenhuma vaga. Ele apenas usa `vagas-producao.db` e `outputs/producao/`.

## Execução com Docker e Hermes

1. Crie o arquivo de ambiente:

   ```bash
   cp .env.example .env
   ```

2. Preencha a chave da NVIDIA em `.env`:

   ```dotenv
   NVIDIA_API_KEY=nvapi-sua-chave
   NVIDIA_BASE_URL=https://integrate.api.nvidia.com/v1
   ```

   O arquivo `config/hermes/config.yaml` já aponta para `provider: nvidia` e
   `z-ai/glm-5.2`. A chave nunca deve ser escrita nesse YAML.

3. Opcionalmente, preencha `TELEGRAM_BOT_TOKEN` e
   `TELEGRAM_ALLOWED_USERS`. Durante o desenvolvimento,
   `notificar_via_telegram` permanece `false`.

4. Construa e suba os containers:

   ```bash
   docker compose build
   docker compose up -d
   docker compose logs -f
   ```

5. Abra o painel local em `http://127.0.0.1:9119`.

O MCP não publica porta no host. Ele só é acessível pelo Hermes na rede interna
do Compose. A cada inicialização, `hermes-init` copia `config.yaml` e `SOUL.md`
para o volume persistente do Hermes; portanto, mudanças permanentes nesses dois
arquivos devem ser feitas em `config/hermes/`.

### Validar a NVIDIA antes de subir o Hermes

O teste abaixo usa o mesmo endpoint e modelo, mas limita a resposta a 256 tokens:

```bash
python -m pip install -e ".[providers]"
export NVIDIA_API_KEY="nvapi-sua-chave"
python scripts/check_nvidia.py
```

No PowerShell:

```powershell
python -m pip install -e ".[providers]"
$env:NVIDIA_API_KEY = "nvapi-sua-chave"
python scripts/check_nvidia.py
```

No código Python, use `os.environ["NVIDIA_API_KEY"]` ou `os.getenv(...)`.
Escrever `api_key="$NVIDIA_API_KEY"` passa literalmente o texto
`$NVIDIA_API_KEY` e não lê a variável.

Os parâmetros `temperature`, `top_p`, `max_tokens` e `seed` do exemplo direto
ficam no script de diagnóstico. O Hermes monta suas próprias chamadas de
inferência e atualmente não expõe todos esses parâmetros no `config.yaml`.

O `reasoning_effort` está fixado em `medium`. Não use `ultra` com esse endpoint
sem testar: há um erro conhecido em que a NVIDIA aceita no máximo `max` para
`z-ai/glm-5.2` ([Hermes Agent #69855](https://github.com/NousResearch/hermes-agent/issues/69855)).

Para testar o fluxo diretamente no container:

```bash
docker compose run --rm job-hunter-mcp \
  python -m job_hunter.main scan --source mock --dry-run
```

## Estrutura

```text
.
├── config/hermes/             # Configuração e regras do Hermes
├── src/job_hunter/
│   ├── discovery/             # Fontes de vagas
│   ├── persistence/           # SQLite e deduplicação
│   ├── application.py         # Caso de uso reutilizado pela CLI e MCP
│   ├── filtering.py           # Regras determinísticas
│   ├── mcp_server.py          # Ferramentas expostas ao Hermes
│   ├── pipeline.py            # Orquestração do fluxo
│   ├── reporting.py           # Relatório inicial
│   └── schemas.py             # Contratos validados
├── tests/
└── workspace/
    ├── inputs/
    ├── outputs/
    └── state/
```

## Decisões de segurança

- O MVP bloqueia `auto apply`.
- CAPTCHA ou autenticação adicional sempre exigem intervenção humana.
- O modo `dry-run` usa estado e saída separados da execução persistente.
- Descrições de vagas são tratadas como entrada não confiável.
- Credenciais ficam fora do repositório.
- O currículo futuro poderá reorganizar apenas fatos existentes.

Consulte [spec.md](docs/spec.md) para a arquitetura completa e o cronograma.
