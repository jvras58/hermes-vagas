from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Annotated, Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import (
    AnyHttpUrl,
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

TextoObrigatorio = Annotated[str, Field(min_length=1)]
HashSha256 = Annotated[str, Field(pattern=r"^[a-fA-F0-9]{64}$")]


class ModeloEstrito(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        validate_assignment=True,
    )


class Plataforma(StrEnum):
    LINKEDIN = "linkedin"
    GUPY = "gupy"


class OrigemVaga(StrEnum):
    ANUNCIO = "anuncio"
    POST_LINKEDIN = "post_linkedin"


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
    SEM_INDICIO_CONTRATACAO = "sem_indicio_contratacao"


class ImportanciaRequisito(StrEnum):
    OBRIGATORIO = "obrigatorio"
    DESEJAVEL = "desejavel"


class StatusRequisito(StrEnum):
    ATENDIDO = "atendido"
    PARCIAL = "parcial"
    AUSENTE = "ausente"


class RecomendacaoAnalise(StrEnum):
    APLICAR = "aplicar"
    REVISAR = "revisar"
    NAO_APLICAR = "nao_aplicar"


class TipoAjusteCurriculo(StrEnum):
    DESTACAR = "destacar"
    REORDENAR = "reordenar"
    REESCREVER = "reescrever"


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


class LinkedInPosts(ModeloEstrito):
    ativo: bool = False
    consultas: list[TextoObrigatorio] = Field(default_factory=list, max_length=20)
    ordenar_por: Literal["date", "relevance"] = "date"
    maximo_por_consulta: int = Field(default=5, ge=1, le=100)
    sinais_contratacao: list[TextoObrigatorio] = Field(
        default_factory=lambda: [
            "vaga",
            "vagas",
            "oportunidade",
            "oportunidades",
            "contratando",
            "hiring",
            "join our team",
            "open position",
        ],
        min_length=1,
    )

    @field_validator("consultas")
    @classmethod
    def validar_consultas(cls, consultas: list[str]) -> list[str]:
        resultado: list[str] = []
        conhecidas: set[str] = set()
        for consulta in consultas:
            if len(consulta) > 85:
                raise ValueError(
                    "cada consulta do LinkedIn deve ter no máximo 85 caracteres"
                )
            chave = consulta.casefold()
            if chave not in conhecidas:
                conhecidas.add(chave)
                resultado.append(consulta)
        return resultado

    @model_validator(mode="after")
    def exigir_consultas_quando_ativa(self) -> LinkedInPosts:
        if self.ativo and not self.consultas:
            raise ValueError(
                "'linkedin_posts.consultas' deve ser preenchido quando a fonte "
                "estiver ativa"
            )
        return self


class AnaliseSemanticaConfig(ModeloEstrito):
    ativa: bool = True
    prompt_version: TextoObrigatorio = "semantic-v2"
    provedor: TextoObrigatorio = "nvidia"
    modelo: TextoObrigatorio = "z-ai/glm-5.2"
    limiar_aplicar: int = Field(default=75, ge=1, le=100)
    limiar_revisar: int = Field(default=50, ge=0, le=99)

    @model_validator(mode="after")
    def validar_limites_recomendacao(self) -> AnaliseSemanticaConfig:
        if self.limiar_revisar >= self.limiar_aplicar:
            raise ValueError(
                "'limiar_revisar' deve ser menor que 'limiar_aplicar'"
            )
        return self


class ResumoDiarioConfig(ModeloEstrito):
    ativo: bool = True
    agendamento_cron: TextoObrigatorio = "0 8 * * *"
    fuso_horario: TextoObrigatorio = "America/Recife"
    maximo_analises_por_execucao: int = Field(default=20, ge=1, le=100)

    @field_validator("agendamento_cron")
    @classmethod
    def validar_cron(cls, valor: str) -> str:
        if len(valor.split()) != 5:
            raise ValueError(
                "'agendamento_cron' deve usar cinco campos no formato cron"
            )
        return valor

    @field_validator("fuso_horario")
    @classmethod
    def validar_fuso_horario(cls, valor: str) -> str:
        try:
            ZoneInfo(valor)
        except ZoneInfoNotFoundError as erro:
            raise ValueError(
                "'fuso_horario' deve ser um identificador IANA válido"
            ) from erro
        return valor


class ConfiguracaoBusca(ModeloEstrito):
    filtros_busca: FiltrosBusca
    plataformas_ativas: PlataformasAtivas
    automacao: Automacao
    linkedin_posts: LinkedInPosts | None = None
    analise_semantica: AnaliseSemanticaConfig | None = None
    resumo_diario: ResumoDiarioConfig | None = None


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
    origem: OrigemVaga = OrigemVaga.ANUNCIO
    autor_nome: str | None = None
    autor_url: AnyHttpUrl | None = None

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


class FatoCurriculo(ModeloEstrito):
    id: TextoObrigatorio
    secao: TextoObrigatorio
    texto: TextoObrigatorio


class RequisitoAnaliseSemantica(ModeloEstrito):
    requisito: TextoObrigatorio
    importancia: ImportanciaRequisito
    status: StatusRequisito
    evidencias_curriculo: list[TextoObrigatorio] = Field(
        default_factory=list,
        max_length=20,
    )
    justificativa: Annotated[str, Field(min_length=1, max_length=1000)]

    @model_validator(mode="after")
    def validar_evidencias(self) -> RequisitoAnaliseSemantica:
        if self.status in {
            StatusRequisito.ATENDIDO,
            StatusRequisito.PARCIAL,
        } and not self.evidencias_curriculo:
            raise ValueError(
                "requisitos atendidos ou parciais exigem evidências do currículo"
            )
        if (
            self.status == StatusRequisito.AUSENTE
            and self.evidencias_curriculo
        ):
            raise ValueError(
                "requisitos ausentes não podem referenciar evidências"
            )
        return self


class AjusteCurriculo(ModeloEstrito):
    tipo: TipoAjusteCurriculo
    secao_alvo: TextoObrigatorio
    fatos_curriculo: list[TextoObrigatorio] = Field(min_length=1, max_length=20)
    instrucao: Annotated[str, Field(min_length=1, max_length=1000)]
    texto_sugerido: (
        Annotated[str, Field(min_length=1, max_length=2000)] | None
    ) = None
    justificativa: Annotated[str, Field(min_length=1, max_length=1000)]

    @field_validator("fatos_curriculo")
    @classmethod
    def impedir_fatos_repetidos(cls, fatos: list[str]) -> list[str]:
        if len(fatos) != len(set(fatos)):
            raise ValueError("o ajuste contém fatos do currículo repetidos")
        return fatos

    @model_validator(mode="after")
    def validar_texto_sugerido(self) -> AjusteCurriculo:
        if (
            self.tipo == TipoAjusteCurriculo.REESCREVER
            and self.texto_sugerido is None
        ):
            raise ValueError(
                "ajustes do tipo 'reescrever' exigem 'texto_sugerido'"
            )
        if (
            self.tipo != TipoAjusteCurriculo.REESCREVER
            and self.texto_sugerido is not None
        ):
            raise ValueError(
                "'texto_sugerido' só é permitido no tipo 'reescrever'"
            )
        return self


class AnaliseSemanticaEntrada(ModeloEstrito):
    prompt_version: TextoObrigatorio
    curriculo_sha256: HashSha256
    resumo: Annotated[str, Field(min_length=1, max_length=1500)]
    requisitos: list[RequisitoAnaliseSemantica] = Field(
        min_length=1,
        max_length=30,
    )
    palavras_chave_ats: list[TextoObrigatorio] = Field(
        default_factory=list,
        max_length=30,
    )
    ajustes_curriculo: list[AjusteCurriculo] = Field(
        default_factory=list,
        max_length=20,
    )

    @field_validator("requisitos")
    @classmethod
    def impedir_requisitos_repetidos(
        cls,
        requisitos: list[RequisitoAnaliseSemantica],
    ) -> list[RequisitoAnaliseSemantica]:
        chaves = [requisito.requisito.casefold() for requisito in requisitos]
        if len(chaves) != len(set(chaves)):
            raise ValueError("a análise contém requisitos repetidos")
        return requisitos

    @field_validator("palavras_chave_ats")
    @classmethod
    def remover_palavras_ats_repetidas(cls, palavras: list[str]) -> list[str]:
        resultado: list[str] = []
        conhecidas: set[str] = set()
        for palavra in palavras:
            chave = palavra.casefold()
            if chave not in conhecidas:
                conhecidas.add(chave)
                resultado.append(palavra)
        return resultado


class AnaliseSemantica(AnaliseSemanticaEntrada):
    plataforma: Plataforma
    id_externo: TextoObrigatorio
    score: int = Field(ge=0, le=100)
    recomendacao: RecomendacaoAnalise
    pontos_fortes: list[TextoObrigatorio] = Field(default_factory=list)
    lacunas: list[TextoObrigatorio] = Field(default_factory=list)
    provedor: TextoObrigatorio
    modelo: TextoObrigatorio
    analisada_em: datetime

    @field_validator("analisada_em")
    @classmethod
    def exigir_timezone_analise(cls, valor: datetime) -> datetime:
        if valor.tzinfo is None or valor.utcoffset() is None:
            raise ValueError("a data da análise deve conter timezone")
        return valor
