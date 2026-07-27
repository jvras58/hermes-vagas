from __future__ import annotations

import asyncio
import unittest

from job_hunter.mcp_server import mcp


class TestServidorMcp(unittest.TestCase):
    def test_expoe_fluxo_semantico_e_resumo_diario(self) -> None:
        ferramentas = asyncio.run(mcp.list_tools())
        nomes = {ferramenta.name for ferramenta in ferramentas}

        self.assertIn("get_semantic_analysis_context", nomes)
        self.assertIn("save_semantic_analysis", nomes)
        self.assertIn("get_daily_digest_plan", nomes)
        self.assertIn("build_daily_digest", nomes)


if __name__ == "__main__":
    unittest.main()
