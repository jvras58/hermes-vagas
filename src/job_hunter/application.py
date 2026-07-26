from __future__ import annotations

from datetime import datetime
from pathlib import Path

from job_hunter.discovery.mock import FonteVagasMock
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

