"""
Etapa 5 — Publica o vídeo final no YouTube como Short, via YouTube Data API v3.

Pré-requisito (uma vez só):
    1. Criar projeto no Google Cloud Console
    2. Ativar "YouTube Data API v3"
    3. Criar credencial OAuth2 tipo "Desktop App"
    4. Baixar o JSON e salvar em config/client_secret.json

Na primeira execução, abre o navegador para autorizar sua conta do YouTube.
Depois disso, o token fica salvo em config/youtube_token.json e reautentica sozinho.

Uso:
    python 05_upload_youtube.py --lenda "curupira"
"""
import argparse
import json
import os
from pathlib import Path

from dotenv import load_dotenv
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

load_dotenv(Path(__file__).parent.parent / "config" / ".env")

BASE_DIR = Path(__file__).parent.parent
ROTEIRO_DIR = BASE_DIR / "assets" / "roteiros"
OUTPUT_DIR = BASE_DIR / "assets" / "output"

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]


def autenticar():
    token_path = Path(os.environ["YOUTUBE_TOKEN_PATH"])
    client_secret_path = Path(os.environ["YOUTUBE_CLIENT_SECRET_PATH"])

    creds = None
    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                str(client_secret_path), SCOPES
            )
            creds = flow.run_local_server(port=0)
        token_path.write_text(creds.to_json(), encoding="utf-8")

    return build("youtube", "v3", credentials=creds)


def publicar(video_path: Path, titulo: str, descricao: str, tags: list[str]):
    youtube = autenticar()

    body = {
        "snippet": {
            "title": titulo,
            "description": descricao,
            "tags": tags,
            "categoryId": "24",  # Entertainment
        },
        "status": {
            "privacyStatus": os.environ.get("YOUTUBE_PRIVACY_STATUS", "private"),
            "selfDeclaredMadeForKids": False,
        },
    }

    media = MediaFileUpload(str(video_path), chunksize=-1, resumable=True)
    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)
    response = request.execute()

    print(f"Publicado! ID do vídeo: {response['id']}")
    print(f"Link: https://youtube.com/shorts/{response['id']}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--lenda", required=True)
    args = parser.parse_args()

    slug = args.lenda.lower().replace(" ", "_")
    roteiro = json.loads((ROTEIRO_DIR / f"{slug}.json").read_text(encoding="utf-8"))
    video_path = OUTPUT_DIR / f"{slug}.mp4"

    titulo = f"{roteiro['titulo']} #shorts #folclorebrasileiro #terror"
    descricao = (
        f"A lenda de {roteiro['lenda']} — folclore brasileiro em forma de terror.\n\n"
        f"#folclore #terror #shorts #lendasbrasileiras"
    )
    tags = ["folclore brasileiro", "terror", "shorts", roteiro["lenda"], "lendas"]

    publicar(video_path, titulo, descricao, tags)


if __name__ == "__main__":
    main()
