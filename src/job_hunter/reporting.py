from __future__ import annotations

import re
import unicodedata
from datetime import datetime
from pathlib import Path

from job_hunter.schemas import ConfiguracaoBusca, Vaga


def criar_relatorio_triagem(
    vaga: Vaga,
    configuracao: ConfiguracaoBusca,
    raiz_saida: Path,
    agora: datetime,
) -> Path:
    diretorio = (
        raiz_saida
        / agora.date().isoformat()
        / _slug(vaga.empresa)
        / f"{_slug(vaga.cargo)}-{_slug(vaga.id_externo)}"
    )
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


def _slug(valor: str) -> str:
    normalizado = unicodedata.normalize("NFKD", valor)
    sem_acentos = "".join(
        caractere for caractere in normalizado if not unicodedata.combining(caractere)
    )
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", sem_acentos).strip("-").lower()
    return slug or "sem-identificador"
