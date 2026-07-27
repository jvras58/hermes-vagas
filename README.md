# Hermes Job Hunter

Base executável para um agente de triagem de vagas integrado ao Hermes Agent
por MCP. A versão atual implementa configuração validada, fonte simulada, busca
de posts públicos de contratação no LinkedIn via Apify HarvestAPI, filtro
temporal de 48 horas, filtros determinísticos, deduplicação em SQLite,
análise semântica rastreável pelo Hermes, relatórios locais e execução isolada
em Docker. O gateway também permite conversar pelo Telegram e entregar um
relatório diário agendado com score, aderência e sugestões factuais para o
currículo.

O provedor principal já está configurado como NVIDIA Build/NIM, usando o modelo
`z-ai/glm-5.2`.

A aba formal de vagas do LinkedIn, Gupy, geração do PDF ATS e candidatura
automática ainda não fazem parte desta entrega.

## Requisitos

- Docker Engine com Docker Compose v2; ou
- Python 3.12+ para executar o núcleo localmente.

## Uso rápido em produção

1. Copie `.env.example` para `.env` e configure `NVIDIA_API_KEY`,
   `APIFY_TOKEN` e, para usar o chat, as variáveis `TELEGRAM_*`.
2. Copie `workspace/inputs/curriculo_base.example.md` para
   `workspace/inputs/curriculo_base.md` e substitua todos os exemplos por fatos
   profissionais reais. O arquivo privado é ignorado pelo Git.
3. Ajuste área, tecnologias e consultas em
   `workspace/inputs/config_busca.json`.
4. Suba `hermes-init`, `job-hunter-mcp` e `hermes`.
5. Execute a busca com `--commit`.
6. Peça ao Hermes para analisar as vagas pendentes ou confirme a criação da
   rotina diária.
7. Consulte os relatórios em `workspace/outputs/producao/` ou receba
   `Relatorio_Diario.md` no Telegram.

```powershell
docker compose up -d --build --force-recreate hermes-init job-hunter-mcp hermes
docker compose run --rm job-hunter-mcp python -m job_hunter.main scan --source linkedin-posts --commit
docker compose run --rm job-hunter-mcp python -m job_hunter.main list --environment producao --limit 20
```

No painel do Hermes:

```text
Analise semanticamente até 5 vagas pendentes em produção. Use apenas fatos
numerados do currículo como evidência e mostre score, recomendação e lacunas.
```

Os filtros são relidos em cada execução, então mudanças em
`config_busca.json` não exigem rebuild. Consulte o
[guia completo de uso](docs/guia-de-uso.md) para configurar filtros, executar
pelo Hermes, entender deduplicação e resolver problemas.

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

3. Para habilitar a busca real de posts do LinkedIn, preencha `APIFY_TOKEN`.
   Para conversar e receber relatórios pelo Telegram, configure também
   `TELEGRAM_BOT_TOKEN`, `TELEGRAM_ALLOWED_USERS` e
   `TELEGRAM_HOME_CHANNEL`. Veja o
   [guia de Telegram e agendamento](docs/telegram-e-agendamento.md).

4. Construa e faça a primeira inicialização dos containers:

   ```bash
   docker compose build
   docker compose up -d
   docker compose logs -f
   ```

Na primeira inicialização, o dashboard pode registrar que recusou o bind em
0.0.0.0. Isso é esperado até que a autenticação seja configurada. O gateway
e o container continuam disponíveis para a geração do hash.

5. Gere o hash da senha do dashboard:

   ```bash
   docker compose exec hermes bash
   ```

   Dentro do container, execute:

   ```bash
   python -c 'from getpass import getpass; from plugins.dashboard_auth.basic import hash_password; print(hash_password(getpass("Senha do dashboard: ")))'
   ```

   Digite a senha desejada e pressione Enter. Por segurança, nenhum caractere
   será exibido enquanto a senha estiver sendo digitada. Copie o hash
   scrypt$... retornado e saia do container:

   ```bash
   exit
   ```

6. Gere um segredo para preservar as sessões do dashboard entre reinicializações:

   ```bash
   uv run python -c 'import secrets; print(secrets.token_hex(32))'
   ```

   Acrescente ao arquivo .env:

   ```text
   # Autenticação do dashboard Hermes.
   HERMES_DASHBOARD_BASIC_AUTH_USERNAME=admin
   HERMES_DASHBOARD_BASIC_AUTH_PASSWORD_HASH='scrypt$...'
   HERMES_DASHBOARD_BASIC_AUTH_SECRET=segredo-hexadecimal-gerado
   ```
   O hash deve ficar inteiro na mesma linha e entre aspas simples. Isso impede
   que o Docker Compose interprete os caracteres $ presentes no hash. Não
   adicione a senha em texto puro nem versione o .env.

7. Recrie o Hermes para carregar as novas variáveis:

   ```bash
   docker compose up -d --force-recreate hermes
   docker compose logs --tail=100 hermes
   ```
   A inicialização correta apresenta:

   ```text
   HERMES_DASHBOARD_READY port=9119
   ```

8. Abra `http://127.0.0.1:9119/auth` e entre com o usuário admin e a senha usada
para gerar o hash.

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

### Testar posts recentes do LinkedIn via Apify

