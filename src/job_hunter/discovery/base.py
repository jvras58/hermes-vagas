from __future__ import annotations

from datetime import datetime
from typing import Protocol

from job_hunter.schemas import Vaga


class FonteVagas(Protocol):
    def descobrir(self, agora: datetime) -> list[Vaga]:
        ...

