from flask import Flask, request, jsonify
import re
import os
import requests

app = Flask(__name__)

IA_WEBHOOK_URL = "https://primary-production-f46c1.up.railway.app/webhook/10ba380d-3a85-4fa9-a556-9673c294d40d"


def extrair_texto(texto: str) -> str:

    texto = re.sub(
        r'<a[^>]*href="mailto:([^"]+)"[^>]*>.*?</a>',
        r'\1',
        texto
    )

    texto = re.sub(r"<at>[^<]+<\/at>", "", texto)
    texto = re.sub(r"<[^>]+>", "", texto)

    texto = texto.replace("&nbsp;", " ").strip()

    return texto


def extrair_pdf(dados):

    attachments = dados.get("attachments", [])

    print(f"[PDF] total de anexos: {len(attachments)}")

    for i, attachment in enumerate(attachments):

        content_type = (attachment.get("contentType") or "").lower()
        nome_arquivo = attachment.get("name") or ""
        content_info = attachment.get("content") or {}

        print(f"[PDF] anexo[{i}] contentType={content_type} name={nome_arquivo} content={content_info}")

        # Teams envia arquivos com contentType especial; URL fica em content.downloadUrl
        if content_type == "application/vnd.microsoft.teams.file.download.info":
            url = content_info.get("downloadUrl") or attachment.get("contentUrl") or ""
            file_type = (content_info.get("fileType") or "").lower()
            eh_pdf = file_type == "pdf" or nome_arquivo.lower().endswith(".pdf")
        else:
            url = attachment.get("contentUrl") or ""
            eh_pdf = (
                "pdf" in content_type
                or nome_arquivo.lower().endswith(".pdf")
            )

        print(f"[PDF] anexo[{i}] url={url} eh_pdf={eh_pdf}")

        if not eh_pdf:
            continue

        if not url:
            print("[PDF] URL não encontrada no anexo")
            continue

        try:

            resposta = requests.get(url, timeout=60)

            if resposta.status_code in (401, 403):

                bot_token = dados.get("channelData", {}).get("token", "")

                headers = {}
                if bot_token:
                    headers["Authorization"] = f"Bearer {bot_token}"

                resposta = requests.get(url, headers=headers, timeout=60)

            if resposta.status_code == 200:

                print(f"[PDF] arquivo encontrado: {nome_arquivo}")

                return {
                    "filename": nome_arquivo,
                    "content": resposta.content,
                    "mime_type": "application/pdf"
                }

            print(f"[PDF] falha download status={resposta.status_code} url={url}")

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

    print(f"[DEBUG] attachments={dados.get('attachments', [])}")
    print(f"[DEBUG] channelData={dados.get('channelData', {})}")
    print(f"[DEBUG] entities={dados.get('entities', [])}")

    texto = extrair_texto(dados.get("text", ""))

    usuario = dados.get("from", {})

    nome = usuario.get("name", "Desconhecido")
    aad_object_id = usuario.get("aadObjectId", "")

    print(
        f"[WEBHOOK] "
        f"nome={nome} "
        f"aad_object_id={aad_object_id} "
        f"texto={texto}"
    )

    payload = {
        "nome": nome,
        "aad_object_id": aad_object_id,
        "mensagem": texto
    }

    pdf = extrair_pdf(dados)

    try:

        if pdf:
            resposta_ia = requests.post(
                IA_WEBHOOK_URL,
                data=payload,
                files={"data": (pdf["filename"], pdf["content"], pdf["mime_type"])},
                timeout=60
            )
        else:
            resposta_ia = requests.post(
                IA_WEBHOOK_URL,
                json=payload,
                timeout=60
            )

        try:
            dados_ia = resposta_ia.json()
        except Exception:
            dados_ia = {
                "message": resposta_ia.text
            }

        print(
            f"[IA] "
            f"status={resposta_ia.status_code} "
            f"dados={dados_ia}"
        )

        resposta_texto = (
            dados_ia.get("response")
            or dados_ia.get("text")
            or dados_ia.get("message")
            or "Sem resposta da IA."
        )

    except Exception as e:

        print(f"[IA] erro={e}")

        resposta_texto = (
            "Não consegui processar sua mensagem no momento."
        )

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

    app.run(
        host="0.0.0.0",
        port=port,
        debug=False
    )
