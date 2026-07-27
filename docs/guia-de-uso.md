# Guia de uso

Este guia descreve como configurar, executar e ajustar a busca de posts de
contratação no LinkedIn usando Hermes Job Hunter, Apify e Docker.

## 1. O que funciona atualmente

O fluxo disponível:

1. pesquisa posts públicos de pessoas e empresas pelo Actor da Apify;
2. considera somente posts dentro da janela temporal configurada;
3. exige termos técnicos e indícios de contratação;
4. deduplica os resultados em SQLite;
5. gera `Relatorio_Match.txt` para cada post qualificado;
6. permite ao Hermes comparar requisitos com fatos numerados do currículo;
7. valida evidências, calcula o score e persiste a análise semântica;
8. propõe ajustes rastreáveis sem editar o currículo-base;
9. permite conversar pelo Telegram e entregar um relatório diário agendado.

Esta etapa não acessa a aba formal de vagas do LinkedIn, não envia mensagens a
recrutadores, não gera currículo PDF e não realiza candidatura. A entrega pelo
Telegram é somente a resposta do bot ao usuário autorizado. O currículo real
permanece local e fora do Git.

## 2. Requisitos

- Docker Engine com Docker Compose v2;
- conta e token da Apify;
- chave da NVIDIA Build/NIM;
- bot do Telegram, para chat e entrega agendada;
- Git para atualizar o projeto.

