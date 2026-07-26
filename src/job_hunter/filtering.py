from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from job_hunter.schemas import ConfiguracaoBusca, MotivoDescarte, Vaga


@dataclass(frozen=True, slots=True)
class ResultadoFiltro:
    qualificada: bool
    motivo: MotivoDescarte | None = None


def avaliar_vaga(
    vaga: Vaga,
    configuracao: ConfiguracaoBusca,
    agora: datetime,
) -> ResultadoFiltro:
    filtros = configuracao.filtros_busca
    idade = agora - vaga.publicada_em

    if idade < timedelta(minutes=-15):
        return ResultadoFiltro(False, MotivoDescarte.DATA_DE_PUBLICACAO_FUTURA)

    if idade > timedelta(hours=filtros.tempo_maximo_publicacao_horas):
        return ResultadoFiltro(False, MotivoDescarte.FORA_DA_JANELA_TEMPORAL)

    if not configuracao.plataformas_ativas.esta_ativa(vaga.plataforma):
        return ResultadoFiltro(False, MotivoDescarte.PLATAFORMA_DESATIVADA)

    texto_vaga = f"{vaga.cargo} {vaga.descricao}".casefold()
    if not any(
        palavra.casefold() in texto_vaga for palavra in filtros.palavras_chave
    ):
        return ResultadoFiltro(
            False,
            MotivoDescarte.PALAVRA_CHAVE_NAO_ENCONTRADA,
        )

    if filtros.localidade.casefold() not in vaga.localidade.casefold():
        return ResultadoFiltro(False, MotivoDescarte.LOCALIDADE_DIVERGENTE)

    if filtros.modalidade.casefold() not in vaga.modalidade.casefold():
        return ResultadoFiltro(False, MotivoDescarte.MODALIDADE_DIVERGENTE)

    return ResultadoFiltro(True)

