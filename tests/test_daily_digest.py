from __future__ import annotations

import json
import os
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

from job_hunter.application import executar_varredura_mock
from job_hunter.daily_digest import ErroResumoDiario, ServicoResumoDiario
from job_hunter.schemas import AnaliseSemanticaEntrada, Plataforma
from job_hunter.semantic_analysis import ServicoAnaliseSemantica


class TestResumoDiario(unittest.TestCase):
    def setUp(self) -> None:
        self.raiz_projeto = Path(__file__).parents[1]
        self.temporario = tempfile.TemporaryDirectory()
        self.workspace = Path(self.temporario.name)
        inputs = self.workspace / "inputs"
        inputs.mkdir(parents=True)
        self._copiar_fixture("config_busca_teste.json", "config_busca.json")
        self._copiar_fixture("curriculo_base_teste.md", "curriculo_base.md")
        (inputs / "vagas_mock.json").write_text(
            json.dumps(
                [
                    {
                        "id_externo": "digest-001",
                        "plataforma": "linkedin",
                        "cargo": "Python Developer",
                        "empresa": "Nexus",
                        "localidade": "Brasil",
                        "modalidade": "Remoto",
                        "descricao": "Vaga remota para Python e FastAPI.",
                        "url": "https://example.invalid/digest-001",
                        "publicada_ha_horas": 2,
                    }
                ]
            ),
            encoding="utf-8",
        )
        self.agora = datetime(2026, 7, 26, 12, tzinfo=UTC)
        self.ambiente_telegram = patch.dict(
            os.environ,
            {
                "TELEGRAM_BOT_TOKEN": "123456:token-teste",
                "TELEGRAM_ALLOWED_USERS": "123456789",
                "TELEGRAM_HOME_CHANNEL": "123456789",
            },
        )
        self.ambiente_telegram.start()
        executar_varredura_mock(
            self.workspace,
            dry_run=False,
            agora=self.agora,
        )

    def tearDown(self) -> None:
        self.ambiente_telegram.stop()
        self.temporario.cleanup()

    def _copiar_fixture(self, origem: str, destino: str) -> None:
        conteudo = (self.raiz_projeto / "tests" / "fixtures" / origem).read_text(
            encoding="utf-8"
        )
        (self.workspace / "inputs" / destino).write_text(
            conteudo,
            encoding="utf-8",
        )

    def _salvar_analise(self) -> None:
        servico = ServicoAnaliseSemantica(
            self.workspace,
            dry_run=False,
            relogio=lambda: self.agora,
        )
        contexto = servico.obter_contexto(
            Plataforma.LINKEDIN,
            "digest-001",
        )
        fatos = contexto["fatos_curriculo"]
        primeiro_id = fatos[0]["id"]
        segundo_id = fatos[1]["id"]
        entrada = AnaliseSemanticaEntrada.model_validate(
            {
                "prompt_version": contexto["prompt_version"],
                "curriculo_sha256": contexto["curriculo_sha256"],
                "resumo": "O currículo comprova os requisitos da vaga.",
                "requisitos": [
                    {
                        "requisito": "Python e FastAPI",
                        "importancia": "obrigatorio",
                        "status": "atendido",
                        "evidencias_curriculo": [segundo_id],
                        "justificativa": "As tecnologias estão explícitas.",
                    }
                ],
                "palavras_chave_ats": ["Python", "FastAPI"],
                "ajustes_curriculo": [
                    {
                        "tipo": "destacar",
                        "secao_alvo": "Competências técnicas",
                        "fatos_curriculo": [segundo_id],
                        "instrucao": "Dar prioridade visual a Python e FastAPI.",
                        "justificativa": (
                            "São requisitos explícitos e já constam no currículo."
                        ),
                    },
                    {
                        "tipo": "reordenar",
                        "secao_alvo": "Resumo profissional",
                        "fatos_curriculo": [primeiro_id],
                        "instrucao": "Mover a experiência com APIs para o início.",
                        "justificativa": "APIs são centrais para a vaga.",
                    },
                ],
            }
        )
        servico.salvar(Plataforma.LINKEDIN, "digest-001", entrada)

    def test_gera_relatorio_e_referencia_media_do_telegram(self) -> None:
        self._salvar_analise()
        servico = ServicoResumoDiario(
            self.workspace,
            dry_run=False,
            relogio=lambda: self.agora,
        )

        resultado = servico.gerar()

        self.assertEqual(resultado["data"], "2026-07-26")
        self.assertEqual(resultado["total_analisadas"], 1)
        self.assertEqual(resultado["recomendacoes"]["aplicar"], 1)
        caminho = Path(resultado["relatorio"])
        self.assertTrue(caminho.exists())
        self.assertEqual(
            resultado["telegram_media"],
            f"MEDIA:{caminho}",
        )
        relatorio = caminho.read_text(encoding="utf-8")
        self.assertIn("Python Developer", relatorio)
        self.assertIn("https://example.invalid/digest-001", relatorio)
        self.assertIn("Dar prioridade visual", relatorio)
        self.assertIn("cv-002", relatorio)

    def test_gera_relatorio_vazio_para_data_sem_analises(self) -> None:
        servico = ServicoResumoDiario(
            self.workspace,
            dry_run=False,
            relogio=lambda: self.agora,
        )

        resultado = servico.gerar("2026-07-27")

        self.assertEqual(resultado["total_analisadas"], 0)
        conteudo = Path(resultado["relatorio"]).read_text(encoding="utf-8")
        self.assertIn("Nenhuma análise semântica", conteudo)

    def test_plano_reflete_cron_fuso_limite_e_fluxo(self) -> None:
        servico = ServicoResumoDiario(
            self.workspace,
            dry_run=False,
            relogio=lambda: self.agora,
        )

        plano = servico.obter_plano_agendamento()

        self.assertEqual(plano["agendamento_cron"], "0 8 * * *")
        self.assertEqual(plano["fuso_horario"], "America/Recife")
        self.assertEqual(plano["maximo_analises_por_execucao"], 20)
        cronjob = plano["cronjob"]
        self.assertEqual(cronjob["name"], "Job Hunter Diário")
        self.assertEqual(cronjob["schedule"], "0 8 * * *")
        self.assertEqual(cronjob["deliver"], "telegram")
        self.assertEqual(cronjob["workdir"], "/workspace")
        self.assertEqual(cronjob["provider"], "nvidia")
        self.assertEqual(cronjob["model"], "z-ai/glm-5.2")
        self.assertIn("scan_linkedin_posts", cronjob["prompt"])
        self.assertIn("build_daily_digest", cronjob["prompt"])
        self.assertIn("telegram_media", cronjob["prompt"])

    def test_rejeita_data_invalida(self) -> None:
        servico = ServicoResumoDiario(
            self.workspace,
            dry_run=False,
            relogio=lambda: self.agora,
        )

        with self.assertRaisesRegex(ErroResumoDiario, "AAAA-MM-DD"):
            servico.gerar("27/07/2026")

    def test_plano_exige_notificacao_telegram_ativa(self) -> None:
        caminho = self.workspace / "inputs" / "config_busca.json"
        dados = json.loads(caminho.read_text(encoding="utf-8"))
        dados["automacao"]["notificar_via_telegram"] = False
        caminho.write_text(json.dumps(dados), encoding="utf-8")
        servico = ServicoResumoDiario(
            self.workspace,
            dry_run=False,
            relogio=lambda: self.agora,
        )

        with self.assertRaisesRegex(
            ErroResumoDiario,
            "notificar_via_telegram",
        ):
            servico.obter_plano_agendamento()

    def test_plano_exige_canal_telegram_configurado(self) -> None:
        servico = ServicoResumoDiario(
            self.workspace,
            dry_run=False,
            relogio=lambda: self.agora,
        )

        with (
            patch.dict(
                os.environ,
                {"TELEGRAM_HOME_CHANNEL": ""},
            ),
            self.assertRaisesRegex(
                ErroResumoDiario,
                "TELEGRAM_HOME_CHANNEL",
            ),
        ):
            servico.obter_plano_agendamento()


if __name__ == "__main__":
    unittest.main()
