"""
Bot Deployd - Teams → n8n
Trata texto, imagens e documentos. Anexos são baixados, convertidos em Base64
e classificados antes de enviar ao n8n.
"""
from flask import Flask, request, jsonify   
import re
import os
import base64
import requests

app = Flask(__name__)

IA_WEBHOOK_URL = os.environ.get(
    "IA_WEBHOOK_URL",
    "https://primary-production-f46c1.up.railway.app/webhook-test/10ba380d-3a85-4fa9-a556-9673c294d40d",
)

# Tipos MIME considerados imagem
IMAGE_MIMES = {
    "image/png", "image/jpeg", "image/jpg",
    "image/gif", "image/webp", "image/bmp",
}

# Extensões aceitas como documento
DOC_EXTS = {
    "pdf", "docx", "doc", "xlsx", "xls",
    "csv", "txt", "pptx", "ppt", "rtf", "odt",
}
IMG_EXTS = {"png", "jpg", "jpeg", "gif", "webp", "bmp"}

# ---------- Utilitários ----------

def extrair_texto(texto: str) -> str:
    """Remove HTML/menções do texto vindo do Teams."""
    if not texto:
        return ""
    texto = re.sub(r'<a[^>]*href="mailto:([^"]+)"[^>]*>.*?</a>', r"\1", texto)
    texto = re.sub(r"<at>[^<]+</at>", "", texto)
    texto = re.sub(r"<[^>]+>", "", texto)
    texto = texto.replace("&nbsp;", " ").strip()
    return texto


def extensao(nome: str) -> str:
    return nome.rsplit(".", 1)[-1].lower() if nome and "." in nome else ""


def classificar(content_type: str, nome: str) -> str | None:
    """Retorna 'imagem', 'documento' ou None."""
    ct = (content_type or "").lower()
    if ct in IMAGE_MIMES or ct.startswith("image/"):
        return "imagem"
    ext = extensao(nome)
    if ext in IMG_EXTS:
        return "imagem"
    if ext in DOC_EXTS:
        return "documento"
    return None


def baixar_b64(url: str) -> str | None:
    """Baixa o conteúdo da URL e devolve em Base64."""
    try:
        r = requests.get(url, timeout=60)
        r.raise_for_status()
        return base64.b64encode(r.content).decode("utf-8")
    except Exception as e:
        print(f"[DOWNLOAD] Falha em {url}: {e}")
        return None


def processar_anexos(attachments: list) -> list:
    """Converte cada anexo em {tipo, nome, extensao, mime, base64}."""
    saida = []
    for att in attachments or []:
        content_type = att.get("contentType", "") or ""
        nome = att.get("name", "") or ""

        url_download = None
        ext = extensao(nome)

        # Arquivos enviados via Teams (channel/chat file)
        if "teams.file.download.info" in content_type.lower():
            content = att.get("content", {}) or {}
            url_download = content.get("downloadUrl")
            file_type = (content.get("fileType") or "").lower()
            if file_type and not ext:
                ext = file_type
                if nome and "." not in nome:
                    nome = f"{nome}.{file_type}"

        # Imagens inline / cartões com contentUrl direto
        elif content_type.startswith("image/") or att.get("contentUrl"):
            url_download = att.get("contentUrl")

        if not url_download:
            continue

        tipo = classificar(content_type, nome)
        if not tipo:
            print(f"[ANEXO] ignorado (sem classificação) nome={nome} ct={content_type}")
            continue

        b64 = baixar_b64(url_download)
        if not b64:
            continue

        saida.append({
            "tipo": tipo,
            "nome": nome or f"arquivo.{ext or 'bin'}",
            "extensao": ext,
            "mime": content_type,
            "base64": b64,
        })
    return saida


# ---------- Rotas ----------

@app.route("/webhook", methods=["POST"])
def webhook():
    dados = request.json
    if not dados:
        return jsonify({"type": "message", "text": "Erro ao processar mensagem."}), 200

    texto = extrair_texto(dados.get("text", ""))
    usuario = dados.get("from", {}) or {}
    nome = usuario.get("name", "Desconhecido")
    aad_object_id = usuario.get("aadObjectId", "")
    attachments = dados.get("attachments", []) or []

    anexos = processar_anexos(attachments)

    # Define tipo do payload (prioriza anexo)
    if anexos:
        # se houver mistura, usa o tipo do primeiro anexo válido
        tipo_payload = anexos[0]["tipo"]
    else:
        tipo_payload = "texto"

    payload = {
        "tipo": tipo_payload,                # 'texto' | 'imagem' | 'documento'
        "nome": nome,
        "aad_object_id": aad_object_id,
        "mensagem": texto,
        "anexos": anexos,                    # lista (vazia em modo texto)
    }

    print(
        f"[WEBHOOK] tipo={tipo_payload} nome={nome} "
        f"texto_len={len(texto)} anexos={len(anexos)}"
    )

    try:
        resp = requests.post(IA_WEBHOOK_URL, json=payload, timeout=180)
        dados_ia = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
        resposta_texto = (
            dados_ia.get("response")
            or dados_ia.get("text")
            or dados_ia.get("message")
            or resp.text
            or "Sem resposta da IA."
        )
    except Exception as e:
        print(f"[IA] Erro: {e}")
        resposta_texto = "Não consegui processar sua mensagem no momento."

    return jsonify({"type": "message", "text": resposta_texto, "textFormat": "markdown"}), 200


@app.route("/", methods=["GET"])
def health():
    return jsonify({"status": "online", "bot": "Deployd"}), 200


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)