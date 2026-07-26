from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

from job_hunter.application import executar_varredura_mock
from job_hunter.persistence.repository import RepositorioVagas


HOST = os.getenv("MCP_HOST", "127.0.0.1")
PORT = int(os.getenv("MCP_PORT", "8000"))
WORKSPACE = Path(os.getenv("JOB_HUNTER_WORKSPACE", "workspace"))

mcp = FastMCP(
    "Hermes Job Hunter",
    host=HOST,
    port=PORT,
    stateless_http=True,
    json_response=True,
)


@mcp.tool()
def scan_mock_vacancies(dry_run: bool = True) -> dict[str, Any]:
    """Executa a fonte simulada sem acessar LinkedIn, Gupy ou Telegram."""
    resumo = executar_varredura_mock(WORKSPACE, dry_run=dry_run)
    return resumo.model_dump(mode="json")


@mcp.tool()
def list_recent_vacancies(
    dry_run: bool = True,
    limit: int = 20,
) -> list[dict[str, Any]]:
    """Lista as vagas já triadas; nunca inicia candidatura ou notificação."""
    ambiente = "dry-run" if dry_run else "producao"
    repositorio = RepositorioVagas(
        WORKSPACE / "state" / f"vagas-{ambiente}.db"
    )
    repositorio.inicializar()
    return repositorio.listar_recentes(limit)


def main() -> None:
    mcp.run(transport="streamable-http")


if __name__ == "__main__":
    main()

