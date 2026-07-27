from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from job_hunter.schemas import (
    AnaliseSemantica,
    MotivoDescarte,
    Plataforma,
    StatusVaga,
    Vaga,
)


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
            conexao.execute(
                """
                CREATE TABLE IF NOT EXISTS analises_semanticas (
                    plataforma TEXT NOT NULL,
                    id_externo TEXT NOT NULL,
                    prompt_version TEXT NOT NULL,
                    curriculo_sha256 TEXT NOT NULL,
                    provedor TEXT NOT NULL,
                    modelo TEXT NOT NULL,
                    score INTEGER NOT NULL,
                    recomendacao TEXT NOT NULL,
                    analisada_em TEXT NOT NULL,
                    analise_json TEXT NOT NULL,
                    PRIMARY KEY (
                        plataforma,
                        id_externo,
                        prompt_version,
                        curriculo_sha256
                    ),
                    FOREIGN KEY (plataforma, id_externo)
                        REFERENCES vagas (plataforma, id_externo)
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

    def obter_vaga_qualificada(
        self,
        plataforma: Plataforma,
        id_externo: str,
    ) -> Vaga | None:
        with self._conectar() as conexao:
            registro = conexao.execute(
                """
                SELECT payload_json
                  FROM vagas
                 WHERE plataforma = ?
                   AND id_externo = ?
                   AND status = ?
                 LIMIT 1
                """,
                (
                    plataforma.value,
                    id_externo,
                    StatusVaga.QUALIFICADA.value,
                ),
            ).fetchone()
        if registro is None:
            return None
        return Vaga.model_validate_json(registro[0])

    def listar_pendentes_analise(
        self,
        prompt_version: str,
        curriculo_sha256: str,
        limite: int = 10,
    ) -> list[Vaga]:
        limite_seguro = min(max(limite, 1), 100)
        with self._conectar() as conexao:
            registros = conexao.execute(
                """
                SELECT v.payload_json
                  FROM vagas AS v
                 WHERE v.status = ?
                   AND NOT EXISTS (
                       SELECT 1
                         FROM analises_semanticas AS a
                        WHERE a.plataforma = v.plataforma
                          AND a.id_externo = v.id_externo
                          AND a.prompt_version = ?
                          AND a.curriculo_sha256 = ?
                   )
                 ORDER BY v.publicada_em DESC
                 LIMIT ?
                """,
                (
                    StatusVaga.QUALIFICADA.value,
                    prompt_version,
                    curriculo_sha256,
                    limite_seguro,
                ),
            ).fetchall()
        return [Vaga.model_validate_json(registro[0]) for registro in registros]

    def registrar_analise(self, analise: AnaliseSemantica) -> None:
        with self._conectar() as conexao:
            conexao.execute(
                """
                INSERT INTO analises_semanticas (
                    plataforma,
                    id_externo,
                    prompt_version,
                    curriculo_sha256,
                    provedor,
                    modelo,
                    score,
                    recomendacao,
                    analisada_em,
                    analise_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(
                    plataforma,
                    id_externo,
                    prompt_version,
                    curriculo_sha256
                ) DO UPDATE SET
                    provedor = excluded.provedor,
                    modelo = excluded.modelo,
                    score = excluded.score,
                    recomendacao = excluded.recomendacao,
                    analisada_em = excluded.analisada_em,
                    analise_json = excluded.analise_json
                """,
                (
                    analise.plataforma.value,
                    analise.id_externo,
                    analise.prompt_version,
                    analise.curriculo_sha256,
                    analise.provedor,
                    analise.modelo,
                    analise.score,
                    analise.recomendacao.value,
                    analise.analisada_em.isoformat(),
                    analise.model_dump_json(),
                ),
            )

    def listar_analises_recentes(
        self,
        limite: int = 20,
    ) -> list[AnaliseSemantica]:
        limite_seguro = min(max(limite, 1), 100)
        with self._conectar() as conexao:
            registros = conexao.execute(
                """
                SELECT analise_json
                  FROM analises_semanticas
                 ORDER BY analisada_em DESC
                 LIMIT ?
                """,
                (limite_seguro,),
            ).fetchall()
        return [
            AnaliseSemantica.model_validate_json(registro[0])
            for registro in registros
        ]

    def listar_analises_por_periodo(
        self,
        inicio: datetime,
        fim: datetime,
        limite: int = 100,
    ) -> list[tuple[Vaga, AnaliseSemantica]]:
        if (
            inicio.tzinfo is None
            or inicio.utcoffset() is None
            or fim.tzinfo is None
            or fim.utcoffset() is None
        ):
            raise ValueError("o período deve conter timezone")
        if fim <= inicio:
            raise ValueError("o fim do período deve ser posterior ao início")

        limite_seguro = min(max(limite, 1), 100)
        with self._conectar() as conexao:
            registros = conexao.execute(
                """
                WITH analises_ordenadas AS (
                    SELECT a.plataforma,
                           a.id_externo,
                           a.analise_json,
                           v.payload_json,
                           ROW_NUMBER() OVER (
                               PARTITION BY a.plataforma, a.id_externo
                               ORDER BY julianday(a.analisada_em) DESC
                           ) AS ordem
                      FROM analises_semanticas AS a
                      JOIN vagas AS v
                        ON v.plataforma = a.plataforma
                       AND v.id_externo = a.id_externo
                     WHERE julianday(a.analisada_em) >= julianday(?)
                       AND julianday(a.analisada_em) < julianday(?)
                )
                SELECT payload_json, analise_json
                  FROM analises_ordenadas
                 WHERE ordem = 1
                 ORDER BY julianday(
                     json_extract(analise_json, '$.analisada_em')
                 ) DESC
                 LIMIT ?
                """,
                (
                    inicio.isoformat(),
                    fim.isoformat(),
                    limite_seguro,
                ),
            ).fetchall()
        return [
            (
                Vaga.model_validate_json(registro[0]),
                AnaliseSemantica.model_validate_json(registro[1]),
            )
            for registro in registros
        ]

    def _conectar(self) -> sqlite3.Connection:
        conexao = sqlite3.connect(self.caminho_banco)
        conexao.execute("PRAGMA foreign_keys = ON")
        return conexao
