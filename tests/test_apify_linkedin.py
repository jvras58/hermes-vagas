from __future__ import annotations

import json
import tempfile
import unittest
from copy import deepcopy
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import httpx

from job_hunter.application import executar_varredura_linkedin_posts
from job_hunter.discovery.apify_linkedin import (
    ClientePostsApify,
    ErroFonteApify,
)

AGORA = datetime(2026, 7, 26, 12, tzinfo=UTC)


class ExecutorApifyFake:
    def __init__(self, registros: list[dict[str, Any]]) -> None:
        self.registros = registros
        self.payload: dict[str, Any] | None = None
        self.maximo_itens: int | None = None

    def executar(
        self,
        payload: dict[str, Any],
        *,
        maximo_itens: int,
    ) -> list[dict[str, Any]]:
        self.payload = deepcopy(payload)
        self.maximo_itens = maximo_itens
        return deepcopy(self.registros)


class TestFontePostsLinkedInApify(unittest.TestCase):
    def setUp(self) -> None:
        self.raiz_projeto = Path(__file__).parents[1]
        self.registros = json.loads(
            (
                self.raiz_projeto
                / "tests"
                / "fixtures"
                / "apify_linkedin_posts.json"
            ).read_text(encoding="utf-8")
        )

    def test_executa_pipeline_com_filtro_local_e_deduplicacao(self) -> None:
        executor = ExecutorApifyFake(self.registros)

        with tempfile.TemporaryDirectory() as temporario:
            workspace = Path(temporario)
            inputs = workspace / "inputs"
            inputs.mkdir(parents=True)
            (inputs / "config_busca.json").write_text(
                (
                    self.raiz_projeto
                    / "tests"
                    / "fixtures"
                    / "config_busca_teste.json"
                ).read_text(encoding="utf-8"),
                encoding="utf-8",
            )

            primeiro = executar_varredura_linkedin_posts(
                workspace,
                dry_run=True,
                agora=AGORA,
                executor=executor,
            )
            segundo = executar_varredura_linkedin_posts(
                workspace,
                dry_run=True,
                agora=AGORA,
                executor=executor,
            )

            self.assertEqual(primeiro.descobertas, 3)
            self.assertEqual(primeiro.qualificadas, 1)
            self.assertEqual(primeiro.descartadas, 2)
            self.assertEqual(primeiro.duplicadas, 0)
            self.assertEqual(len(primeiro.relatorios_gerados), 1)
            relatorio = Path(primeiro.relatorios_gerados[0])
            self.assertTrue(relatorio.exists())
            texto_relatorio = relatorio.read_text(encoding="utf-8")
            self.assertIn("Origem: post_linkedin", texto_relatorio)
            self.assertIn("Autor: Ana Recrutadora", texto_relatorio)

            self.assertEqual(segundo.descobertas, 3)
            self.assertEqual(segundo.duplicadas, 3)
            self.assertEqual(segundo.qualificadas, 0)

        self.assertIsNotNone(executor.payload)
        assert executor.payload is not None
        self.assertEqual(executor.payload["maxPosts"], 5)
        self.assertEqual(executor.payload["sortBy"], "date")
        self.assertEqual(
            executor.payload["postedLimitDate"],
            "2026-07-24T12:00:00Z",
        )
        self.assertFalse(executor.payload["scrapeComments"])
        self.assertFalse(executor.payload["scrapeReactions"])
        self.assertEqual(executor.maximo_itens, 10)

    def test_cliente_usa_bearer_limites_e_actor_configurado(self) -> None:
        requisicao_recebida: httpx.Request | None = None

        def responder(requisicao: httpx.Request) -> httpx.Response:
            nonlocal requisicao_recebida
            requisicao_recebida = requisicao
            return httpx.Response(201, json=self.registros)

        transporte = httpx.MockTransport(responder)
        with httpx.Client(transport=transporte) as cliente_http:
            cliente = ClientePostsApify(
                token="apify-token-de-teste",
                limite_custo_usd=Decimal("0.25"),
                cliente_http=cliente_http,
            )
            resultado = cliente.executar(
                {"searchQueries": ["Python hiring"]},
                maximo_itens=25,
            )

        self.assertEqual(len(resultado), 3)
        self.assertIsNotNone(requisicao_recebida)
        assert requisicao_recebida is not None
        self.assertIn(
            "/actors/harvestapi~linkedin-post-search/"
            "run-sync-get-dataset-items",
            str(requisicao_recebida.url),
        )
        self.assertEqual(
            requisicao_recebida.headers["Authorization"],
            "Bearer apify-token-de-teste",
        )
        self.assertEqual(requisicao_recebida.url.params["maxItems"], "25")
        self.assertEqual(requisicao_recebida.url.params["limit"], "25")
        self.assertEqual(
            requisicao_recebida.url.params["maxTotalChargeUsd"],
            "0.25",
        )
        self.assertEqual(requisicao_recebida.url.params["timeout"], "240")

    def test_cliente_rejeita_resposta_que_nao_e_lista(self) -> None:
        transporte = httpx.MockTransport(
            lambda _: httpx.Response(201, json={"erro": "formato inesperado"})
        )
        with httpx.Client(transport=transporte) as cliente_http:
            cliente = ClientePostsApify(
                token="apify-token-de-teste",
                cliente_http=cliente_http,
            )
            with self.assertRaises(ErroFonteApify):
                cliente.executar({}, maximo_itens=1)


if __name__ == "__main__":
    unittest.main()