Esta integração pesquisa posts de pessoas e empresas, não a aba formal de vagas
do LinkedIn. Ela usa o Actor
[`harvestapi/linkedin-post-search`](https://apify.com/harvestapi/linkedin-post-search)
e não precisa de cookie ou login do LinkedIn.

O Actor é mantido por um terceiro e não é uma integração oficial do LinkedIn.
Antes de uma execução real, revise os termos da plataforma, a política de
privacidade aplicável e a página do Actor.

Configure no `.env`:

```dotenv
APIFY_TOKEN=apify_api_seu-token
APIFY_LINKEDIN_POSTS_ACTOR=harvestapi/linkedin-post-search
APIFY_MAX_TOTAL_CHARGE_USD=0.50
APIFY_TIMEOUT_SECONDS=240
```

As consultas booleanas ficam em
`workspace/inputs/config_busca.json`, na seção `linkedin_posts`. A configuração
inicial usa cinco consultas e no máximo cinco posts por consulta, limitando a
resposta a 25 itens por execução. O código também envia um teto de cobrança de
US$ 0,50 para a execução.

Recrie os serviços para instalar o cliente e copiar a nova lista de ferramentas
do Hermes:

```bash
docker compose up -d --build --force-recreate \
  hermes-init job-hunter-mcp hermes
```

Para executar uma varredura persistente de produção pela CLI:

```bash
docker compose run --rm job-hunter-mcp \
  python -m job_hunter.main scan --source linkedin-posts --commit
```

O pipeline salva o estado em `vagas-producao.db`, descarta localmente posts com
mais de 48 horas, sem indício de contratação ou sem tecnologia compatível, e
nunca contata o autor nem inicia candidatura.

Como alternativa à CLI, faça a primeira varredura pelo painel do Hermes:

```text
Execute scan_linkedin_posts com dry_run=false e resuma os posts qualificados.
```

Os resultados ficam em `workspace/outputs/producao/` e podem ser consultados
com `list_recent_vacancies` usando `dry_run=false`. Se você já executou a CLI,
peça ao Hermes para listar os resultados em vez de iniciar outra varredura; uma
nova execução classificará os mesmos posts como duplicados.

O modo `dry-run` continua disponível apenas para diagnóstico. Ele usa banco e
outputs separados, mas ainda chama o Actor e pode consumir créditos da Apify.

### Analisar a compatibilidade pelo Hermes

O currículo real não é versionado. Crie a cópia privada antes da primeira
análise:

```powershell
Copy-Item workspace/inputs/curriculo_base.example.md workspace/inputs/curriculo_base.md
```

Preencha o arquivo com fatos reais e remova todos os placeholders. Depois da
varredura em produção, peça ao Hermes:

```text
Analise semanticamente até 5 vagas pendentes em produção. Para cada vaga,
obtenha o contexto, use somente IDs cv-* como evidência, salve a análise e
resuma o resultado persistido.
```

O Hermes, usando o modelo NVIDIA configurado, interpreta os requisitos. O MCP
valida as referências ao currículo, calcula o score e grava
`Analise_Semantica.json`, `Sugestoes_Curriculo.md` e a seção semântica de
`Relatorio_Match.txt`. Alterar o currículo ou
`analise_semantica.prompt_version` faz a vaga voltar à fila de análise sem
apagar resultados anteriores.

Consulte [análise semântica com o Hermes](docs/analise-semantica.md) para o
contrato, cálculo do score e solução de problemas.

### Usar Telegram e relatório diário

O Telegram usa o próprio gateway do Hermes. Depois de configurar o bot e os IDs
numéricos permitidos no `.env`, você pode conversar com o agente normalmente ou
pedir uma rodada completa:

```text
Execute uma rodada de produção agora: busque posts do LinkedIn uma vez,
analise semanticamente até o limite configurado e gere o relatório diário.
Inclua o arquivo retornado por build_daily_digest na resposta.
```

Horário, fuso e limite ficam em `resumo_diario`, dentro de
`workspace/inputs/config_busca.json`. Para criar o cron, peça ao Hermes que use
`get_daily_digest_plan`; ele deve mostrar o plano e pedir confirmação antes de
autorizar chamadas diárias à Apify e à NVIDIA.

Consulte o [guia de Telegram e agendamento](docs/telegram-e-agendamento.md)
para criar o bot, obter o ID numérico, testar o chat e gerenciar a rotina.

## Estrutura

```text
.
├── config/hermes/             # Configuração e regras do Hermes
├── src/job_hunter/
│   ├── discovery/             # Mock e fonte Apify de posts do LinkedIn
│   ├── persistence/           # SQLite e deduplicação
│   ├── application.py         # Caso de uso reutilizado pela CLI e MCP
│   ├── daily_digest.py        # Plano e relatório diário para o Telegram
│   ├── filtering.py           # Regras determinísticas
│   ├── mcp_server.py          # Ferramentas expostas ao Hermes
│   ├── pipeline.py            # Orquestração do fluxo
│   ├── reporting.py           # Relatórios de triagem e análise
│   ├── semantic_analysis.py   # Contexto, evidências, score e persistência
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
- `curriculo_base.md` fica fora do Git; somente o modelo `.example.md` é
  versionado.
- A análise cita fatos numerados e não pode salvar evidências inexistentes.
- O cron real só é criado após confirmação explícita e entrega apenas para o
  canal autorizado.

Consulte o [guia de uso](docs/guia-de-uso.md) para operação e
[spec.md](docs/spec.md) para arquitetura e cronograma.
