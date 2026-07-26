from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from job_hunter.application import executar_varredura_mock
from job_hunter.persistence.repository import RepositorioVagas


def criar_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="job-hunter",
        description="Triagem determinística de vagas para o Hermes Agent.",
    )
    parser.add_argument(
        "--workspace",
        type=Path,
        default=Path(os.getenv("JOB_HUNTER_WORKSPACE", "workspace")),
    )
    subcomandos = parser.add_subparsers(dest="comando", required=True)

    scan = subcomandos.add_parser("scan", help="Executa uma varredura de vagas.")
    scan.add_argument("--source", choices=["mock"], default="mock")
    modo = scan.add_mutually_exclusive_group()
    modo.add_argument("--dry-run", dest="dry_run", action="store_true")
    modo.add_argument("--commit", dest="dry_run", action="store_false")
    scan.set_defaults(dry_run=None)

    listar = subcomandos.add_parser("list", help="Lista vagas persistidas.")
    listar.add_argument("--limit", type=int, default=20)
    listar.add_argument(
        "--environment",
        choices=["dry-run", "producao"],
        default="dry-run",
    )
    return parser


def main() -> None:
    argumentos = criar_parser().parse_args()

    if argumentos.comando == "scan":
        resumo = executar_varredura_mock(
            workspace=argumentos.workspace,
            dry_run=argumentos.dry_run,
        )
        print(resumo.model_dump_json(indent=2))
        return

    repositorio = RepositorioVagas(
        argumentos.workspace
        / "state"
        / f"vagas-{argumentos.environment}.db"
    )
    repositorio.inicializar()
    print(
        json.dumps(
            repositorio.listar_recentes(argumentos.limit),
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()

