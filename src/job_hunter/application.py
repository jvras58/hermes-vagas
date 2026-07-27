from __future__ import annotations

import os
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

from job_hunter.discovery.apify_linkedin import (
    ClientePostsApify,
    ExecutorPostsApify,
    FontePostsLinkedInApify,
)
from job_hunter.discovery.mock import FonteVagasMock
from job_hunter.filtering import avaliar_post_linkedin
from job_hunter.persistence.repository import RepositorioVagas
from job_hunter.pipeline import PipelineVagas
from job_hunter.schemas import ResumoExecucao
from job_hunter.settings import carregar_configuracao


def executar_varredura_mock(
    workspace: Path,
    dry_run: bool | None = None,
    agora: datetime | None = None,
) -> ResumoExecucao:
    configuracao = carregar_configuracao(workspace / "inputs" / "config_busca.json")
    modo_dry_run = configuracao.automacao.dry_run if dry_run is None else dry_run
    sufixo = "dry-run" if modo_dry_run else "producao"

    repositorio = RepositorioVagas(workspace / "state" / f"vagas-{sufixo}.db")
    fonte = FonteVagasMock(workspace / "inputs" / "vagas_mock.json")
    raiz_saida = workspace / "outputs" / sufixo
    relogio = (lambda: agora) if agora is not None else None

    return PipelineVagas(
        configuracao=configuracao,
        repositorio=repositorio,
        raiz_saida=raiz_saida,
        dry_run=modo_dry_run,
        relogio=relogio,
    ).executar(fonte)


def executar_varredura_linkedin_posts(
    workspace: Path,
    dry_run: bool | None = None,
    agora: datetime | None = None,
    executor: ExecutorPostsApify | None = None,
) -> ResumoExecucao:
    configuracao = carregar_configuracao(workspace / "inputs" / "config_busca.json")
    if configuracao.linkedin_posts is None or not configuracao.linkedin_posts.ativo:
        raise ValueError("a fonte 'linkedin_posts' não está ativa na configuração")

    modo_dry_run = configuracao.automacao.dry_run if dry_run is None else dry_run
    sufixo = "dry-run" if modo_dry_run else "producao"

    if executor is None:
        executor = _criar_cliente_apify()

    fonte = FontePostsLinkedInApify(configuracao, executor)
    repositorio = RepositorioVagas(workspace / "state" / f"vagas-{sufixo}.db")
    raiz_saida = workspace / "outputs" / sufixo
    relogio = (lambda: agora) if agora is not None else None

    return PipelineVagas(
        configuracao=configuracao,
        repositorio=repositorio,
        raiz_saida=raiz_saida,
        dry_run=modo_dry_run,
        relogio=relogio,
        avaliador=avaliar_post_linkedin,
    ).executar(fonte)


def _criar_cliente_apify() -> ClientePostsApify:
    token = os.getenv("APIFY_TOKEN", "").strip()
    if not token:
        raise ValueError(
            "APIFY_TOKEN não foi definido; configure o .env antes da busca real"
        )

    try:
        limite_custo = Decimal(
            os.getenv("APIFY_MAX_TOTAL_CHARGE_USD", "0.50")
        )
    except InvalidOperation as erro:
        raise ValueError("APIFY_MAX_TOTAL_CHARGE_USD deve ser decimal") from erro

    try:
        timeout_segundos = float(os.getenv("APIFY_TIMEOUT_SECONDS", "240"))
    except ValueError as erro:
        raise ValueError("APIFY_TIMEOUT_SECONDS deve ser numérico") from erro

    return ClientePostsApify(
        token=token,
        actor_id=os.getenv(
            "APIFY_LINKEDIN_POSTS_ACTOR",
            "harvestapi/linkedin-post-search",
        ),
        timeout_segundos=timeout_segundos,
        limite_custo_usd=limite_custo,
    )