O Actor utilizado é
[`harvestapi/linkedin-post-search`](https://apify.com/harvestapi/linkedin-post-search).
Ele é mantido por terceiros e não é uma integração oficial do LinkedIn.

## 3. Preparar o ambiente

### 3.1 Criar o `.env`

No PowerShell:

```powershell
Copy-Item .env.example .env
```

No Linux ou macOS:

```bash
cp .env.example .env
```

Preencha pelo menos:

```dotenv
NVIDIA_API_KEY=nvapi-sua-chave
NVIDIA_BASE_URL=https://integrate.api.nvidia.com/v1

APIFY_TOKEN=apify_api_seu-token
APIFY_LINKEDIN_POSTS_ACTOR=harvestapi/linkedin-post-search
APIFY_MAX_TOTAL_CHARGE_USD=0.50
APIFY_TIMEOUT_SECONDS=240

TELEGRAM_BOT_TOKEN=token-do-botfather
TELEGRAM_ALLOWED_USERS=123456789
TELEGRAM_HOME_CHANNEL=123456789
TELEGRAM_HOME_CHANNEL_NAME=Jonathas
```

| Variável | Finalidade |
| --- | --- |
| `NVIDIA_API_KEY` | Autentica o modelo usado pelo Hermes |
| `APIFY_TOKEN` | Autoriza a execução do Actor |
| `APIFY_LINKEDIN_POSTS_ACTOR` | Define o Actor permitido |
| `APIFY_MAX_TOTAL_CHARGE_USD` | Limita o custo máximo de cada execução |
| `APIFY_TIMEOUT_SECONDS` | Limita a espera pela resposta da Apify |
| `TELEGRAM_BOT_TOKEN` | Ativa o bot no gateway Hermes |
| `TELEGRAM_ALLOWED_USERS` | Allowlist numérica de remetentes |
| `TELEGRAM_HOME_CHANNEL` | Destino das respostas do cron |
| `TELEGRAM_HOME_CHANNEL_NAME` | Nome legível do destino |

Nunca versione o `.env`.

### 3.2 Criar o currículo privado

No PowerShell:

```powershell
Copy-Item workspace/inputs/curriculo_base.example.md workspace/inputs/curriculo_base.md
```

No Linux ou macOS:

```bash
cp workspace/inputs/curriculo_base.example.md workspace/inputs/curriculo_base.md
```

Substitua todos os placeholders por informações profissionais reais. O arquivo
`curriculo_base.md` é ignorado pelo Git. Não use `git add -f` nele.

### 3.3 Validar a NVIDIA

No PowerShell:

```powershell
uv run --env-file .env python scripts/check_nvidia.py
```

Resultado esperado:

```text
NVIDIA OK
```

### 3.4 Subir os serviços

```powershell
docker compose up -d --build --force-recreate hermes-init job-hunter-mcp hermes
docker compose ps
```

O serviço `hermes-init` é temporário. O estado correto dele depois da cópia das
configurações é `Exited`, enquanto `hermes` e `job-hunter-mcp` devem permanecer
ativos.

Para acompanhar a inicialização:

```powershell
docker compose logs --tail=100 job-hunter-mcp hermes
```

### 3.5 Configurar o acesso ao dashboard

Na primeira inicialização, o Hermes pode recusar o dashboard externo até que a
autenticação seja configurada. O container continua disponível para gerar o
hash.

Entre no container:

```powershell
docker compose exec hermes bash
```

Gere o hash da senha:

```bash
python -c 'from getpass import getpass; from plugins.dashboard_auth.basic import hash_password; print(hash_password(getpass("Senha do dashboard: ")))'
```

Nenhum caractere aparece durante a digitação. Copie o valor `scrypt$...`
retornado e saia com `exit`.

Gere também um segredo para as sessões:

```powershell
uv run python -c 'import secrets; print(secrets.token_hex(32))'
```

Preencha no `.env`:

```dotenv
HERMES_DASHBOARD_BASIC_AUTH_USERNAME=admin
HERMES_DASHBOARD_BASIC_AUTH_PASSWORD_HASH='scrypt$...'
HERMES_DASHBOARD_BASIC_AUTH_SECRET=segredo-hexadecimal-gerado
```

O hash deve ficar inteiro, na mesma linha e entre aspas simples, para que o
Compose não interprete os caracteres `$`.

Recrie o Hermes:

```powershell
docker compose up -d --force-recreate hermes
```

## 4. Configurar os filtros

Todos os filtros editáveis ficam em:

```text
workspace/inputs/config_busca.json
```

O diretório `workspace/` é montado no container. O arquivo é relido em cada
varredura, portanto mudar filtros não exige rebuild nem reinicialização.

### 4.1 Filtros de qualificação

```json
"filtros_busca": {
  "palavras_chave": [
    "Desenvolvedor Python",
    "Engenheiro de Software",
    "Desenvolvedor Frontend",
    "React",
    "Next.js",
    "JavaScript",
    "TypeScript"
  ],
  "localidade": "Brasil",
  "modalidade": "Remoto",
  "tempo_maximo_publicacao_horas": 48
}
```

- `palavras_chave`: termos técnicos aceitos na triagem;
- `localidade`: localidade desejada;
- `modalidade`: modalidade preferida;
- `tempo_maximo_publicacao_horas`: idade máxima do post.

Na fonte atual de posts sociais, localidade e modalidade não são critérios
rígidos de descarte porque frequentemente não aparecem de maneira estruturada.
Para aumentar a precisão, inclua `Brasil`, `remoto` ou termos equivalentes
diretamente nas consultas.

### 4.2 Consultas enviadas ao LinkedIn

```json
"consultas": [
  "\"estamos contratando\" AND (Python OR FastAPI OR Django)",
  "(vaga OR oportunidade) AND (Python OR \"engenheiro de software\")",
  "(vaga OR oportunidade) AND (React OR Next.js OR frontend)",
  "(contratando OR oportunidade) AND (JavaScript OR TypeScript)",
  "(vaga OR contratando) AND (remoto OR \"trabalho remoto\") AND frontend"
]
```

Regras:

- cada consulta aceita no máximo 85 caracteres;
- escreva `AND` e `OR` em maiúsculas;
- use aspas para expressões compostas;
- mantenha consultas relativamente amplas e deixe a triagem local eliminar
  falsos positivos.

### 4.3 Sinais de contratação

```json
"sinais_contratacao": [
  "vaga",
  "vagas",
  "oportunidade",
  "oportunidades",
  "contratando",
  "estamos contratando",
  "processo seletivo",
  "venha para o time",
  "posição aberta"
]
```

Esses sinais evitam que um post puramente técnico sobre React ou Python seja
classificado como oportunidade.

### 4.4 Trocar de área

Ao mudar de Python/frontend para outra área, altere sempre:

1. `filtros_busca.palavras_chave`;
2. `linkedin_posts.consultas`;
3. `linkedin_posts.sinais_contratacao`, somente se o idioma ou os termos de
   recrutamento também mudarem.

Alterar apenas as consultas pode fazer a Apify encontrar posts que serão
descartados posteriormente pelas palavras-chave locais.

## 5. Executar em produção

Para a busca real e persistente:

```powershell
docker compose run --rm job-hunter-mcp python -m job_hunter.main scan --source linkedin-posts --commit
```

O argumento `--commit` significa persistir no ambiente de produção. Ele não
envia candidatura, Telegram ou mensagem ao autor do post.

Exemplo de resumo:

```json
{
  "dry_run": false,
  "descobertas": 20,
  "qualificadas": 4,
  "descartadas": 16,
  "duplicadas": 0,
  "relatorios_gerados": [
    "/workspace/outputs/producao/..."
  ]
}
```

### 5.1 Executar pelo Hermes

Abra:

```text
http://127.0.0.1:9119/auth
```

Envie:

```text
Execute scan_linkedin_posts com dry_run=false e resuma os posts qualificados.
```

Use a CLI ou o Hermes para iniciar a varredura. Se executar os dois em
sequência, a segunda execução encontrará os mesmos IDs e os classificará como
duplicados.

## 6. Consultar os resultados

Pela CLI:

```powershell
docker compose run --rm job-hunter-mcp python -m job_hunter.main list --environment producao --limit 20
```

Pelo Hermes:

```text
Use list_recent_vacancies com dry_run=false e limit=20.
```

Arquivos e estado:

```text
workspace/
├── outputs/
│   └── producao/
│       └── AAAA-MM-DD/
│           └── empresa/
│               └── cargo-id/
│                   └── Relatorio_Match.txt
└── state/
    └── vagas-producao.db
```

O banco registra vagas qualificadas e descartadas. Isso impede que a mesma
publicação gere relatórios repetidos.

## 7. Executar a análise semântica

Depois de uma varredura com `--commit`, abra o painel do Hermes e envie:

```text
Analise semanticamente até 5 vagas pendentes em produção. Para cada vaga,
obtenha o contexto, use somente IDs cv-* como evidência, salve a análise e
resuma o resultado persistido.
```

O Hermes usa quatro ferramentas no fluxo semântico e duas no fluxo diário:

| Ferramenta | Função |
| --- | --- |
| `list_pending_semantic_reviews` | Lista vagas qualificadas ainda não analisadas |
| `get_semantic_analysis_context` | Entrega vaga e fatos numerados do currículo |
| `save_semantic_analysis` | Valida evidências, calcula score e grava o resultado |
| `list_semantic_results` | Consulta análises persistidas |
| `get_daily_digest_plan` | Lê cron, fuso, limite e prompt da rotina |
| `build_daily_digest` | Consolida as análises e prepara o anexo |

O modelo NVIDIA interpreta a vaga. O código Python não faz uma segunda chamada
ao LLM: ele valida IDs `cv-*`, aplica o cálculo determinístico e grava:

```text
workspace/outputs/producao/AAAA-MM-DD/empresa/cargo-id/
├── Analise_Semantica.json
├── Relatorio_Match.txt
└── Sugestoes_Curriculo.md
```

Se o currículo for alterado, seu hash muda e as vagas ficam pendentes para uma
nova análise. Consulte o
[guia específico de análise semântica](analise-semantica.md) para o contrato e
o cálculo do score.

## 8. Telegram e rotina diária

Depois de criar o bot, configurar a allowlist numérica e recriar o Hermes, o
mesmo agente fica disponível no dashboard e no Telegram.

Para uma execução imediata:

```text
Execute uma rodada de produção agora: busque posts do LinkedIn uma vez,
analise semanticamente até o limite configurado e gere o relatório diário.
Inclua o arquivo retornado por build_daily_digest na resposta.
```

A seção `resumo_diario` de `config_busca.json` controla cron, fuso e número
máximo de análises. Para criar a rotina, peça ao Hermes que use
`get_daily_digest_plan`; ele mostra o uso previsto da Apify/NVIDIA e solicita
confirmação antes de criar o cron.

O relatório consolidado fica em:

```text
workspace/outputs/producao/AAAA-MM-DD/Relatorio_Diario.md
```

Consulte [Telegram e agendamento diário](telegram-e-agendamento.md) para criar
o bot, obter o ID, testar anexos e gerenciar o cron.

## 9. Quando usar `dry-run`

O modo `dry-run` serve apenas para diagnóstico e mantém banco e outputs
separados:

```powershell
docker compose run --rm job-hunter-mcp python -m job_hunter.main scan --source linkedin-posts --dry-run
```

Ele ainda executa o Actor e pode consumir créditos da Apify. Para a rotina real,
use `--commit`.

## 10. Alteração de filtros e deduplicação

Filtros novos afetam imediatamente os próximos posts descobertos. Posts já
registrados em `vagas-producao.db`, inclusive os descartados, não são
reprocessados.

Se for realmente necessário refazer toda a triagem, faça primeiro uma cópia
recuperável do banco:

```powershell
docker compose stop job-hunter-mcp
Move-Item workspace/state/vagas-producao.db workspace/state/vagas-producao.backup.db
docker compose up -d job-hunter-mcp
```

Depois execute novamente com `--commit`. Remova o backup somente quando tiver
certeza de que ele não será mais necessário.

## 11. Limites e custos

Na configuração inicial:

- cinco consultas;
- cinco posts por consulta;
- até 25 itens por execução;
- teto de cobrança de US$ 0,50;
- comentários e reações desativados.

O limite de custo é uma proteção, não uma previsão de cobrança. Confira preços e
execuções diretamente no painel da Apify.

## 12. Solução de problemas

### `APIFY_TOKEN não foi definido`

Confirme o token no `.env` e recrie o serviço:

```powershell
docker compose up -d --force-recreate job-hunter-mcp
```

### Nenhum post qualificado

Verifique:

- se as consultas estão restritivas demais;
- se as palavras-chave correspondem à área pesquisada;
- se os posts já aparecem como duplicados;
- se a janela de publicação está pequena demais;
- se o texto contém algum `sinal_contratacao`.

### Ferramenta não aparece no Hermes

Force a cópia da configuração e recrie os serviços:

```powershell
docker compose up -d --force-recreate hermes-init job-hunter-mcp hermes
```

### `currículo-base não encontrado`

Crie a cópia privada descrita na seção 3.2. Se o arquivo existe, confira se o
volume `workspace/` está montado no container MCP.

### `substitua os placeholders`

Edite `curriculo_base.md` e remova todos os textos de exemplo. A análise fecha
com erro para impedir que um currículo fictício gere recomendações.

### Dashboard indisponível

Confira:

```powershell
docker compose logs --tail=100 hermes
```

O log esperado contém:

```text
HERMES_DASHBOARD_READY port=9119
```

### Acompanhar o MCP

```powershell
docker compose logs -f job-hunter-mcp
```

## 13. Segurança

- mantenha tokens apenas no `.env`;
- mantenha `curriculo_base.md` fora do Git;
- não envie cookies ou credenciais do LinkedIn;
- revise os termos aplicáveis antes da coleta;
- não aumente limites sem avaliar o custo;
- permita no Telegram somente IDs numéricos conhecidos;
- confirme o plano antes de ativar uma busca recorrente paga;
- mantenha candidatura e contato sob revisão humana.
