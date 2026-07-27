from __future__ import annotations

import unittest
from datetime import UTC, datetime, timedelta

from job_hunter.filtering import avaliar_vaga
from job_hunter.schemas import (
    ConfiguracaoBusca,
    MotivoDescarte,
    Plataforma,
    Vaga,
)

AGORA = datetime(2026, 7, 26, 12, tzinfo=UTC)


def criar_configuracao() -> ConfiguracaoBusca:
    return ConfiguracaoBusca.model_validate(
        {
            "filtros_busca": {
                "palavras_chave": ["Python Developer", "Engenheiro de IA"],
                "localidade": "Brasil",
                "modalidade": "Remoto",
                "tempo_maximo_publicacao_horas": 48,
            },
            "plataformas_ativas": {"linkedin": True, "gupy": True},
            "automacao": {
                "navegacao_controlada": True,
                "interromper_em_captcha": True,
                "notificar_via_telegram": False,
                "tentar_auto_apply_simplificado": False,
                "dry_run": True,
            },
        }
    )


def criar_vaga(**alteracoes: object) -> Vaga:
    dados: dict[str, object] = {
        "id_externo": "vaga-1",
        "plataforma": Plataforma.LINKEDIN,
        "cargo": "Python Developer",
        "empresa": "Nexus",
        "localidade": "Brasil",
        "modalidade": "Remoto",
        "descricao": "APIs Python e Docker",
        "url": "https://example.invalid/vaga-1",
        "publicada_em": AGORA - timedelta(hours=8),
        "coletada_em": AGORA,
    }
    dados.update(alteracoes)
    return Vaga.model_validate(dados)


class TestFiltro(unittest.TestCase):
    def test_qualifica_vaga_recente_compativel(self) -> None:
        resultado = avaliar_vaga(criar_vaga(), criar_configuracao(), AGORA)
        self.assertTrue(resultado.qualificada)
        self.assertIsNone(resultado.motivo)

    def test_descarta_vaga_com_mais_de_48_horas(self) -> None:
        vaga = criar_vaga(publicada_em=AGORA - timedelta(hours=49))
        resultado = avaliar_vaga(vaga, criar_configuracao(), AGORA)
        self.assertFalse(resultado.qualificada)
        self.assertEqual(
            resultado.motivo,
            MotivoDescarte.FORA_DA_JANELA_TEMPORAL,
        )

    def test_aceita_vaga_com_48_horas_exatas(self) -> None:
        vaga = criar_vaga(publicada_em=AGORA - timedelta(hours=48))
        resultado = avaliar_vaga(vaga, criar_configuracao(), AGORA)
        self.assertTrue(resultado.qualificada)

    def test_descarta_data_futura_alem_da_tolerancia(self) -> None:
        vaga = criar_vaga(publicada_em=AGORA + timedelta(minutes=16))
        resultado = avaliar_vaga(vaga, criar_configuracao(), AGORA)
        self.assertFalse(resultado.qualificada)
        self.assertEqual(
            resultado.motivo,
            MotivoDescarte.DATA_DE_PUBLICACAO_FUTURA,
        )

    def test_descarta_vaga_sem_palavra_chave(self) -> None:
        vaga = criar_vaga(cargo="Frontend React", descricao="Design system")
        resultado = avaliar_vaga(vaga, criar_configuracao(), AGORA)
        self.assertFalse(resultado.qualificada)
        self.assertEqual(
            resultado.motivo,
            MotivoDescarte.PALAVRA_CHAVE_NAO_ENCONTRADA,
        )

    def test_rejeita_data_sem_timezone(self) -> None:
        with self.assertRaises(ValueError):
            criar_vaga(publicada_em=datetime(2026, 7, 26, 10))


if __name__ == "__main__":
    unittest.main()
