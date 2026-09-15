"""
Etapa 3b (opcional) — Anima cada cena com IA (Runway image_to_video),
transformando a imagem estática da etapa 3 num clipe curto com movimento
real (câmera, personagem, ambiente).

Requer RUNWAY_API_KEY no config/.env. Sem essa chave, o pipeline
simplesmente pula essa etapa e a 04_assemble_video.py usa a imagem estática
com zoom/pan (Ken Burns) como sempre.

ATENÇÃO: isso é bem mais caro que gerar só as imagens — Gen-4 Turbo cobra
por segundo de vídeo gerado (https://docs.dev.runwayml.com/api-details/pricing/).
Confira o preço atual antes de rodar em lote.

Uso:
    python 03b_animate_scenes.py --lenda "curupira"

Gera um .mp4 por cena em assets/video_cenas/<lenda>/cena_N.mp4
"""
import argparse
import base64
import json
import os
import time
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / "config" / ".env")

ROTEIRO_DIR = Path(__file__).parent.parent / "assets" / "roteiros"
IMG_DIR = Path(__file__).parent.parent / "assets" / "imagens"
AUDIO_DIR = Path(__file__).parent.parent / "assets" / "audio"
VIDEO_CENAS_DIR = Path(__file__).parent.parent / "assets" / "video_cenas"

RUNWAY_BASE_URL = "https://api.dev.runwayml.com/v1"
RUNWAY_VERSION = "2024-11-06"

MOTION_SUFFIXO = (
    "sutis movimentos de câmera e de personagem, estilo graphic novel animado, "
    "sem cortes bruscos, sem mudança de cenário"
)


def _headers() -> dict:
    return {
        "Authorization": f"Bearer {os.environ['RUNWAY_API_KEY']}",
        "Content-Type": "application/json",
        "X-Runway-Version": RUNWAY_VERSION,
    }


def _duracao_alvo(audio_path: Path) -> int:
    """Runway aceita duração em segundos inteiros; escolhe 5 ou 10 conforme
    o tamanho da narração da cena (o ffmpeg depois ajusta/loopa pro tamanho exato)."""
    import subprocess

    resultado = subprocess.run(
        [
            "ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1", str(audio_path),
        ],
        capture_output=True, text=True, check=True,
    )
    dur = float(resultado.stdout.strip())
    return 5 if dur <= 5 else 10


def _submeter_tarefa(imagem: Path, prompt_texto: str, duracao: int) -> str:
    b64 = base64.b64encode(imagem.read_bytes()).decode()
    prompt_image = f"data:image/png;base64,{b64}"

    model = os.environ.get("RUNWAY_MODEL", "gen4_turbo")
    ratio = os.environ.get("RUNWAY_RATIO", "720:1280")

    resp = requests.post(
        f"{RUNWAY_BASE_URL}/image_to_video",
        headers=_headers(),
        json={
            "model": model,
            "promptImage": prompt_image,
            "promptText": prompt_texto[:1000],
            "ratio": ratio,
            "duration": duracao,
        },
        timeout=60,
    )
    resp.raise_for_status()
    return resp.json()["id"]


def _aguardar_tarefa(task_id: str, timeout_s: int = 300) -> str:
    """Espera a tarefa terminar e retorna a URL do vídeo gerado."""
    inicio = time.monotonic()
    while time.monotonic() - inicio < timeout_s:
        resp = requests.get(
            f"{RUNWAY_BASE_URL}/tasks/{task_id}", headers=_headers(), timeout=30
        )
        resp.raise_for_status()
        dados = resp.json()
        status = dados["status"]

        if status == "SUCCEEDED":
            return dados["output"][0]
        if status in ("FAILED", "CANCELLED"):
            raise RuntimeError(f"Tarefa Runway {task_id} falhou: {dados.get('failure', status)}")

        time.sleep(5)

    raise TimeoutError(f"Tarefa Runway {task_id} não terminou em {timeout_s}s")


def animar_cena(imagem: Path, audio: Path, prompt_visual: str, destino: Path):
    duracao = _duracao_alvo(audio)
    prompt_texto = f"{prompt_visual}, {MOTION_SUFFIXO}"

    task_id = _submeter_tarefa(imagem, prompt_texto, duracao)
    url_video = _aguardar_tarefa(task_id)

    video = requests.get(url_video, timeout=120)
    video.raise_for_status()
    destino.write_bytes(video.content)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--lenda", required=True)
    args = parser.parse_args()

    if not os.environ.get("RUNWAY_API_KEY"):
        print("RUNWAY_API_KEY não configurada — pulando animação (vai usar imagem estática + zoom).")
        return

    slug = args.lenda.lower().replace(" ", "_")
    roteiro = json.loads((ROTEIRO_DIR / f"{slug}.json").read_text(encoding="utf-8"))

    out_dir = VIDEO_CENAS_DIR / slug
    out_dir.mkdir(parents=True, exist_ok=True)

    for i, cena in enumerate(roteiro["cenas"], start=1):
        imagem = IMG_DIR / slug / f"cena_{i}.png"
        audio = AUDIO_DIR / slug / f"cena_{i}.mp3"
        destino = out_dir / f"cena_{i}.mp4"

        print(f"Animando cena {i}/{len(roteiro['cenas'])}... (isso demora, pode levar alguns minutos)")
        animar_cena(imagem, audio, cena["descricao_visual"], destino)
        print(f"Cena {i} animada: {destino}")


if __name__ == "__main__":
    main()
