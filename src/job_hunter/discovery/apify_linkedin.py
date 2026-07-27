from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any, Protocol

import httpx
from pydantic import AnyHttpUrl, BaseModel, ConfigDict, Field, ValidationError

from job_hunter.schemas import ConfiguracaoBusca, OrigemVaga, Plataforma, Vaga


class ErroFonteApify(RuntimeError):
    pass


class ExecutorPostsApify(Protocol):
    def executar(
        self,
        payload: dict[str, Any],
        *,
        maximo_itens: int,
    ) -> list[dict[str, Any]]:
        ...


class ClientePostsApify:
    def __init__(
        self,
        token: str,
        actor_id: str = "harvestapi/linkedin-post-search",
        timeout_segundos: float = 240,
        limite_custo_usd: Decimal = Decimal("0.50"),
        cliente_http: httpx.Client | None = None,
    ) -> None:
        if not token.strip():
            raise ValueError("o token do Apify não pode ser vazio")
        if not actor_id.strip():
            raise ValueError("o ID do Actor do Apify não pode ser vazio")
        if timeout_segundos <= 0 or timeout_segundos > 300:
            raise ValueError("o timeout do Apify deve estar entre 1 e 300 segundos")
        if not limite_custo_usd.is_finite() or limite_custo_usd <= 0:
            raise ValueError("o limite de custo do Apify deve ser maior que zero")
        self.token = token.strip()
        self.actor_id = actor_id.strip().replace("/", "~")
        self.timeout_segundos = timeout_segundos
        self.limite_custo_usd = limite_custo_usd
        self.cliente_http = cliente_http

    def executar(
        self,
        payload: dict[str, Any],
        *,
        maximo_itens: int,
    ) -> list[dict[str, Any]]:
        if maximo_itens <= 0:
            raise ValueError("o máximo de itens do Apify deve ser maior que zero")
        url = (
            "https://api.apify.com/v2/actors/"
            f"{self.actor_id}/run-sync-get-dataset-items"
        )
        parametros = {
            "clean": "true",
            "format": "json",
            "limit": str(maximo_itens),
            "maxItems": str(maximo_itens),
            "maxTotalChargeUsd": str(self.limite_custo_usd),
            "timeout": f"{self.timeout_segundos:g}",
        }
        cabecalhos = {"Authorization": f"Bearer {self.token}"}

        try:
            if self.cliente_http is not None:
                resposta = self.cliente_http.post(
                    url,
                    params=parametros,
                    headers=cabecalhos,
                    json=payload,
                    timeout=self.timeout_segundos,
                )
            else:
                resposta = httpx.post(
                    url,
                    params=parametros,
                    headers=cabecalhos,
                    json=payload,
                    timeout=self.timeout_segundos,
                )
            resposta.raise_for_status()
            dados = resposta.json()
        except (httpx.HTTPError, ValueError) as erro:
            raise ErroFonteApify(
                "falha ao executar o Actor de posts do LinkedIn no Apify"
            ) from erro

        if not isinstance(dados, list):
            raise ErroFonteApify("o Apify retornou um payload que não é uma lista")
        return dados


