from flask import Flask, request, jsonify
import re
import os
import requests

app = Flask(__name__)

IA_WEBHOOK_URL = "https://primary-production-f46c1.up.railway.app/webhook/10ba380d-3a85-4fa9-a556-9673c294d40d"

def extrair_texto(texto: str) -> str:
    texto = re.sub(r'<a[^>]*href="mailto:([^"]+)"[^>]*>.*?</a>', r'\1', texto)
    texto = re.sub(r"<at>[^<]+<\/at>", "", texto)
    texto = re.sub(r"<[^>]+>", "", texto)
    texto = texto.replace("&nbsp;", " ").strip()
    return texto


def extrair_pdf(dados):
    attachments = dados.get("attachments", [])

    for attachment in attachments:
        content_type = attachment.get("contentType", "").lower()
        nome_arquivo = attachment.get("name", "")
        url = attachment.get("contentUrl")

        if (
            "pdf" in content_type
            or nome_arquivo.lower().endswith(".pdf")
        ):
            try:
                headers = {}

                auth = request.headers.get("Authorization")
                if auth:
                    headers["Authorization"] = auth

                resposta = requests.get(
                    url,
                    headers=headers,
                    timeout=60
                )

                if resposta.status_code == 200:
                    return {
                        "filename": nome_arquivo,
                        "content": resposta.content,
                        "mime_type": "application/pdf"
                    }

            except Exception as e:
                print(f"[PDF] erro ao baixar pdf: {e}")

    return None


@app.route("/webhook", methods=["POST"])
def webhook():

    dados = request.json

    if not dados:
        return jsonify({
            "type": "message",
            "text": "Erro ao processar mensagem."
        }), 200

    texto = extrair_texto(dados.get("text", ""))

    usuario = dados.get("from", {})
    nome = usuario.get("name", "Desconhecido")
    aad_object_id = usuario.get("aadObjectId", "")

    print(f"[WEBHOOK] nome={nome} aad_object_id={aad_object_id} texto={texto}")

    payload = {
        "nome": nome,
        "aad_object_id": aad_object_id,
        "mensagem": texto
    }

    pdf_data = extrair_pdf(dados)

    try:

        # COM PDF
        if pdf_data:

            files = {
                "data": (
                    pdf_data["filename"],
                    pdf_data["content"],
                    pdf_data["mime_type"]
                )
            }

            resposta_ia = requests.post(
                IA_WEBHOOK_URL,
                data=payload,
                files=files,
                timeout=120
            )

        # SEM PDF
        else:

            resposta_ia = requests.post(
                IA_WEBHOOK_URL,
                json=payload,
                timeout=120
            )

        try:
            dados_ia = resposta_ia.json()
        except Exception:
            dados_ia = {
                "message": resposta_ia.text
            }

        print(f"[IA] status={resposta_ia.status_code} dados={dados_ia}")

        resposta_texto = (
            dados_ia.get("response")
            or dados_ia.get("text")
            or dados_ia.get("message")
            or "Sem resposta da IA."
        )

    except Exception as e:
        print(f"[IA] Erro: {e}")
        resposta_texto = "Não consegui processar sua mensagem no momento."

    return jsonify({
        "type": "message",
        "text": resposta_texto,
        "textFormat": "markdown"
    }), 200


@app.route("/", methods=["GET"])
def health():
    return jsonify({
        "status": "online",
        "bot": "Deployd"
    }), 200


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)