"""
Etapa 3 — Gera a imagem de cada cena a partir da "descricao_visual" do roteiro.

Suporta múltiplos provedores via IMAGE_PROVIDER no .env:
  - "free"     → Pollinations.ai (GRATUITO, sem chave de API, boa para testes)
  - "ideogram" → Ideogram (pago, melhor consistência de estilo/personagem)
  - "openai"   → DALL-E / gpt-image-1 (pago)

Uso:
    python 03_generate_images.py --lenda "curupira"
"""
import argparse
import base64
import json
import os
import urllib.parse
import zlib
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / "config" / ".env")

ROTEIRO_DIR = Path(__file__).parent.parent / "assets" / "roteiros"
IMG_DIR = Path(__file__).parent.parent / "assets" / "imagens"

ESTILO_BASE = (
    "dark folk horror illustration, painterly, moody lighting, Brazilian folklore "
    "atmosphere, vertical 9:16 composition, no text, no watermark"
)


def gerar_imagem_free(prompt: str, destino: Path, **_kwargs):
    """Pollinations.ai: gratuito, sem chave, sem cadastro. Ótimo para testar o pipeline."""
    prompt_completo = f"{prompt}, {ESTILO_BASE}"
    prompt_codificado = urllib.parse.quote(prompt_completo)
    url = (
        f"https://image.pollinations.ai/prompt/{prompt_codificado}"
        f"?width=1024&height=1792&nologo=true"
    )
    resp = requests.get(url, timeout=120)
    resp.raise_for_status()
    destino.write_bytes(resp.content)


def gerar_imagem_openai(prompt: str, destino: Path, **_kwargs):
    resp = requests.post(
        "https://api.openai.com/v1/images/generations",
        headers={"Authorization": f"Bearer {os.environ['OPENAI_API_KEY']}"},
        json={
            "model": "gpt-image-1",
            "prompt": f"{prompt}, {ESTILO_BASE}",
            "size": "1024x1792",
        },
        timeout=120,
    )
    resp.raise_for_status()
    b64 = resp.json()["data"][0]["b64_json"]
    destino.write_bytes(base64.b64decode(b64))


def gerar_imagem_ideogram(prompt: str, destino: Path, seed: int | None = None, **_kwargs):
    image_request = {
        "prompt": f"{prompt}, {ESTILO_BASE}",
        "aspect_ratio": "ASPECT_9_16",
        "model": "V_2",
    }
    if seed is not None:
        # Mesma seed em todas as cenas do vídeo ajuda o Ideogram a manter
        # paleta/estilo mais parecidos entre uma cena e outra.
        image_request["seed"] = seed

    resp = requests.post(
        "https://api.ideogram.ai/generate",
        headers={
            "Api-Key": os.environ["IDEOGRAM_API_KEY"],
            "Content-Type": "application/json",
        },
        json={"image_request": image_request},
        timeout=120,
    )
    resp.raise_for_status()
    url = resp.json()["data"][0]["url"]
    img = requests.get(url, timeout=60)
    destino.write_bytes(img.content)


PROVIDERS = {
    "free": gerar_imagem_free,
    "openai": gerar_imagem_openai,
    "ideogram": gerar_imagem_ideogram,
}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--lenda", required=True)
    args = parser.parse_args()

    slug = args.lenda.lower().replace(" ", "_")
    roteiro = json.loads((ROTEIRO_DIR / f"{slug}.json").read_text(encoding="utf-8"))

    provider = os.environ.get("IMAGE_PROVIDER", "free")
    gerar_imagem = PROVIDERS[provider]
    print(f"Usando provedor de imagem: {provider}")

    out_dir = IMG_DIR / slug
    out_dir.mkdir(parents=True, exist_ok=True)

    # Mesma seed pra todas as cenas de um vídeo, pra ajudar consistência visual
    # entre elas (o Ideogram ignora esse parâmetro nos outros provedores).
    seed = zlib.crc32(slug.encode()) % (2**31)

    for i, cena in enumerate(roteiro["cenas"], start=1):
        destino = out_dir / f"cena_{i}.png"
        # Reforça o nome da lenda no prompt de cada cena, pra ajudar o modelo
        # a manter a mesma aparência do personagem entre as cenas.
        prompt = f"{cena['descricao_visual']}, personagem da lenda do {roteiro['lenda']}"
        gerar_imagem(prompt, destino, seed=seed)
        print(f"Imagem da cena {i} salva em: {destino}")


if __name__ == "__main__":
    main()
