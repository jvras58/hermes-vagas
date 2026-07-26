from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from job_hunter.schemas import Vaga


class FonteVagasMock:
    def __init__(self, caminho: Path) -> None:
        self.caminho = caminho

    def descobrir(self, agora: datetime) -> list[Vaga]:
        registros = json.loads(self.caminho.read_text(encoding="utf-8"))
        if not isinstance(registros, list):
            raise ValueError("o arquivo de vagas mock deve conter uma lista JSON")
        return [self._normalizar(registro, agora) for registro in registros]

    @staticmethod
    def _normalizar(registro: dict[str, Any], agora: datetime) -> Vaga:
        dados = dict(registro)
        horas = dados.pop("publicada_ha_horas", None)
        if horas is not None:
            dados["publicada_em"] = agora - timedelta(hours=float(horas))
        dados.setdefault("coletada_em", agora)
        return Vaga.model_validate(dados)

