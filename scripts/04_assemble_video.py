"""
Etapa 4 — Monta o vídeo final: para cada cena, aplica efeito de zoom/pan (Ken Burns)
na imagem estática, sincroniza com a duração do áudio, adiciona legendas dinâmicas
(blocos curtos de 2-3 palavras, sincronizados com a fala quando há timing
disponível — veja a etapa 2) e exporta em formato 9:16 (Shorts).

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
LARGURA_MAX_LEGENDA = 28  # caracteres por linha, no modo sem timing (bloco único)

# Legenda dinâmica: agrupa as palavras em blocos curtos
MAX_PALAVRAS_POR_BLOCO = 3
MAX_CHARS_POR_BLOCO = 20
COR_LEGENDA = "#FFD60A"  # amarelo vibrante, chamativo sobre o fundo escuro
FONTSIZE_DINAMICO = 64
POP_DURACAO = 0.12  # segundos da animação de entrada de cada bloco

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


def escapar_drawtext(texto: str) -> str:
    return (
        texto.replace("\\", r"\\")
        .replace("'", r"\'")
        .replace(":", r"\:")
        .replace(",", r"\,")
        .replace("%", r"\%")
    )


def agrupar_em_blocos(palavras: list[dict]) -> list[list[dict]]:
    blocos = []
    atual: list[dict] = []
    for p in palavras:
        candidato = [*atual, p]
        texto_candidato = " ".join(w["palavra"] for w in candidato)
        cabe = len(candidato) <= MAX_PALAVRAS_POR_BLOCO and len(texto_candidato) <= MAX_CHARS_POR_BLOCO
        if atual and not cabe:
            blocos.append(atual)
            atual = [p]
        else:
            atual = candidato
    if atual:
        blocos.append(atual)
    return blocos


def legenda_dinamica_filtros(fontfile: str, palavras: list[dict], dur: float) -> str:
    blocos = agrupar_em_blocos(palavras)
    filtros = []
    for idx, bloco in enumerate(blocos):
        inicio = max(0.0, bloco[0]["inicio"])
        fim = blocos[idx + 1][0]["inicio"] if idx + 1 < len(blocos) else dur
        texto = escapar_drawtext(" ".join(w["palavra"] for w in bloco).upper())

        # Entrada em "pop": desliza de baixo pra cima e ganha opacidade
        alpha_expr = f"if(lt(t,{inicio}+{POP_DURACAO}),(t-{inicio})/{POP_DURACAO},1)"
        y_expr = f"h-350+max(0,18*(1-min((t-{inicio})/{POP_DURACAO},1)))"

        filtros.append(
            f"drawtext=fontfile='{fontfile}':text='{texto}':fontcolor={COR_LEGENDA}:"
            f"fontsize={FONTSIZE_DINAMICO}:borderw=4:bordercolor=black:"
            f"x=(w-text_w)/2:y='{y_expr}':alpha='{alpha_expr}':"
            f"enable='between(t,{inicio},{fim})'"
        )
    return ",".join(filtros)


def legenda_estatica_filtro(fontfile: str, texto_legenda: str) -> str:
    """Fallback pra quando não há timing por palavra (ex: áudio gerado antes
    dessa funcionalidade, ou provedor sem suporte a timing)."""
    legenda_quebrada = "\n".join(textwrap.wrap(texto_legenda, LARGURA_MAX_LEGENDA))
    texto = escapar_drawtext(legenda_quebrada)
    return (
        f"drawtext=fontfile='{fontfile}':text='{texto}':fontcolor=white:fontsize=54:"
        f"borderw=3:bordercolor=black:x=(w-text_w)/2:y=h-350:line_spacing=8:box=0"
    )


def montar_cena(
    imagem: Path, audio: Path, destino: Path, texto_legenda: str, palavras: list[dict] | None
):
    dur = duracao_audio(audio)
    # Zoom lento (Ken Burns): zoompan do ffmpeg, com zoom crescente ao longo da cena
    fps = 30
    frames = int(dur * fps)

    # Caminho da fonte pro filtro ffmpeg: barras normais e ":" escapado
    # (ex: Windows "C:\Windows\Fonts\arial.ttf" -> "C\:/Windows/Fonts/arial.ttf")
    fontfile = str(resolver_fonte()).replace("\\", "/").replace(":", r"\:")

    if palavras:
        legenda_filtros = legenda_dinamica_filtros(fontfile, palavras, dur)
    else:
        legenda_filtros = legenda_estatica_filtro(fontfile, texto_legenda)

    filtro = (
        f"[0:v]scale=8000:-1,"
        f"zoompan=z='min(zoom+0.0015,1.3)':d={frames}:s={LARGURA}x{ALTURA}:fps={fps},"
        f"{legenda_filtros}[vout]"
    )

    subprocess.run(
        [
            "ffmpeg", "-y",
            "-loop", "1", "-i", str(imagem),
            "-i", str(audio),
            "-filter_complex", filtro,
            "-map", "[vout]", "-map", "1:a",
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


def resolver_musica_fundo() -> Path | None:
    caminho = os.environ.get("BACKGROUND_MUSIC_FILE")
    if not caminho:
        return None
    caminho_path = Path(caminho)
    if not caminho_path.exists():
        print(f"Aviso: BACKGROUND_MUSIC_FILE aponta pra um arquivo que não existe: {caminho_path}")
        return None
    return caminho_path


def adicionar_musica_fundo(video_sem_musica: Path, musica: Path, destino_final: Path):
    volume = os.environ.get("BACKGROUND_MUSIC_VOLUME", "0.12")
    subprocess.run(
        [
            "ffmpeg", "-y",
            "-i", str(video_sem_musica),
            "-stream_loop", "-1", "-i", str(musica),
            "-filter_complex",
            (
                f"[1:a]volume={volume}[musica_baixa];"
                f"[0:a][musica_baixa]amix=inputs=2:duration=first:dropout_transition=2[aout]"
            ),
            "-map", "0:v", "-map", "[aout]",
            "-c:v", "copy", "-c:a", "aac",
            "-shortest",
            str(destino_final),
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
        timing_path = AUDIO_DIR / slug / f"cena_{i}.timing.json"
        clip_destino = TMP_DIR / f"{slug}_cena_{i}.mp4"

        palavras = None
        if timing_path.exists():
            palavras = json.loads(timing_path.read_text(encoding="utf-8"))

        montar_cena(imagem, audio, clip_destino, cena["texto"], palavras)
        clips.append(clip_destino)
        print(f"Cena {i} montada: {clip_destino}")

    video_final = OUTPUT_DIR / f"{slug}.mp4"
    musica = resolver_musica_fundo()

    if musica:
        video_sem_musica = TMP_DIR / f"{slug}_sem_musica.mp4"
        concatenar_cenas(clips, video_sem_musica)
        adicionar_musica_fundo(video_sem_musica, musica, video_final)
        print(f"Música de fundo adicionada: {musica}")
    else:
        concatenar_cenas(clips, video_final)

    print(f"\nVídeo final gerado em: {video_final}")


if __name__ == "__main__":
    main()
