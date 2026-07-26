from __future__ import annotations

import json
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path

from job_hunter.application import executar_varredura_mock


class TestPipeline(unittest.TestCase):
    def test_executa_fluxo_e_deduplica_segunda_varredura(self) -> None:
        raiz_projeto = Path(__file__).parents[1]

        with tempfile.TemporaryDirectory() as temporario:
            workspace = Path(temporario)
            inputs = workspace / "inputs"
            inputs.mkdir(parents=True)
            (inputs / "config_busca.json").write_text(
                (
                    raiz_projeto / "workspace" / "inputs" / "config_busca.json"
                ).read_text(encoding="utf-8"),
                encoding="utf-8",
            )
            vagas = [
                {
                    "id_externo": "recente",
                    "plataforma": "linkedin",
                    "cargo": "Python Developer",
                    "empresa": "Nexus",
                    "localidade": "Brasil",
                    "modalidade": "Remoto",
                    "descricao": "APIs Python",
                    "url": "https://example.invalid/recente",
                    "publicada_ha_horas": 8,
                },
                {
                    "id_externo": "antiga",
                    "plataforma": "gupy",
                    "cargo": "Engenheiro de IA",
                    "empresa": "Aurora",
                    "localidade": "Brasil",
                    "modalidade": "Remoto",
                    "descricao": "Modelos e Python",
                    "url": "https://example.invalid/antiga",
                    "publicada_ha_horas": 72,
                },
                {
                    "id_externo": "incompativel",
                    "plataforma": "linkedin",
                    "cargo": "Frontend React",
                    "empresa": "Interface",
                    "localidade": "Brasil",
                    "modalidade": "Remoto",
                    "descricao": "React",
                    "url": "https://example.invalid/incompativel",
                    "publicada_ha_horas": 2,
                },
            ]
            (inputs / "vagas_mock.json").write_text(
                json.dumps(vagas),
                encoding="utf-8",
            )
            agora = datetime(2026, 7, 26, 12, tzinfo=UTC)

            primeiro = executar_varredura_mock(workspace, True, agora)
            segundo = executar_varredura_mock(workspace, True, agora)

            self.assertEqual(primeiro.descobertas, 3)
            self.assertEqual(primeiro.qualificadas, 1)
            self.assertEqual(primeiro.descartadas, 2)
            self.assertEqual(primeiro.duplicadas, 0)
            self.assertEqual(len(primeiro.relatorios_gerados), 1)
            self.assertTrue(Path(primeiro.relatorios_gerados[0]).exists())
            self.assertTrue((workspace / "state" / "vagas-dry-run.db").exists())
            self.assertFalse((workspace / "state" / "vagas-producao.db").exists())

            self.assertEqual(segundo.descobertas, 3)
            self.assertEqual(segundo.duplicadas, 3)
            self.assertEqual(segundo.qualificadas, 0)


if __name__ == "__main__":
    unittest.main()
