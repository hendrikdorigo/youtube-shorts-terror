"""
Etapa 2 — Gera a narração em áudio para cada cena do roteiro.

Suporta dois provedores, escolhidos via TTS_PROVIDER no .env:
  - "free"       → edge-tts (Microsoft, GRATUITO, sem chave de API, boa qualidade em pt-BR)
  - "elevenlabs" → ElevenLabs (pago, voz mais expressiva/customizável)

Uso:
    python 02_generate_audio.py --lenda "curupira"

Gera um .mp3 por cena em assets/audio/<lenda>/cena_N.mp3
"""
import argparse
import asyncio
import json
import os
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / "config" / ".env")

ROTEIRO_DIR = Path(__file__).parent.parent / "assets" / "roteiros"
AUDIO_DIR = Path(__file__).parent.parent / "assets" / "audio"

ELEVENLABS_TTS_URL = "https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"


def gerar_audio_elevenlabs(texto: str, destino: Path):
    voice_id = os.environ["ELEVENLABS_VOICE_ID"]
    api_key = os.environ["ELEVENLABS_API_KEY"]

    resp = requests.post(
        ELEVENLABS_TTS_URL.format(voice_id=voice_id),
        headers={
            "xi-api-key": api_key,
            "Content-Type": "application/json",
        },
        json={
            "text": texto,
            "model_id": "eleven_multilingual_v2",
            "voice_settings": {"stability": 0.5, "similarity_boost": 0.8},
        },
        timeout=60,
    )
    resp.raise_for_status()
    destino.write_bytes(resp.content)


def gerar_audio_free(texto: str, destino: Path):
    """edge-tts: gratuito, sem chave, usa as vozes neurais do Microsoft Edge."""
    import edge_tts

    # Vozes pt-BR disponíveis: pt-BR-AntonioNeural (masc.) / pt-BR-FranciscaNeural (fem.)
    voz = os.environ.get("EDGE_TTS_VOICE", "pt-BR-AntonioNeural")

    async def _gerar():
        communicate = edge_tts.Communicate(texto, voice=voz, rate="-5%")
        await communicate.save(str(destino))

    asyncio.run(_gerar())


PROVIDERS = {
    "free": gerar_audio_free,
    "elevenlabs": gerar_audio_elevenlabs,
}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--lenda", required=True)
    args = parser.parse_args()

    slug = args.lenda.lower().replace(" ", "_")
    roteiro = json.loads((ROTEIRO_DIR / f"{slug}.json").read_text(encoding="utf-8"))

    provider = os.environ.get("TTS_PROVIDER", "free")
    gerar_audio = PROVIDERS[provider]
    print(f"Usando provedor de voz: {provider}")

    out_dir = AUDIO_DIR / slug
    out_dir.mkdir(parents=True, exist_ok=True)

    max_tentativas = 3
    for i, cena in enumerate(roteiro["cenas"], start=1):
        destino = out_dir / f"cena_{i}.mp3"

        for tentativa in range(1, max_tentativas + 1):
            gerar_audio(cena["texto"], destino)
            if destino.exists() and destino.stat().st_size > 0:
                break
            print(f"Aviso: áudio da cena {i} saiu vazio (tentativa {tentativa}/{max_tentativas})")
        else:
            raise RuntimeError(
                f"Falha ao gerar áudio da cena {i} após {max_tentativas} tentativas "
                f"(arquivo ficou vazio: {destino}). Verifique sua conexão e tente novamente."
            )

        print(f"Áudio da cena {i} salvo em: {destino}")


if __name__ == "__main__":
    main()
