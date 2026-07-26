from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Annotated

from pydantic import (
    AnyHttpUrl,
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)


TextoObrigatorio = Annotated[str, Field(min_length=1)]


class ModeloEstrito(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        validate_assignment=True,
    )


class Plataforma(StrEnum):
    LINKEDIN = "linkedin"
    GUPY = "gupy"


class StatusVaga(StrEnum):
    QUALIFICADA = "qualificada"
    DESCARTADA = "descartada"


class MotivoDescarte(StrEnum):
    FORA_DA_JANELA_TEMPORAL = "fora_da_janela_temporal"
    DATA_DE_PUBLICACAO_FUTURA = "data_de_publicacao_futura"
    PLATAFORMA_DESATIVADA = "plataforma_desativada"
    PALAVRA_CHAVE_NAO_ENCONTRADA = "palavra_chave_nao_encontrada"
    LOCALIDADE_DIVERGENTE = "localidade_divergente"
    MODALIDADE_DIVERGENTE = "modalidade_divergente"


class FiltrosBusca(ModeloEstrito):
    palavras_chave: list[TextoObrigatorio] = Field(min_length=1)
    localidade: TextoObrigatorio
    modalidade: TextoObrigatorio
    tempo_maximo_publicacao_horas: int = Field(gt=0, le=168)

    @field_validator("palavras_chave")
    @classmethod
    def remover_palavras_repetidas(cls, palavras: list[str]) -> list[str]:
        resultado: list[str] = []
        conhecidas: set[str] = set()
        for palavra in palavras:
            chave = palavra.casefold()
            if chave not in conhecidas:
                conhecidas.add(chave)
                resultado.append(palavra)
        return resultado


class PlataformasAtivas(ModeloEstrito):
    linkedin: bool = True
    gupy: bool = True

    def esta_ativa(self, plataforma: Plataforma) -> bool:
        return bool(getattr(self, plataforma.value))


class Automacao(ModeloEstrito):
    navegacao_controlada: bool = True
    interromper_em_captcha: bool = True
    notificar_via_telegram: bool = False
    tentar_auto_apply_simplificado: bool = False
    dry_run: bool = True

    @model_validator(mode="after")
    def bloquear_auto_apply_no_mvp(self) -> Automacao:
        if self.tentar_auto_apply_simplificado:
            raise ValueError(
                "auto apply ainda não está disponível; mantenha "
                "'tentar_auto_apply_simplificado' como false"
            )
        if not self.interromper_em_captcha:
            raise ValueError(
                "'interromper_em_captcha' deve permanecer true por segurança"
            )
        return self


class ConfiguracaoBusca(ModeloEstrito):
    filtros_busca: FiltrosBusca
    plataformas_ativas: PlataformasAtivas
    automacao: Automacao


class Vaga(ModeloEstrito):
    id_externo: TextoObrigatorio
    plataforma: Plataforma
    cargo: TextoObrigatorio
    empresa: TextoObrigatorio
    localidade: TextoObrigatorio
    modalidade: TextoObrigatorio
    descricao: TextoObrigatorio
    url: AnyHttpUrl
    publicada_em: datetime
    coletada_em: datetime

    @field_validator("publicada_em", "coletada_em")
    @classmethod
    def exigir_timezone(cls, valor: datetime) -> datetime:
        if valor.tzinfo is None or valor.utcoffset() is None:
            raise ValueError("datas devem conter timezone")
        return valor

    @property
    def chave_deduplicacao(self) -> tuple[str, str]:
        return self.plataforma.value, self.id_externo


class ResumoExecucao(ModeloEstrito):
    dry_run: bool
    descobertas: int = 0
    qualificadas: int = 0
    descartadas: int = 0
    duplicadas: int = 0
    relatorios_gerados: list[str] = Field(default_factory=list)

