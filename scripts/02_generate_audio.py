"""
Etapa 2 — Gera a narração em áudio para cada cena do roteiro.

Suporta dois provedores, escolhidos via TTS_PROVIDER no .env:
  - "free"       → edge-tts (Microsoft, GRATUITO, sem chave de API, boa qualidade em pt-BR)
  - "elevenlabs" → ElevenLabs (pago, voz mais expressiva/customizável)

Quando o provedor consegue, também salva o timing de cada palavra em
cena_N.timing.json (usado pela etapa 4 pra montar legendas dinâmicas
sincronizadas com a fala).

Uso:
    python 02_generate_audio.py --lenda "curupira"

Gera um .mp3 por cena em assets/audio/<lenda>/cena_N.mp3
"""
import argparse
import asyncio
import base64
import json
import os
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / "config" / ".env")

ROTEIRO_DIR = Path(__file__).parent.parent / "assets" / "roteiros"
AUDIO_DIR = Path(__file__).parent.parent / "assets" / "audio"

ELEVENLABS_TTS_URL = "https://api.elevenlabs.io/v1/text-to-speech/{voice_id}/with-timestamps"


def _palavras_do_alignment(alignment: dict) -> list[dict]:
    """Agrupa o alinhamento por caractere da ElevenLabs em palavras com início/fim."""
    chars = alignment["characters"]
    inicios = alignment["character_start_times_seconds"]
    fins = alignment["character_end_times_seconds"]

    palavras = []
    atual = ""
    inicio = None
    fim = None
    for ch, s, e in zip(chars, inicios, fins):
        if ch.isspace():
            if atual:
                palavras.append({"palavra": atual, "inicio": inicio, "fim": fim})
                atual = ""
                inicio = None
            continue
        if inicio is None:
            inicio = s
        atual += ch
        fim = e
    if atual:
        palavras.append({"palavra": atual, "inicio": inicio, "fim": fim})
    return palavras


def gerar_audio_elevenlabs(texto: str, destino: Path) -> list[dict]:
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
    data = resp.json()
    destino.write_bytes(base64.b64decode(data["audio_base64"]))
    return _palavras_do_alignment(data["alignment"])


def gerar_audio_free(texto: str, destino: Path) -> list[dict]:
    """edge-tts: gratuito, sem chave, usa as vozes neurais do Microsoft Edge."""
    import edge_tts

    # Vozes pt-BR disponíveis: pt-BR-AntonioNeural (masc.) / pt-BR-FranciscaNeural (fem.)
    voz = os.environ.get("EDGE_TTS_VOICE", "pt-BR-AntonioNeural")

    async def _gerar():
        communicate = edge_tts.Communicate(texto, voice=voz, rate="-5%")
        audio_partes = []
        palavras = []
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_partes.append(chunk["data"])
            elif chunk["type"] == "WordBoundary":
                palavras.append(
                    {
                        "palavra": chunk["text"],
                        "inicio": chunk["offset"] / 10_000_000,
                        "fim": (chunk["offset"] + chunk["duration"]) / 10_000_000,
                    }
                )
        return audio_partes, palavras

    audio_partes, palavras = asyncio.run(_gerar())
    destino.write_bytes(b"".join(audio_partes))
    return palavras


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
        timing_path = out_dir / f"cena_{i}.timing.json"

        palavras = []
        for tentativa in range(1, max_tentativas + 1):
            palavras = gerar_audio(cena["texto"], destino)
            if destino.exists() and destino.stat().st_size > 0:
                break
            print(f"Aviso: áudio da cena {i} saiu vazio (tentativa {tentativa}/{max_tentativas})")
        else:
            raise RuntimeError(
                f"Falha ao gerar áudio da cena {i} após {max_tentativas} tentativas "
                f"(arquivo ficou vazio: {destino}). Verifique sua conexão e tente novamente."
            )

        if palavras:
            timing_path.write_text(
                json.dumps(palavras, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        elif timing_path.exists():
            # Evita usar timing de uma geração anterior com outro provedor/texto
            timing_path.unlink()

        print(f"Áudio da cena {i} salvo em: {destino}")


if __name__ == "__main__":
    main()
