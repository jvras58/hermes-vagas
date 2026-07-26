from __future__ import annotations

import json
from pathlib import Path

from pydantic import ValidationError

from job_hunter.schemas import ConfiguracaoBusca


class ErroConfiguracao(ValueError):
    pass


def carregar_configuracao(caminho: Path) -> ConfiguracaoBusca:
    try:
        conteudo = caminho.read_text(encoding="utf-8")
        dados = json.loads(conteudo)
        return ConfiguracaoBusca.model_validate(dados)
    except FileNotFoundError as erro:
        raise ErroConfiguracao(f"configuração não encontrada: {caminho}") from erro
    except json.JSONDecodeError as erro:
        raise ErroConfiguracao(
            f"JSON inválido em {caminho}: linha {erro.lineno}, coluna {erro.colno}"
        ) from erro
    except ValidationError as erro:
        raise ErroConfiguracao(
            f"configuração inválida em {caminho}:\n{erro}"
        ) from erro

