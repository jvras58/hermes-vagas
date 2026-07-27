from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from job_hunter.discovery.base import FonteVagas
from job_hunter.filtering import ResultadoFiltro, avaliar_vaga
from job_hunter.persistence.repository import RepositorioVagas
from job_hunter.reporting import criar_relatorio_triagem
from job_hunter.schemas import ConfiguracaoBusca, ResumoExecucao, StatusVaga, Vaga


TipoAvaliador = Callable[
    [Vaga, ConfiguracaoBusca, datetime],
    ResultadoFiltro,
]


class PipelineVagas:
    def __init__(
        self,
        configuracao: ConfiguracaoBusca,
        repositorio: RepositorioVagas,
        raiz_saida: Path,
        dry_run: bool,
        relogio: Callable[[], datetime] | None = None,
        avaliador: TipoAvaliador | None = None,
    ) -> None:
        self.configuracao = configuracao
        self.repositorio = repositorio
        self.raiz_saida = raiz_saida
        self.dry_run = dry_run
        self.relogio = relogio or (lambda: datetime.now(UTC))
        self.avaliador = avaliador or avaliar_vaga

    def executar(self, fonte: FonteVagas) -> ResumoExecucao:
        agora = self.relogio()
        if agora.tzinfo is None or agora.utcoffset() is None:
            raise ValueError("o relógio do pipeline deve retornar datetime com timezone")

        self.repositorio.inicializar()
        resumo = ResumoExecucao(dry_run=self.dry_run)

        for vaga in fonte.descobrir(agora):
            resumo.descobertas += 1

            if self.repositorio.existe(vaga):
                resumo.duplicadas += 1
                continue

            resultado = self.avaliador(vaga, self.configuracao, agora)
            if not resultado.qualificada:
                resumo.descartadas += 1
                self.repositorio.registrar(
                    vaga,
                    StatusVaga.DESCARTADA,
                    resultado.motivo,
                )
                continue

            resumo.qualificadas += 1
            self.repositorio.registrar(vaga, StatusVaga.QUALIFICADA, None)
            relatorio = criar_relatorio_triagem(
                vaga,
                self.configuracao,
                self.raiz_saida,
                agora,
            )
            resumo.relatorios_gerados.append(str(relatorio))

        return resumo
