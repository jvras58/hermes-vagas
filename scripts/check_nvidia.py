from __future__ import annotations

import argparse
import os
import sys

from openai import OpenAI

BASE_URL_PADRAO = "https://integrate.api.nvidia.com/v1"
MODELO_PADRAO = "z-ai/glm-5.2"


def criar_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Testa a credencial NVIDIA sem iniciar o Hermes.",
    )
    parser.add_argument("--model", default=MODELO_PADRAO)
    parser.add_argument(
        "--prompt",
        default="Responda somente com: NVIDIA OK",
    )
    parser.add_argument("--max-tokens", type=int, default=256)
    return parser


def main() -> None:
    argumentos = criar_parser().parse_args()
    api_key = os.getenv("NVIDIA_API_KEY")
    if not api_key:
        raise SystemExit(
            "NVIDIA_API_KEY não foi definida. Carregue o .env antes do teste."
        )

    client = OpenAI(
        base_url=os.getenv("NVIDIA_BASE_URL", BASE_URL_PADRAO),
        api_key=api_key,
    )
    resposta = client.chat.completions.create(
        model=argumentos.model,
        messages=[{"role": "user", "content": argumentos.prompt}],
        temperature=1,
        top_p=1,
        max_tokens=argumentos.max_tokens,
        seed=42,
        stream=True,
    )

    usar_cor = sys.stdout.isatty() and os.getenv("NO_COLOR") is None
    cor_raciocinio = "\033[90m" if usar_cor else ""
    reset = "\033[0m" if usar_cor else ""

    for chunk in resposta:
        escolhas = getattr(chunk, "choices", None)
        if not escolhas:
            continue
        delta = getattr(escolhas[0], "delta", None)
        if delta is None:
            continue

        raciocinio = getattr(delta, "reasoning_content", None)
        if raciocinio:
            print(f"{cor_raciocinio}{raciocinio}{reset}", end="", flush=True)

        conteudo = getattr(delta, "content", None)
        if conteudo:
            print(conteudo, end="", flush=True)

    print()


if __name__ == "__main__":
    main()

