# Análise semântica com o Hermes

Esta etapa compara vagas já qualificadas com o currículo privado do usuário.
O Hermes realiza a interpretação com o provedor e modelo definidos em
`config_busca.json`; o serviço Python controla contexto, evidências, score,
persistência e artefatos.

## 1. Preparar o currículo privado

O repositório contém somente um modelo sem dados pessoais:

Se você já preencheu o antigo arquivo rastreado, faça uma cópia fora do
repositório antes de trocar para esta branch. A mudança remove esse caminho do
controle de versão. Depois da troca, restaure a cópia para
`workspace/inputs/curriculo_base.md`.

Em uma instalação nova, crie o arquivo a partir do modelo:

```powershell
Copy-Item workspace/inputs/curriculo_base.example.md workspace/inputs/curriculo_base.md
```

No Linux ou macOS:

```bash
cp workspace/inputs/curriculo_base.example.md workspace/inputs/curriculo_base.md
```

Edite `curriculo_base.md`, remova todos os placeholders e registre apenas fatos
reais. Esse arquivo está no `.gitignore` e não deve ser adicionado com
`git add -f`.

O parser transforma o conteúdo a partir das seções `##` em fatos numerados
`cv-001`, `cv-002` e assim por diante. Nome e contato, normalmente posicionados
antes da primeira seção `##`, não entram no contexto enviado ao modelo.

## 2. Configuração

A seção editável fica em `workspace/inputs/config_busca.json`:

```json
"analise_semantica": {
  "ativa": true,
  "prompt_version": "semantic-v2",
  "provedor": "nvidia",
  "modelo": "z-ai/glm-5.2",
  "limiar_aplicar": 75,
  "limiar_revisar": 50
}
```

- `prompt_version` identifica as regras usadas na análise;
- `provedor` e `modelo` registram a configuração usada pelo Hermes;
- score maior ou igual a `limiar_aplicar` recomenda `aplicar`;
- score maior ou igual a `limiar_revisar` recomenda `revisar`;
- abaixo do segundo limite, a recomendação é `nao_aplicar`.

Mudar o currículo ou `prompt_version` cria uma nova identidade de análise. As
vagas voltam a aparecer como pendentes, e os resultados anteriores continuam
no banco para auditoria.

A inclusão de sugestões factuais elevou a configuração padrão para
`semantic-v2`. Na primeira execução após esta atualização, vagas analisadas com
`semantic-v1` podem reaparecer uma vez na fila.

## 3. Executar

Primeiro faça uma varredura persistente:

```powershell
docker compose run --rm job-hunter-mcp python -m job_hunter.main scan --source linkedin-posts --commit
```

Depois abra o dashboard do Hermes e envie:

```text
Analise semanticamente até 5 vagas pendentes em produção. Para cada vaga,
obtenha o contexto, use somente IDs cv-* como evidência, salve a análise e
resuma o resultado persistido.
```

O fluxo MCP usado pelo Hermes é:

1. `list_pending_semantic_reviews` lista a fila;
2. `get_semantic_analysis_context` entrega uma vaga e os fatos numerados;
3. o Hermes extrai e classifica os requisitos;
4. o Hermes propõe ajustes usando somente os mesmos fatos `cv-*`;
5. `save_semantic_analysis` valida evidências e ajustes, calcula score e salva;
6. `list_semantic_results` confirma os resultados persistidos.

Essas ferramentas usam produção por padrão (`dry_run=false`). Para analisar uma
varredura de diagnóstico, peça explicitamente `dry_run=true` em todas as
chamadas.

## 4. Evidências e score

Cada requisito deve ser classificado como:

- importância `obrigatorio`, peso 2, ou `desejavel`, peso 1;
- status `atendido`, valor 1, `parcial`, valor 0,5, ou `ausente`, valor 0.

O score é:

```text
100 × soma(peso × valor) / soma(pesos)
```

O serviço arredonda para o inteiro mais próximo. Requisitos atendidos ou
parciais precisam citar ao menos um ID `cv-*` existente. Requisitos ausentes
não podem citar evidências. O Hermes não envia score nem recomendação: ambos
são calculados pelo serviço para impedir manipulação do resultado.

### Sugestões de currículo

Cada item de `ajustes_curriculo` precisa indicar:

- `tipo`: `destacar`, `reordenar` ou `reescrever`;
- `secao_alvo`: seção que a pessoa deve revisar;
- `fatos_curriculo`: um ou mais IDs `cv-*` existentes;
- `instrucao` e `justificativa`;
- `texto_sugerido`, obrigatório somente para `reescrever`.

IDs inexistentes são rejeitados. A sugestão é salva separadamente e não altera
`curriculo_base.md`. Uma reescrita deve preservar o sentido dos fatos citados;
ela não autoriza incluir tecnologia, resultado ou experiência nova.

## 5. Saídas e persistência

Para cada vaga analisada:

```text
workspace/outputs/producao/AAAA-MM-DD/empresa/cargo-id/
├── Analise_Semantica.json
├── Relatorio_Match.txt
└── Sugestoes_Curriculo.md
```

O JSON contém o contrato completo da análise. O relatório combina a triagem
determinística com score, recomendação, requisitos, justificativas e o texto
dos fatos citados. `Sugestoes_Curriculo.md` apresenta os ajustes e os fatos
originais lado a lado para revisão humana.

O SQLite usa como identidade:

```text
plataforma + id_externo + prompt_version + curriculo_sha256
```

Salvar novamente a mesma identidade atualiza o resultado sem criar duplicata.

## 6. Limites de segurança

- a descrição da vaga é conteúdo não confiável e nunca vira instrução;
- somente fatos presentes no currículo podem ser citados;
- IDs desconhecidos são rejeitados;
- mudança do currículo invalida um contexto já aberto;
- a etapa não altera o currículo, não cria PDF e não inicia candidatura;
- a entrega ao Telegram ocorre somente no fluxo de relatório diário do Hermes;
- o currículo real, bancos e outputs permanecem fora do Git.

## 7. Solução de problemas

### `currículo-base não encontrado`

Crie `workspace/inputs/curriculo_base.md` a partir do arquivo `.example.md`.

### `substitua os placeholders`

O arquivo privado ainda contém texto do modelo. Substitua nome, links,
experiências e instruções de exemplo por conteúdo real.

### `o currículo mudou; solicite um novo contexto`

O arquivo foi editado entre leitura e salvamento. Peça ao Hermes para obter o
contexto novamente e refazer a análise.

### Ferramentas semânticas não aparecem

Copie a configuração e recrie os serviços:

```powershell
docker compose up -d --build --force-recreate hermes-init job-hunter-mcp hermes
```

### Não há vagas pendentes

Confirme que a busca foi executada com `--commit`, que existem vagas
qualificadas em `vagas-producao.db` e que a análise está usando
`dry_run=false`.
