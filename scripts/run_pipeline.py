"""
Orquestrador — roda o pipeline completo para uma lenda:
roteiro → áudio → imagens → montagem → upload

Uso:
    python run_pipeline.py --lenda "curupira"
    python run_pipeline.py --lenda "mula sem cabeca" --sem-upload   # gera mas não publica
"""
import argparse
import subprocess
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).parent


def rodar(script: str, lenda: str):
    print(f"\n{'=' * 50}\n▶ Rodando {script}\n{'=' * 50}")
    resultado = subprocess.run(
        [sys.executable, str(SCRIPTS_DIR / script), "--lenda", lenda], check=False
    )
    if resultado.returncode != 0:
        print(f"Erro em {script}. Pipeline interrompido.")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--lenda", required=True, help='Ex: "curupira", "mula sem cabeça"')
    parser.add_argument(
        "--sem-upload", action="store_true",
        help="Gera o vídeo mas não publica no YouTube (útil para revisar antes)",
    )
    args = parser.parse_args()

    etapas = [
        "01_generate_script.py",
        "02_generate_audio.py",
        "03_generate_images.py",
        "03b_animate_scenes.py",  # pula sozinha se RUNWAY_API_KEY não estiver no .env
        "04_assemble_video.py",
    ]
    if not args.sem_upload:
        etapas.append("05_upload_youtube.py")

    for etapa in etapas:
        rodar(etapa, args.lenda)

    print("\nPipeline concluído com sucesso!")


if __name__ == "__main__":
    main()
