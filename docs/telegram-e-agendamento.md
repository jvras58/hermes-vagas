# Telegram e agendamento diário

O Telegram é atendido pelo gateway do Hermes. Não há um segundo bot dentro do
MCP: mensagens recebidas no Telegram usam o mesmo agente, regras e ferramentas
do dashboard. A rotina diária executa uma busca real, analisa as vagas
pendentes, consolida o resultado e anexa `Relatorio_Diario.md`.

Nenhuma candidatura é enviada. As mudanças de currículo são sugestões
vinculadas a fatos `cv-*` e exigem revisão humana.

## 1. Criar e autorizar o bot

1. Abra uma conversa com o `@BotFather` no Telegram.
2. Execute `/newbot`, escolha nome e identificador e copie o token.
3. Obtenha seu ID numérico enviando uma mensagem para `@userinfobot`, método
   recomendado pela documentação do Hermes.
4. Se preferir não usar outro bot, envie uma mensagem ao seu bot, deixe somente
   `TELEGRAM_BOT_TOKEN` preenchido, pare o gateway e consulte `getUpdates` em
   um container temporário, sem imprimir o token:

   ```powershell
   docker compose stop hermes
   docker compose run --rm --no-deps --entrypoint python hermes -c "import json, os, urllib.request; u='https://api.telegram.org/bot'+os.environ['TELEGRAM_BOT_TOKEN']+'/getUpdates'; d=json.load(urllib.request.urlopen(u)); print([(x.get('message',{}).get('from',{}).get('id'), x.get('message',{}).get('from',{}).get('username')) for x in d.get('result',[])])"
   ```

   O primeiro valor de cada par é o ID numérico. Se a lista vier vazia, envie
   outra mensagem ao bot e repita o comando.

Preencha o `.env`:

```dotenv
TELEGRAM_BOT_TOKEN=token-fornecido-pelo-botfather
TELEGRAM_ALLOWED_USERS=123456789
TELEGRAM_HOME_CHANNEL=123456789
TELEGRAM_HOME_CHANNEL_NAME=Jonathas
```

- `TELEGRAM_ALLOWED_USERS` aceita IDs numéricos separados por vírgula;
- `TELEGRAM_HOME_CHANNEL` define para onde o cron entrega o resultado;
- em conversa privada, o ID do canal normalmente é o ID do usuário;
- nunca use nome de usuário no lugar do ID e nunca versione o `.env`.

Recrie o Hermes para carregar as variáveis:

```powershell
docker compose up -d --force-recreate hermes
docker compose logs --tail=100 hermes
```

O gateway usa *long polling*, portanto nenhuma porta do Telegram precisa ser
publicada no host. Envie uma mensagem curta ao bot e confirme que o Hermes
responde.

## 2. Executar o fluxo pelo chat

Para uma rodada imediata de produção, envie pelo dashboard ou Telegram:

```text
Execute uma rodada de produção agora: busque posts do LinkedIn uma vez,
analise semanticamente até o limite configurado e gere o relatório diário.
Inclua o arquivo retornado por build_daily_digest na resposta.
```

Esse pedido autoriza uma chamada real à Apify. O fluxo:

1. executa `scan_linkedin_posts` uma vez;
2. lista até `resumo_diario.maximo_analises_por_execucao` pendências;
3. analisa cada vaga com fatos numerados do currículo;
4. salva score, requisitos, lacunas e sugestões factuais;
5. gera `Relatorio_Diario.md`;
6. devolve `MEDIA:/workspace/.../Relatorio_Diario.md`, que o gateway transforma
   em anexo.

O MCP e o Hermes montam a pasta no mesmo caminho `/workspace`; por isso o
arquivo retornado existe dentro do container responsável pelo Telegram.

## 3. Configurar horário e limite

Edite `workspace/inputs/config_busca.json`:

```json
"resumo_diario": {
  "ativo": true,
  "agendamento_cron": "0 8 * * *",
  "fuso_horario": "America/Recife",
  "maximo_analises_por_execucao": 20
}
```

