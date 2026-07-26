from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from job_hunter.schemas import MotivoDescarte, StatusVaga, Vaga


class RepositorioVagas:
    def __init__(self, caminho_banco: Path) -> None:
        self.caminho_banco = caminho_banco

    def inicializar(self) -> None:
        self.caminho_banco.parent.mkdir(parents=True, exist_ok=True)
        with self._conectar() as conexao:
            conexao.execute(
                """
                CREATE TABLE IF NOT EXISTS vagas (
                    plataforma TEXT NOT NULL,
                    id_externo TEXT NOT NULL,
                    url TEXT NOT NULL,
                    status TEXT NOT NULL,
                    motivo_descarte TEXT,
                    publicada_em TEXT NOT NULL,
                    coletada_em TEXT NOT NULL,
                    primeira_visualizacao_em TEXT NOT NULL,
                    ultima_visualizacao_em TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    PRIMARY KEY (plataforma, id_externo)
                )
                """
            )

    def existe(self, vaga: Vaga) -> bool:
        with self._conectar() as conexao:
            registro = conexao.execute(
                """
                SELECT 1
                  FROM vagas
                 WHERE plataforma = ? AND id_externo = ?
                 LIMIT 1
                """,
                vaga.chave_deduplicacao,
            ).fetchone()
        return registro is not None

    def registrar(
        self,
        vaga: Vaga,
        status: StatusVaga,
        motivo: MotivoDescarte | None,
    ) -> None:
        agora = datetime.now(UTC).isoformat()
        with self._conectar() as conexao:
            conexao.execute(
                """
                INSERT INTO vagas (
                    plataforma,
                    id_externo,
                    url,
                    status,
                    motivo_descarte,
                    publicada_em,
                    coletada_em,
                    primeira_visualizacao_em,
                    ultima_visualizacao_em,
                    payload_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(plataforma, id_externo) DO UPDATE SET
                    url = excluded.url,
                    status = excluded.status,
                    motivo_descarte = excluded.motivo_descarte,
                    coletada_em = excluded.coletada_em,
                    ultima_visualizacao_em = excluded.ultima_visualizacao_em,
                    payload_json = excluded.payload_json
                """,
                (
                    vaga.plataforma.value,
                    vaga.id_externo,
                    str(vaga.url),
                    status.value,
                    motivo.value if motivo else None,
                    vaga.publicada_em.isoformat(),
                    vaga.coletada_em.isoformat(),
                    agora,
                    agora,
                    vaga.model_dump_json(),
                ),
            )

    def listar_recentes(self, limite: int = 20) -> list[dict[str, Any]]:
        limite_seguro = min(max(limite, 1), 100)
        with self._conectar() as conexao:
            conexao.row_factory = sqlite3.Row
            registros = conexao.execute(
                """
                SELECT plataforma,
                       id_externo,
                       status,
                       motivo_descarte,
                       publicada_em,
                       ultima_visualizacao_em,
                       payload_json
                  FROM vagas
                 ORDER BY ultima_visualizacao_em DESC
                 LIMIT ?
                """,
                (limite_seguro,),
            ).fetchall()
        return [dict(registro) for registro in registros]

    def _conectar(self) -> sqlite3.Connection:
        return sqlite3.connect(self.caminho_banco)

