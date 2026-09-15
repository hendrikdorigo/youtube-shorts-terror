# Folclore Shorts — Pipeline de Automação

Pipeline para gerar Shorts de histórias animadas de terror do folclore brasileiro,
do roteiro até o upload no YouTube.

## Arquitetura do fluxo

```
01_generate_script.py   → gera roteiro (texto) de uma lenda
        ↓
02_generate_audio.py    → narração em voz (ElevenLabs)
        ↓
03_generate_images.py   → imagens estilo storybook (Midjourney/Ideogram/DALL-E — API externa)
        ↓
04_assemble_video.py    → monta o vídeo (ffmpeg: zoom/pan + áudio + legendas)
        ↓
05_upload_youtube.py    → publica no YouTube como Short (YouTube Data API v3)
```

`run_pipeline.py` roda as 5 etapas em sequência para uma lenda por vez.

## Estrutura de pastas

```
folclore-shorts/
├── config/
│   └── .env.example       ← copie para .env e preencha suas chaves
├── scripts/
│   ├── 01_generate_script.py
│   ├── 02_generate_audio.py
│   ├── 03_generate_images.py
│   ├── 04_assemble_video.py
│   ├── 05_upload_youtube.py
│   └── run_pipeline.py
├── assets/
│   ├── roteiros/    ← roteiros gerados (.json)
│   ├── audio/        ← narrações geradas (.mp3)
│   ├── imagens/       ← imagens geradas por lenda (.png)
│   └── output/        ← vídeos finais (.mp4)
└── requirements.txt
```

## Modo GRATUITO para testar (recomendado no início)

O `.env.example` já vem configurado no modo gratuito por padrão:

- **Voz** → `TTS_PROVIDER=free` usa o **edge-tts** (vozes neurais da Microsoft, sem
  custo e sem chave de API — só precisa de internet). Qualidade boa, mas menos
  expressiva que a ElevenLabs.
- **Imagem** → `IMAGE_PROVIDER=free` usa o **Pollinations.ai** (gratuito, sem
  cadastro, sem chave). A consistência visual entre cenas é menor que Ideogram/
  DALL-E, mas serve bem para validar o formato e o ritmo do vídeo.
- **Upload** → YouTube API é gratuito em qualquer modo (tem só um limite de
  cota diária de uploads, não de custo).

Nesse modo, o **único gasto real é a API da Anthropic para o roteiro** — e mesmo
assim, poucos centavos por vídeo (ou zero, se você gerar o roteiro manualmente
aqui no chat e colar o JSON em `assets/roteiros/`).

Depois de validar o formato, é só trocar `TTS_PROVIDER=elevenlabs` e/ou
`IMAGE_PROVIDER=ideogram` no `.env` para subir a qualidade — sem mexer em
nenhum script.

## Publicação no YouTube

Por padrão, os vídeos são publicados como **`private`** (`YOUTUBE_PRIVACY_STATUS`
no `.env`), para você revisar antes de tornar público — troque para `public`
ou `unlisted` só depois de validar o resultado. O `.env` e as credenciais
(`client_secret.json`, `youtube_token.json`) já ficam fora do git via
`.gitignore`.

## O que você precisa configurar (uma vez)

**Se for usar o modo gratuito:** nenhuma chave é necessária para voz e imagem —
só o `ANTHROPIC_API_KEY` para o roteiro (etapa 1) e a credencial do Google para
o upload (etapa 5, sempre necessária).

**Se quiser qualidade paga:**

1. **ElevenLabs** — conta + API key → narração
   https://elevenlabs.io/app/settings/api-keys

2. **Serviço de geração de imagem** (escolha um) — conta + API key:
   - Ideogram (bom para estilo consistente de personagem)
   - DALL-E (OpenAI API)

3. **Google Cloud / YouTube Data API v3** — para upload automático (sempre necessário):
   - Criar projeto no Google Cloud Console
   - Ativar "YouTube Data API v3"
   - Criar credenciais OAuth2 (tipo "Desktop App")
   - Baixar `client_secret.json` e colocar em `config/`
   - Na primeira execução do `05_upload_youtube.py`, vai abrir o navegador
     para você autorizar — depois disso o token fica salvo e é automático

4. **ffmpeg** instalado na máquina (não precisa de API key, é local):
   ```
   sudo apt install ffmpeg   # Linux
   brew install ffmpeg       # Mac
   ```

## Como rodar

```bash
pip install -r requirements.txt
cp config/.env.example config/.env
# preencha o config/.env com suas chaves

python scripts/run_pipeline.py --lenda "curupira"
```

## Custo estimado por vídeo (referência, pode variar)

| Etapa | Serviço | Custo aproximado |
|---|---|---|
| Narração (~200 palavras) | ElevenLabs | ~$0,05–0,15 |
| Imagens (4-6 cenas) | Ideogram/DALL-E | ~$0,20–0,60 |
| Montagem (ffmpeg) | Local | grátis |
| Upload | YouTube API | grátis (limite de cota diária) |

**Total por Short: ~$0,25–0,75**, dependendo do serviço de imagem escolhido.

## Próximos passos sugeridos

- Testar 1 vídeo end-to-end manualmente antes de automatizar em lote
- Ajustar o prompt de estilo visual em `03_generate_images.py` até achar
  a estética que combina com o canal (ex: "dark folk art", "pixar horror style")
- Depois de validado, agendar `run_pipeline.py` via cron ou n8n para rodar
  N vezes por semana com lendas diferentes de uma lista
