from __future__ import annotations

import os
from collections import Counter
from collections.abc import Callable
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from job_hunter.persistence.repository import RepositorioVagas
from job_hunter.schemas import AnaliseSemantica, RecomendacaoAnalise, Vaga
from job_hunter.settings import carregar_configuracao


class ErroResumoDiario(ValueError):
    pass


class ServicoResumoDiario:
    def __init__(
        self,
        workspace: Path,
        dry_run: bool = False,
        relogio: Callable[[], datetime] | None = None,
    ) -> None:
        self.workspace = workspace
        self.dry_run = dry_run
        self.relogio = relogio or (lambda: datetime.now(UTC))
        configuracao = carregar_configuracao(workspace / "inputs" / "config_busca.json")
        if configuracao.resumo_diario is None:
            raise ErroResumoDiario(
                "'resumo_diario' não está configurado em config_busca.json"
            )
        if not configuracao.resumo_diario.ativo:
            raise ErroResumoDiario(
                "o resumo diário está desativado em config_busca.json"
            )
        if (
            configuracao.analise_semantica is None
            or not configuracao.analise_semantica.ativa
        ):
            raise ErroResumoDiario(
                "a análise semântica deve estar ativa para gerar o resumo diário"
            )

        self.configuracao = configuracao.resumo_diario
        self.configuracao_analise = configuracao.analise_semantica
        self.notificar_via_telegram = configuracao.automacao.notificar_via_telegram
        self.fuso_horario = ZoneInfo(self.configuracao.fuso_horario)
        self.ambiente = "dry-run" if dry_run else "producao"
        self.repositorio = RepositorioVagas(
            workspace / "state" / f"vagas-{self.ambiente}.db"
        )
        self.repositorio.inicializar()
        self.raiz_saida = workspace / "outputs" / self.ambiente

    def obter_plano_agendamento(self) -> dict[str, Any]:
        if not self.notificar_via_telegram:
            raise ErroResumoDiario(
                "'automacao.notificar_via_telegram' deve estar true para "
                "agendar a entrega"
            )
        self._validar_telegram()
        limite = self.configuracao.maximo_analises_por_execucao
        prompt = f"""Execute uma rodada diária do Hermes Job Hunter em produção.

1. Chame scan_linkedin_posts com dry_run=false exatamente uma vez.
2. Chame list_pending_semantic_reviews com dry_run=false e limit={limite}.
3. Para cada vaga retornada, uma por vez, obtenha o contexto com
   get_semantic_analysis_context e salve a análise com save_semantic_analysis.
4. Use somente IDs cv-* existentes como evidências. Em ajustes_curriculo,
   proponha apenas destacar, reordenar ou reescrever fatos existentes. Nunca
   invente experiência e nunca altere curriculo_base.md.
5. Ao terminar, chame build_daily_digest com dry_run=false.
6. Responda com um resumo curto dos totais e inclua exatamente o valor
   telegram_media retornado, para anexar Relatorio_Diario.md ao Telegram.

Não se candidate, não contate recrutadores, não crie outro agendamento e não
repita a busca se ocorrer erro. Informe falhas de busca ou análise no resumo."""
        return {
            "ativo": True,
            "agendamento_cron": self.configuracao.agendamento_cron,
            "fuso_horario": self.configuracao.fuso_horario,
            "maximo_analises_por_execucao": limite,
            "provedor": self.configuracao_analise.provedor,
            "modelo": self.configuracao_analise.modelo,
            "cronjob": {
                "action": "create",
                "name": "Job Hunter Diário",
                "schedule": self.configuracao.agendamento_cron,
                "prompt": prompt,
                "deliver": "telegram",
                "workdir": "/workspace",
                "provider": self.configuracao_analise.provedor,
                "model": self.configuracao_analise.modelo,
            },
        }

    @staticmethod
    def _validar_telegram() -> None:
        obrigatorias = (
            "TELEGRAM_BOT_TOKEN",
            "TELEGRAM_ALLOWED_USERS",
            "TELEGRAM_HOME_CHANNEL",
        )
        faltantes = [nome for nome in obrigatorias if not os.getenv(nome, "").strip()]
        if faltantes:
            raise ErroResumoDiario(
                "configure no .env antes de agendar: " + ", ".join(faltantes)
            )

        usuarios = [
            item.strip()
            for item in os.environ["TELEGRAM_ALLOWED_USERS"].split(",")
            if item.strip()
        ]
        if not usuarios or any(
            usuario == "*" or not usuario.isdecimal() for usuario in usuarios
        ):
            raise ErroResumoDiario(
                "TELEGRAM_ALLOWED_USERS deve conter somente IDs numéricos explícitos"
            )
        canal = os.environ["TELEGRAM_HOME_CHANNEL"].strip()
        if not canal.lstrip("-").isdecimal():
            raise ErroResumoDiario("TELEGRAM_HOME_CHANNEL deve ser um ID numérico")

    def gerar(self, data_referencia: str | None = None) -> dict[str, Any]:
        agora = self.relogio()
        if agora.tzinfo is None or agora.utcoffset() is None:
            raise ErroResumoDiario(
                "o relógio do resumo deve retornar datetime com timezone"
            )
        data_local = self._resolver_data(data_referencia, agora)
        inicio_local = datetime.combine(
            data_local,
            time.min,
            tzinfo=self.fuso_horario,
        )
        fim_local = inicio_local + timedelta(days=1)
        resultados = self.repositorio.listar_analises_por_periodo(
            inicio=inicio_local.astimezone(UTC),
            fim=fim_local.astimezone(UTC),
            limite=self.configuracao.maximo_analises_por_execucao,
        )

        diretorio = self.raiz_saida / data_local.isoformat()
        diretorio.mkdir(parents=True, exist_ok=True)
        caminho = diretorio / "Relatorio_Diario.md"
        caminho.write_text(
            self._criar_relatorio(data_local, agora, resultados),
            encoding="utf-8",
        )

        contagens = Counter(analise.recomendacao.value for _, analise in resultados)
        recomendacoes = {
            recomendacao.value: contagens.get(recomendacao.value, 0)
            for recomendacao in RecomendacaoAnalise
        }
        return {
            "data": data_local.isoformat(),
            "fuso_horario": self.configuracao.fuso_horario,
            "ambiente": self.ambiente,
            "total_analisadas": len(resultados),
            "recomendacoes": recomendacoes,
            "relatorio": str(caminho),
            "telegram_media": f"MEDIA:{caminho}",
        }

    def _resolver_data(
        self,
        data_referencia: str | None,
        agora: datetime,
    ) -> date:
        if data_referencia is None:
            return agora.astimezone(self.fuso_horario).date()
        try:
            return date.fromisoformat(data_referencia)
        except ValueError as erro:
            raise ErroResumoDiario("a data deve usar o formato AAAA-MM-DD") from erro

    def _criar_relatorio(
        self,
        data_local: date,
        agora: datetime,
        resultados: list[tuple[Vaga, AnaliseSemantica]],
    ) -> str:
        contagens = Counter(analise.recomendacao.value for _, analise in resultados)
        linhas = [
            f"# Relatório diário de vagas — {data_local.isoformat()}",
            "",
            f"- Ambiente: {self.ambiente}",
            f"- Fuso horário: {self.configuracao.fuso_horario}",
            f"- Gerado em: {agora.astimezone(self.fuso_horario).isoformat()}",
            f"- Vagas analisadas: {len(resultados)}",
            f"- Aplicar: {contagens.get('aplicar', 0)}",
            f"- Revisar: {contagens.get('revisar', 0)}",
            f"- Não aplicar: {contagens.get('nao_aplicar', 0)}",
            "",
            (
                "> O relatório recomenda revisão humana. Nenhuma candidatura "
                "foi enviada e o currículo-base não foi alterado."
            ),
        ]
        if not resultados:
            linhas.extend(
                [
                    "",
                    "Nenhuma análise semântica foi salva nesta data.",
                ]
            )

        for vaga, analise in resultados:
            linhas.extend(
                [
                    "",
                    f"## {analise.score}% — {vaga.cargo}",
                    "",
                    f"- Empresa: {vaga.empresa}",
                    f"- Recomendação: {analise.recomendacao.value}",
                    f"- Plataforma: {vaga.plataforma.value}",
                    f"- Origem: {vaga.origem.value}",
                    (f"- Localidade/modalidade: {vaga.localidade} / {vaga.modalidade}"),
                    (
                        "- Publicada em: "
                        f"{vaga.publicada_em.astimezone(self.fuso_horario).isoformat()}"
                    ),
                    f"- Link: {vaga.url}",
                    (
                        "- Analisada em: "
                        f"{analise.analisada_em.astimezone(self.fuso_horario).isoformat()}"
                    ),
                    "",
                    analise.resumo,
                    "",
                    "### Requisitos",
                ]
            )
            for requisito in analise.requisitos:
                evidencias = (
                    ", ".join(requisito.evidencias_curriculo)
                    if requisito.evidencias_curriculo
                    else "sem evidência"
                )
                linhas.append(
                    f"- **{requisito.status.value}** — "
                    f"{requisito.requisito} "
                    f"({requisito.importancia.value}; {evidencias})"
                )

            linhas.extend(
                [
                    "",
                    "### Pontos fortes",
                    "",
                    ", ".join(analise.pontos_fortes)
                    if analise.pontos_fortes
                    else "Nenhum ponto forte confirmado.",
                    "",
                    "### Lacunas",
                    "",
                    ", ".join(analise.lacunas)
                    if analise.lacunas
                    else "Nenhuma lacuna identificada.",
                    "",
                    "### Palavras-chave ATS",
                    "",
                    ", ".join(analise.palavras_chave_ats)
                    if analise.palavras_chave_ats
                    else "Nenhuma palavra-chave sugerida.",
                    "",
                    "### Ajustes factuais no currículo",
                ]
            )
            if not analise.ajustes_curriculo:
                linhas.extend(["", "Nenhum ajuste proposto."])
            for ajuste in analise.ajustes_curriculo:
                linhas.extend(
                    [
                        "",
                        (
                            f"- **{ajuste.tipo.value} — "
                            f"{ajuste.secao_alvo}:** {ajuste.instrucao}"
                        ),
                        f"  - Fatos: {', '.join(ajuste.fatos_curriculo)}",
                        f"  - Justificativa: {ajuste.justificativa}",
                    ]
                )
                if ajuste.texto_sugerido:
                    linhas.append(f"  - Texto sugerido: {ajuste.texto_sugerido}")

        return "\n".join(linhas).rstrip() + "\n"
