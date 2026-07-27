from __future__ import annotations

import json
import re
import unicodedata
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path

from job_hunter.schemas import (
    AnaliseSemantica,
    ConfiguracaoBusca,
    FatoCurriculo,
    Vaga,
)

MARCADOR_ANALISE = "ANÁLISE SEMÂNTICA HERMES"


def criar_relatorio_triagem(
    vaga: Vaga,
    configuracao: ConfiguracaoBusca,
    raiz_saida: Path,
    agora: datetime,
) -> Path:
    diretorio = _diretorio_vaga(vaga, raiz_saida, agora)
    diretorio.mkdir(parents=True, exist_ok=True)
    caminho = diretorio / "Relatorio_Match.txt"

    texto_completo = f"{vaga.cargo} {vaga.descricao}".casefold()
    palavras_encontradas = [
        palavra
        for palavra in configuracao.filtros_busca.palavras_chave
        if palavra.casefold() in texto_completo
    ]
    idade_horas = max((agora - vaga.publicada_em).total_seconds() / 3600, 0)

    linhas = [
        "RELATÓRIO DE TRIAGEM DETERMINÍSTICA",
        "",
        f"Vaga: {vaga.cargo}",
        f"Empresa: {vaga.empresa}",
        f"Plataforma: {vaga.plataforma.value}",
        f"Origem: {vaga.origem.value}",
    ]
    if vaga.autor_nome:
        linhas.append(f"Autor: {vaga.autor_nome}")
    if vaga.autor_url:
        linhas.append(f"Perfil do autor: {vaga.autor_url}")
    linhas.extend(
        [
            f"Publicada há: {idade_horas:.1f} hora(s)",
            f"Localidade: {vaga.localidade}",
            f"Modalidade: {vaga.modalidade}",
            f"Link: {vaga.url}",
            "",
            "Status: QUALIFICADA PARA ANÁLISE LLM",
            "Match Rate: pendente de análise semântica",
            "Palavras-chave encontradas: "
            + (
                ", ".join(palavras_encontradas)
                or "nenhuma correspondência literal"
            ),
            "",
            "Observação: nenhum currículo foi alterado nesta etapa.",
        ]
    )
    if vaga.origem.value == "post_linkedin":
        linhas.append(
            "Dados inferidos do texto do post devem ser confirmados no link."
        )

    conteudo = "\n".join(linhas)
    caminho.write_text(f"{conteudo}\n", encoding="utf-8")
    return caminho


def salvar_artefatos_analise(
    vaga: Vaga,
    analise: AnaliseSemantica,
    fatos_curriculo: Sequence[FatoCurriculo],
    raiz_saida: Path,
) -> tuple[Path, Path]:
    diretorio = _diretorio_vaga(vaga, raiz_saida, vaga.coletada_em)
    diretorio.mkdir(parents=True, exist_ok=True)

    caminho_json = diretorio / "Analise_Semantica.json"
    caminho_json.write_text(
        json.dumps(
            analise.model_dump(mode="json"),
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    caminho_relatorio = diretorio / "Relatorio_Match.txt"
    conteudo_anterior = ""
    if caminho_relatorio.exists():
        conteudo_anterior = caminho_relatorio.read_text(encoding="utf-8")
    conteudo_triagem = conteudo_anterior.split(MARCADOR_ANALISE, maxsplit=1)[0]
    if not conteudo_triagem.strip():
        conteudo_triagem = "\n".join(
            [
                "RELATÓRIO DE TRIAGEM DETERMINÍSTICA",
                "",
                f"Vaga: {vaga.cargo}",
                f"Empresa: {vaga.empresa}",
                f"Link: {vaga.url}",
            ]
        )

    fatos_por_id = {fato.id: fato for fato in fatos_curriculo}
    linhas = [
        MARCADOR_ANALISE,
        "",
        f"Score: {analise.score}%",
        f"Recomendação: {analise.recomendacao.value}",
        f"Resumo: {analise.resumo}",
        f"Provedor/modelo: {analise.provedor} / {analise.modelo}",
        f"Versão do prompt: {analise.prompt_version}",
        f"Hash do currículo: {analise.curriculo_sha256}",
        f"Analisada em: {analise.analisada_em.isoformat()}",
        "",
        "REQUISITOS",
    ]
    for requisito in analise.requisitos:
        linhas.extend(
            [
                "",
                f"- {requisito.requisito}",
                f"  Importância: {requisito.importancia.value}",
                f"  Status: {requisito.status.value}",
                f"  Justificativa: {requisito.justificativa}",
            ]
        )
        if requisito.evidencias_curriculo:
            linhas.append("  Evidências:")
            for identificador in requisito.evidencias_curriculo:
                fato = fatos_por_id[identificador]
                linhas.append(
                    f"    - {fato.id} — {fato.secao}: {fato.texto}"
                )
        else:
            linhas.append("  Evidências: nenhuma")

    linhas.extend(
        [
            "",
            "Pontos fortes: "
            + (", ".join(analise.pontos_fortes) or "nenhum confirmado"),
            "Lacunas: " + (", ".join(analise.lacunas) or "nenhuma identificada"),
            "Palavras-chave ATS: "
            + (
                ", ".join(analise.palavras_chave_ats)
                or "nenhuma sugerida"
            ),
            "",
            "Observação: o score foi calculado pelo serviço com base nos "
            "requisitos classificados pelo Hermes e nas evidências validadas.",
        ]
    )
    secao_analise = "\n".join(linhas)
    caminho_relatorio.write_text(
        f"{conteudo_triagem.rstrip()}\n\n{secao_analise}\n",
        encoding="utf-8",
    )
    return caminho_json, caminho_relatorio


def _diretorio_vaga(
    vaga: Vaga,
    raiz_saida: Path,
    referencia: datetime,
) -> Path:
    return (
        raiz_saida
        / referencia.date().isoformat()
        / _slug(vaga.empresa)
        / f"{_slug(vaga.cargo)}-{_slug(vaga.id_externo)}"
    )


def _slug(valor: str) -> str:
    normalizado = unicodedata.normalize("NFKD", valor)
    sem_acentos = "".join(
        caractere for caractere in normalizado if not unicodedata.combining(caractere)
    )
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", sem_acentos).strip("-").lower()
    return slug or "sem-identificador"
