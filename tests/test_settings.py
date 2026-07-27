from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from job_hunter.settings import ErroConfiguracao, carregar_configuracao


class TestConfiguracao(unittest.TestCase):
    def test_carrega_configuracao_valida_e_remove_palavras_repetidas(self) -> None:
        with tempfile.TemporaryDirectory() as temporario:
            caminho = Path(temporario) / "config.json"
            caminho.write_text(
                json.dumps(
                    {
                        "filtros_busca": {
                            "palavras_chave": ["Python", "python"],
                            "localidade": "Brasil",
                            "modalidade": "Remoto",
                            "tempo_maximo_publicacao_horas": 48,
                        },
                        "plataformas_ativas": {
                            "linkedin": True,
                            "gupy": True,
                        },
                        "automacao": {
                            "navegacao_controlada": True,
                            "interromper_em_captcha": True,
                            "notificar_via_telegram": False,
                            "tentar_auto_apply_simplificado": False,
                            "dry_run": True,
                        },
                    }
                ),
                encoding="utf-8",
            )

            configuracao = carregar_configuracao(caminho)

        self.assertEqual(configuracao.filtros_busca.palavras_chave, ["Python"])
        self.assertEqual(
            configuracao.filtros_busca.tempo_maximo_publicacao_horas,
            48,
        )

    def test_rejeita_auto_apply_no_mvp(self) -> None:
        origem = (
            Path(__file__).parents[1]
            / "workspace"
            / "inputs"
            / "config_busca.json"
        )
        dados = json.loads(origem.read_text(encoding="utf-8"))
        dados["automacao"]["tentar_auto_apply_simplificado"] = True

        with tempfile.TemporaryDirectory() as temporario:
            caminho = Path(temporario) / "config.json"
            caminho.write_text(json.dumps(dados), encoding="utf-8")

            with self.assertRaises(ErroConfiguracao):
                carregar_configuracao(caminho)

    def test_rejeita_consulta_linkedin_acima_de_85_caracteres(self) -> None:
        origem = (
            Path(__file__).parents[1]
            / "workspace"
            / "inputs"
            / "config_busca.json"
        )
        dados = json.loads(origem.read_text(encoding="utf-8"))
        dados["linkedin_posts"]["consultas"] = ["x" * 86]

        with tempfile.TemporaryDirectory() as temporario:
            caminho = Path(temporario) / "config.json"
            caminho.write_text(json.dumps(dados), encoding="utf-8")

            with self.assertRaises(ErroConfiguracao):
                carregar_configuracao(caminho)


if __name__ == "__main__":
    unittest.main()