class _AutorApify(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: str = "Autor não identificado"
    linkedin_url: AnyHttpUrl | None = Field(default=None, alias="linkedinUrl")
    info: str | None = None
    type: str | None = None


class _DataPublicacaoApify(BaseModel):
    model_config = ConfigDict(extra="ignore")

    date: datetime


class _PostApify(BaseModel):
    model_config = ConfigDict(extra="ignore")

    type: str = "post"
    id: str
    linkedin_url: AnyHttpUrl = Field(alias="linkedinUrl")
    content: str = Field(min_length=1)
    author: _AutorApify = Field(default_factory=_AutorApify)
    posted_at: _DataPublicacaoApify = Field(alias="postedAt")


class FontePostsLinkedInApify:
    def __init__(
        self,
        configuracao: ConfiguracaoBusca,
        executor: ExecutorPostsApify,
    ) -> None:
        if configuracao.linkedin_posts is None:
            raise ValueError("a configuração 'linkedin_posts' não foi definida")
        self.configuracao = configuracao
        self.executor = executor

    def descobrir(self, agora: datetime) -> list[Vaga]:
        if agora.tzinfo is None or agora.utcoffset() is None:
            raise ValueError("a data da coleta deve conter timezone")

        config_posts = self.configuracao.linkedin_posts
        if config_posts is None or not config_posts.ativo:
            return []

        limite = config_posts.maximo_por_consulta * len(config_posts.consultas)
        payload = {
            "maxPosts": config_posts.maximo_por_consulta,
            "postNestedComments": False,
            "postNestedReactions": False,
            "scrapeComments": False,
            "scrapeReactions": False,
            "postedLimitDate": _formatar_data_apify(
                agora
                - timedelta(
                    hours=self.configuracao.filtros_busca.tempo_maximo_publicacao_horas
                )
            ),
            "sortBy": config_posts.ordenar_por,
            "searchQueries": config_posts.consultas,
        }
        registros = self.executor.executar(payload, maximo_itens=limite)

        vagas: list[Vaga] = []
        for indice, registro in enumerate(registros):
            if registro.get("type", "post") != "post":
                continue
            try:
                post = _PostApify.model_validate(registro)
            except ValidationError as erro:
                raise ErroFonteApify(
                    f"post inválido retornado pelo Apify no índice {indice}"
                ) from erro
            vagas.append(self._normalizar(post, agora))
        return vagas

    def _normalizar(self, post: _PostApify, agora: datetime) -> Vaga:
        conteudo = post.content.strip()
        cargo = _identificar_cargo(
            conteudo,
            self.configuracao.filtros_busca.palavras_chave,
        )
        empresa = _identificar_empresa(post.author)
        localidade = _identificar_localidade(conteudo)
        modalidade = _identificar_modalidade(conteudo)

        return Vaga(
            id_externo=f"post-{post.id}",
            plataforma=Plataforma.LINKEDIN,
            cargo=cargo,
            empresa=empresa,
            localidade=localidade,
            modalidade=modalidade,
            descricao=conteudo,
            url=post.linkedin_url,
            publicada_em=post.posted_at.date,
            coletada_em=agora,
            origem=OrigemVaga.POST_LINKEDIN,
            autor_nome=post.author.name,
            autor_url=post.author.linkedin_url,
        )


def _formatar_data_apify(valor: datetime) -> str:
    return valor.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _identificar_cargo(conteudo: str, palavras_chave: list[str]) -> str:
    texto = conteudo.casefold()
    for palavra in palavras_chave:
        if palavra.casefold() in texto:
            return palavra
    for palavra in palavras_chave:
        tokens = [token for token in re.split(r"[\s/-]+", palavra) if len(token) >= 3]
        if any(token.casefold() in texto for token in tokens):
            return palavra
    return "Oportunidade via post do LinkedIn"


def _identificar_empresa(autor: _AutorApify) -> str:
    if autor.type == "company":
        return autor.name
    if autor.info:
        correspondencia = re.search(
            r"(?:@|\bat\b|\bna\b|\bno\b)\s+([^|•]+)",
            autor.info,
            flags=re.IGNORECASE,
        )
        if correspondencia:
            return correspondencia.group(1).strip()
    return f"Publicação de {autor.name}"


def _identificar_localidade(conteudo: str) -> str:
    texto = conteudo.casefold()
    if "brasil" in texto or "brazil" in texto:
        return "Brasil"
    return "Não informada"


def _identificar_modalidade(conteudo: str) -> str:
    texto = conteudo.casefold()
    if "remoto" in texto or "remote" in texto:
        return "Remoto"
    if "híbrido" in texto or "hybrid" in texto:
        return "Híbrido"
    if "presencial" in texto or "on-site" in texto or "onsite" in texto:
        return "Presencial"
    return "Não informada"
