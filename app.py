from flask import Flask, request, jsonify
import re
import os
import requests

app = Flask(__name__)

IA_WEBHOOK_URL = "https://primary-production-f46c1.up.railway.app/webhook/10ba380d-3a85-4fa9-a556-9673c294d40d"

MICROSOFT_APP_ID = os.environ.get("MICROSOFT_APP_ID", "")
MICROSOFT_APP_PASSWORD = os.environ.get("MICROSOFT_APP_PASSWORD", "")
MICROSOFT_TENANT_ID = os.environ.get("MICROSOFT_TENANT_ID", "botframework.com")


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


def obter_token_bot(tenant_id=None):

    if not MICROSOFT_APP_ID or not MICROSOFT_APP_PASSWORD:
        print("[TOKEN] MICROSOFT_APP_ID ou MICROSOFT_APP_PASSWORD não configurados")
        return None

    tenant = tenant_id or MICROSOFT_TENANT_ID

    try:
        resp = requests.post(
            f"https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token",
            data={
                "grant_type": "client_credentials",
                "client_id": MICROSOFT_APP_ID,
                "client_secret": MICROSOFT_APP_PASSWORD,
                "scope": "https://api.botframework.com/.default"
            },
            timeout=15
        )

        if resp.status_code == 200:
            token = resp.json().get("access_token")
            print(f"[TOKEN] token obtido com sucesso tenant={tenant}")
            return token

        print(f"[TOKEN] falha tenant={tenant} status={resp.status_code} body={resp.text}")

    except Exception as e:
        print(f"[TOKEN] erro: {e}")

    return None


def baixar_pdf_por_url(url, token):

    headers = {"Authorization": f"Bearer {token}"} if token else {}

    try:
        resp = requests.get(url, headers=headers, timeout=60)

        if resp.status_code == 200:
            return resp.content

        print(f"[PDF] falha download status={resp.status_code} url={url}")

    except Exception as e:
        print(f"[PDF] erro ao baixar: {e}")

    return None


def extrair_pdf_de_attachment(attachment, token=None):

    content_type = (attachment.get("contentType") or "").lower()
    nome_arquivo = attachment.get("name") or ""
    content_info = attachment.get("content") or {}

    if isinstance(content_info, str):
        content_info = {}

    if content_type == "application/vnd.microsoft.teams.file.download.info":
        url = content_info.get("downloadUrl") or attachment.get("contentUrl") or ""
        file_type = (content_info.get("fileType") or "").lower()
        eh_pdf = file_type == "pdf" or nome_arquivo.lower().endswith(".pdf")
    else:
        url = attachment.get("contentUrl") or ""
        eh_pdf = "pdf" in content_type or nome_arquivo.lower().endswith(".pdf")

    if not eh_pdf or not url:
        return None

    conteudo = baixar_pdf_por_url(url, token)

    if conteudo:
        print(f"[PDF] arquivo encontrado: {nome_arquivo}")
        return {
            "filename": nome_arquivo or "documento.pdf",
            "content": conteudo,
            "mime_type": "application/pdf"
        }

    return None


def extrair_pdf(dados, token=None):

    attachments = dados.get("attachments", [])

    print(f"[PDF] total de anexos: {len(attachments)}")

    for i, attachment in enumerate(attachments):
        content_type = (attachment.get("contentType") or "").lower()
        nome_arquivo = attachment.get("name") or ""
        print(f"[PDF] anexo[{i}] contentType={content_type} name={nome_arquivo}")

        pdf = extrair_pdf_de_attachment(attachment, token)
        if pdf:
            return pdf

    return None


def buscar_pdf_na_conversa(dados, token):

    service_url = (dados.get("serviceUrl") or "").rstrip("/")
    conversation_id = (dados.get("conversation") or {}).get("id", "")

    if not service_url or not conversation_id or not token:
        return None

    print(f"[CONV] buscando atividades em {service_url}")

    try:
        url = f"{service_url}/v3/conversations/{conversation_id}/activities"
        resp = requests.get(
            url,
            headers={"Authorization": f"Bearer {token}"},
            timeout=30
        )

        if resp.status_code != 200:
            print(f"[CONV] falha ao buscar atividades status={resp.status_code}")
            return None

        atividades = resp.json().get("activities", [])

        print(f"[CONV] total de atividades: {len(atividades)}")

        for atividade in reversed(atividades):
            for attachment in (atividade.get("attachments") or []):
                pdf = extrair_pdf_de_attachment(attachment, token)
                if pdf:
                    print(f"[CONV] PDF encontrado no histórico: {pdf['filename']}")
                    return pdf

    except Exception as e:
        print(f"[CONV] erro: {e}")

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

    print(
        f"[WEBHOOK] "
        f"nome={nome} "
        f"aad_object_id={aad_object_id} "
        f"texto={texto}"
    )

    tenant_id = (dados.get("channelData") or {}).get("tenant", {}).get("id", "")

    token = obter_token_bot(tenant_id) or obter_token_bot()

    pdf = extrair_pdf(dados, token)

    if not pdf and token:
        pdf = buscar_pdf_na_conversa(dados, token)

    payload = {
        "nome": nome,
        "aad_object_id": aad_object_id,
        "mensagem": texto
    }

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
