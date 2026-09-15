"""
Etapa 4 — Monta o vídeo final: para cada cena, aplica efeito de zoom/pan (Ken Burns)
na imagem estática, sincroniza com a duração do áudio, depois concatena tudo,
adiciona legendas simples (queimadas no vídeo) e exporta em formato 9:16 (Shorts).

Requer ffmpeg instalado no sistema.

Uso:
    python 04_assemble_video.py --lenda "curupira"
"""
import argparse
import json
import os
import platform
import subprocess
import textwrap
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).parent.parent
load_dotenv(BASE_DIR / "config" / ".env")
ROTEIRO_DIR = BASE_DIR / "assets" / "roteiros"
AUDIO_DIR = BASE_DIR / "assets" / "audio"
IMG_DIR = BASE_DIR / "assets" / "imagens"
OUTPUT_DIR = BASE_DIR / "assets" / "output"
TMP_DIR = BASE_DIR / "assets" / "output" / "_tmp"

LARGURA, ALTURA = 1080, 1920  # 9:16
LARGURA_MAX_LEGENDA = 28  # caracteres por linha, antes de quebrar

# drawtext do ffmpeg depende do fontconfig pra achar fonte por nome, e nem
# todo build (principalmente no Windows) vem com fontconfig configurado.
# Por isso apontamos direto pro arquivo .ttf, evitando essa dependência.
FONTES_PADRAO_POR_SO = {
    "Windows": r"C:\Windows\Fonts\arial.ttf",
    "Darwin": "/System/Library/Fonts/Supplemental/Arial.ttf",
    "Linux": "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
}


def resolver_fonte() -> Path:
    caminho = os.environ.get("CAPTION_FONT_FILE") or FONTES_PADRAO_POR_SO.get(
        platform.system(), ""
    )
    if not caminho or not Path(caminho).exists():
        raise FileNotFoundError(
            "Não achei uma fonte .ttf pra legenda. Defina CAPTION_FONT_FILE no "
            "config/.env apontando pro caminho de uma fonte instalada no seu sistema."
        )
    return Path(caminho)


def duracao_audio(path: Path) -> float:
    resultado = subprocess.run(
        [
            "ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1", str(path),
        ],
        capture_output=True, text=True, check=True,
    )
    return float(resultado.stdout.strip())


def montar_cena(imagem: Path, audio: Path, destino: Path, texto_legenda: str):
    dur = duracao_audio(audio)
    # Zoom lento (Ken Burns): zoompan do ffmpeg, com zoom crescente ao longo da cena
    fps = 30
    frames = int(dur * fps)

    legenda_quebrada = "\n".join(textwrap.wrap(texto_legenda, LARGURA_MAX_LEGENDA))
    legenda_escapada = (
        legenda_quebrada.replace("\\", r"\\")
        .replace("'", r"\'")
        .replace(":", r"\:")
        .replace(",", r"\,")
        .replace("%", r"\%")
    )

    # Caminho da fonte pro filtro ffmpeg: barras normais e ":" escapado
    # (ex: Windows "C:\Windows\Fonts\arial.ttf" -> "C\:/Windows/Fonts/arial.ttf")
    fontfile = str(resolver_fonte()).replace("\\", "/").replace(":", r"\:")

    filtro = (
        f"scale=8000:-1,"
        f"zoompan=z='min(zoom+0.0015,1.3)':d={frames}:s={LARGURA}x{ALTURA}:fps={fps},"
        f"drawtext=fontfile='{fontfile}':text='{legenda_escapada}':fontcolor=white:fontsize=54:"
        f"borderw=3:bordercolor=black:x=(w-text_w)/2:y=h-350:"
        f"line_spacing=8:box=0"
    )

    subprocess.run(
        [
            "ffmpeg", "-y",
            "-loop", "1", "-i", str(imagem),
            "-i", str(audio),
            "-filter_complex", filtro,
            "-map", "0:v", "-map", "1:a",
            "-c:v", "libx264", "-c:a", "aac",
            "-t", str(dur),
            "-pix_fmt", "yuv420p",
            str(destino),
        ],
        check=True,
    )


def concatenar_cenas(clips: list[Path], destino_final: Path):
    lista_path = TMP_DIR / "lista.txt"
    lista_path.write_text(
        "\n".join(f"file '{c.resolve()}'" for c in clips), encoding="utf-8"
    )
    subprocess.run(
        [
            "ffmpeg", "-y", "-f", "concat", "-safe", "0",
            "-i", str(lista_path), "-c", "copy", str(destino_final),
        ],
        check=True,
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--lenda", required=True)
    args = parser.parse_args()

    slug = args.lenda.lower().replace(" ", "_")
    roteiro = json.loads((ROTEIRO_DIR / f"{slug}.json").read_text(encoding="utf-8"))

    TMP_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    clips = []
    for i, cena in enumerate(roteiro["cenas"], start=1):
        imagem = IMG_DIR / slug / f"cena_{i}.png"
        audio = AUDIO_DIR / slug / f"cena_{i}.mp3"
        clip_destino = TMP_DIR / f"{slug}_cena_{i}.mp4"

        montar_cena(imagem, audio, clip_destino, cena["texto"])
        clips.append(clip_destino)
        print(f"Cena {i} montada: {clip_destino}")

    video_final = OUTPUT_DIR / f"{slug}.mp4"
    concatenar_cenas(clips, video_final)

    print(f"\nVídeo final gerado em: {video_final}")


if __name__ == "__main__":
    main()
