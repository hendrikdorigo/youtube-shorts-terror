"""
Etapa 1 — Gera o roteiro de uma lenda do folclore brasileiro
formatado para YouTube Shorts (30-60s de narração).

Uso:
    python 01_generate_script.py --lenda "curupira"
"""
import argparse
import json
import os
from pathlib import Path

from dotenv import load_dotenv
from anthropic import Anthropic

load_dotenv(Path(__file__).parent.parent / "config" / ".env")

ROTEIRO_DIR = Path(__file__).parent.parent / "assets" / "roteiros"

PROMPT_TEMPLATE = """Você é um roteirista especializado em terror curto para YouTube Shorts.

Escreva um roteiro de terror sobre a lenda brasileira: {lenda}

Regras:
- Narração de 130 a 170 palavras (cabe em 45-60 segundos de fala)
- Estrutura: gancho nos primeiros 3 segundos, tensão crescente, virada final assustadora
- Tom: sombrio, envolvente, em português do Brasil
- Divida em 4 a 6 CENAS, cada uma com:
  - "texto": a fala narrada daquele trecho
  - "descricao_visual": descrição da imagem/cena para gerar a arte (estilo dark folk art,
    sem elementos com direitos autorais, foco no personagem e ambiente)

Responda APENAS em JSON válido, neste formato exato, sem markdown, sem comentários:
{{
  "titulo": "string curto pro vídeo",
  "lenda": "{lenda}",
  "cenas": [
    {{"texto": "...", "descricao_visual": "..."}}
  ]
}}
"""


MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-5")


def gerar_roteiro(lenda: str) -> dict:
    client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    response = client.messages.create(
        model=MODEL,
        max_tokens=1500,
        messages=[{"role": "user", "content": PROMPT_TEMPLATE.format(lenda=lenda)}],
    )
    texto = response.content[0].text.strip()
    # remove possíveis blocos de código markdown, caso venham
    texto = texto.replace("```json", "").replace("```", "").strip()

    try:
        roteiro = json.loads(texto)
    except json.JSONDecodeError as e:
        raise ValueError(
            f"A resposta do modelo não veio em JSON válido: {e}\nResposta bruta:\n{texto}"
        ) from e

    if not roteiro.get("cenas"):
        raise ValueError(f"Roteiro gerado sem cenas: {roteiro}")

    return roteiro


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--lenda", required=True, help="Nome da lenda, ex: curupira")
    args = parser.parse_args()

    roteiro = gerar_roteiro(args.lenda)

    ROTEIRO_DIR.mkdir(parents=True, exist_ok=True)
    out_path = ROTEIRO_DIR / f"{args.lenda.lower().replace(' ', '_')}.json"
    out_path.write_text(json.dumps(roteiro, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Roteiro salvo em: {out_path}")
    print(f"Título: {roteiro['titulo']}")
    print(f"Cenas: {len(roteiro['cenas'])}")


if __name__ == "__main__":
    main()