- `agendamento_cron` usa cinco campos e, no exemplo, significa 08:00 todos os
  dias;
- `fuso_horario` usa um identificador IANA;
- o limite controla quantas vagas pendentes o Hermes pode analisar na rodada;
- `automacao.notificar_via_telegram` também deve permanecer `true`;
- filtros de cargo, tecnologia e consultas continuam em outras seções do mesmo
  JSON e são relidos a cada execução.

O mesmo fuso está configurado em `config/hermes/config.yaml`, para que o
agendador e o relatório concordem sobre a data local.

## 4. Criar a rotina no Hermes

Envie ao Hermes:

```text
Quero configurar a rotina diária do Job Hunter. Use
get_daily_digest_plan, mostre o cron, fuso, limite e custo envolvido e peça
minha confirmação antes de criar o agendamento com entrega no Telegram.
```

O plano MCP apenas lê a configuração; ele não busca vagas e não cria tarefas.
Ele também falha sem token, allowlist numérica explícita ou canal inicial.
Depois de conferir os valores, confirme explicitamente. O Hermes então cria um
cron com entrega `telegram` e usa os parâmetros validados retornados pelo plano.

A confirmação autoriza, a cada execução:

- uma chamada do Actor da Apify, sujeita ao teto
  `APIFY_MAX_TOTAL_CHARGE_USD`;
- chamadas ao modelo NVIDIA para cada vaga pendente analisada;
- geração e envio do relatório diário para o canal configurado.

Para inspecionar, pausar, retomar, executar agora ou remover a rotina, peça ao
Hermes para usar a ferramenta `cronjob`, por exemplo:

```text
Liste meus agendamentos do Job Hunter e mostre status, horário e próxima
execução.
```

```text
Pause a rotina diária do Job Hunter.
```

## 5. Operação

O container `hermes` e a máquina que hospeda o Docker precisam estar ativos no
horário agendado. As sessões do cron são isoladas das conversas, então o prompt
contém o fluxo completo e não depende do histórico do chat.

Os arquivos ficam em:

```text
workspace/outputs/producao/AAAA-MM-DD/
├── Relatorio_Diario.md
└── empresa/
    └── cargo-id/
        ├── Analise_Semantica.json
        ├── Relatorio_Match.txt
        └── Sugestoes_Curriculo.md
```

Editar `config_busca.json` altera o próximo plano e as próximas execuções do
fluxo, mas não reescreve automaticamente um cron já criado. Se cron ou fuso
mudarem, peça ao Hermes para atualizar o agendamento.

## 6. Solução de problemas

### O bot não responde

Confira:

```powershell
docker compose ps
docker compose logs --tail=200 hermes
```

Valide se o token está completo, se o remetente aparece em
`TELEGRAM_ALLOWED_USERS` e se o serviço foi recriado depois da alteração.

### O cron executa, mas não entrega

Confirme `TELEGRAM_HOME_CHANNEL` e peça ao Hermes para listar a execução mais
recente do cron. O canal precisa estar acessível ao bot.

### O relatório aparece no texto, mas não como anexo

O valor final deve começar exatamente com `MEDIA:` e apontar para `/workspace`.
Recrie MCP e Hermes com o Compose atualizado:

```powershell
docker compose up -d --build --force-recreate hermes-init job-hunter-mcp hermes
```

### O relatório está vazio

Isso significa que nenhuma análise semântica foi salva na data local
selecionada. Confira nos logs se a busca falhou, se todos os posts eram
duplicados/descartados ou se o currículo privado estava ausente.

## 7. Referências do Hermes

- [Telegram Gateway](https://hermes-agent.nousresearch.com/docs/user-guide/messaging/telegram)
- [Cron Jobs](https://github.com/NousResearch/hermes-agent/blob/main/website/docs/user-guide/features/cron.md)
- [Configuração e timezone](https://github.com/NousResearch/hermes-agent/blob/main/website/docs/user-guide/configuration.md)
