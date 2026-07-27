from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta

from job_hunter.schemas import (
    ConfiguracaoBusca,
    MotivoDescarte,
    Vaga,
)


@dataclass(frozen=True, slots=True)
class ResultadoFiltro:
    qualificada: bool
    motivo: MotivoDescarte | None = None


def avaliar_vaga(
    vaga: Vaga,
    configuracao: ConfiguracaoBusca,
    agora: datetime,
) -> ResultadoFiltro:
    resultado_comum = _avaliar_regras_comuns(vaga, configuracao, agora)
    if resultado_comum is not None:
        return resultado_comum

    filtros = configuracao.filtros_busca
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


def avaliar_post_linkedin(
    vaga: Vaga,
    configuracao: ConfiguracaoBusca,
    agora: datetime,
) -> ResultadoFiltro:
    resultado_comum = _avaliar_regras_comuns(vaga, configuracao, agora)
    if resultado_comum is not None:
        return resultado_comum

    linkedin_posts = configuracao.linkedin_posts
    if linkedin_posts is None or not linkedin_posts.ativo:
        return ResultadoFiltro(False, MotivoDescarte.PLATAFORMA_DESATIVADA)

    texto = f"{vaga.cargo} {vaga.descricao}".casefold()
    if not any(
        _termo_presente(sinal, texto)
        for sinal in linkedin_posts.sinais_contratacao
    ):
        return ResultadoFiltro(False, MotivoDescarte.SEM_INDICIO_CONTRATACAO)

    if not any(
        _frase_ou_token_presente(palavra, texto)
        for palavra in configuracao.filtros_busca.palavras_chave
    ):
        return ResultadoFiltro(
            False,
            MotivoDescarte.PALAVRA_CHAVE_NAO_ENCONTRADA,
        )

    return ResultadoFiltro(True)


def _avaliar_regras_comuns(
    vaga: Vaga,
    configuracao: ConfiguracaoBusca,
    agora: datetime,
) -> ResultadoFiltro | None:
    filtros = configuracao.filtros_busca
    idade = agora - vaga.publicada_em

    if idade < timedelta(minutes=-15):
        return ResultadoFiltro(False, MotivoDescarte.DATA_DE_PUBLICACAO_FUTURA)

    if idade > timedelta(hours=filtros.tempo_maximo_publicacao_horas):
        return ResultadoFiltro(False, MotivoDescarte.FORA_DA_JANELA_TEMPORAL)

    if not configuracao.plataformas_ativas.esta_ativa(vaga.plataforma):
        return ResultadoFiltro(False, MotivoDescarte.PLATAFORMA_DESATIVADA)

    return None


def _frase_ou_token_presente(frase: str, texto: str) -> bool:
    frase_normalizada = frase.casefold()
    if _termo_presente(frase_normalizada, texto):
        return True

    tokens = {
        token
        for token in frase_normalizada.replace("/", " ").replace("-", " ").split()
        if len(token) >= 3
    }
    return any(_termo_presente(token, texto) for token in tokens)


def _termo_presente(termo: str, texto: str) -> bool:
    padrao = rf"(?<!\w){re.escape(termo.casefold())}(?!\w)"
    return re.search(padrao, texto) is not None
