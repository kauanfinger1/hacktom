from flask import Flask, request, jsonify
import re
import os
import requests
import threading
import json

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

    try:
        resp = requests.get(url, timeout=60)

        if resp.status_code == 200:
            return resp.content

        if resp.status_code in (401, 403) and token:
            resp = requests.get(
                url,
                headers={"Authorization": f"Bearer {token}"},
                timeout=60
            )
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


def obter_token_graph(tenant_id):

    if not MICROSOFT_APP_ID or not MICROSOFT_APP_PASSWORD or not tenant_id:
        return None

    try:
        resp = requests.post(
            f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token",
            data={
                "grant_type": "client_credentials",
                "client_id": MICROSOFT_APP_ID,
                "client_secret": MICROSOFT_APP_PASSWORD,
                "scope": "https://graph.microsoft.com/.default"
            },
            timeout=15
        )

        if resp.status_code == 200:
            token = resp.json().get("access_token")
            print(f"[GRAPH] token obtido tenant={tenant_id}")
            return token

        print(f"[GRAPH] falha token status={resp.status_code} body={resp.text}")

    except Exception as e:
        print(f"[GRAPH] erro token: {e}")

    return None


def buscar_pdf_no_canal(dados, graph_token):

    channel_data = dados.get("channelData") or {}
    team_id = channel_data.get("teamsTeamId", "")
    channel_id = channel_data.get("teamsChannelId", "")

    if not team_id or not channel_id or not graph_token:
        return None

    headers = {"Authorization": f"Bearer {graph_token}"}

    print(f"[GRAPH] buscando mensagens do canal team={team_id[:20]}...")

    try:
        url = f"https://graph.microsoft.com/v1.0/teams/{team_id}/channels/{channel_id}/messages"
        resp = requests.get(url, headers=headers, params={"$top": 20}, timeout=30)

        if resp.status_code != 200:
            print(f"[GRAPH] falha ao buscar mensagens status={resp.status_code} body={resp.text}")
            return None

        mensagens = resp.json().get("value", [])
        print(f"[GRAPH] total de mensagens: {len(mensagens)}")

        for mensagem in mensagens:
            for attachment in (mensagem.get("attachments") or []):
                content_type = (attachment.get("contentType") or "").lower()
                nome_arquivo = attachment.get("name") or ""
                url_arquivo = attachment.get("contentUrl") or ""

                eh_pdf = nome_arquivo.lower().endswith(".pdf") or "pdf" in content_type

                print(f"[GRAPH] attachment contentType={content_type} name={nome_arquivo} eh_pdf={eh_pdf}")

                if not eh_pdf or not url_arquivo:
                    continue

                conteudo = baixar_pdf_por_url(url_arquivo, graph_token)
                if conteudo:
                    print(f"[GRAPH] PDF encontrado: {nome_arquivo}")
                    return {
                        "filename": nome_arquivo or "documento.pdf",
                        "content": conteudo,
                        "mime_type": "application/pdf"
                    }

    except Exception as e:
        print(f"[GRAPH] erro: {e}")

    return None


def enviar_resposta_proativa(service_url, conversation_id, texto, tenant_id):

    token = obter_token_bot(tenant_id) or obter_token_bot()

    if not token:
        print("[PROATIVO] sem token para enviar resposta")
        return

    url = f"{service_url.rstrip('/')}/v3/conversations/{conversation_id}/activities"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    body = {
        "type": "message",
        "text": texto,
        "textFormat": "markdown"
    }

    try:
        resp = requests.post(url, json=body, headers=headers, timeout=30)
        print(f"[PROATIVO] status={resp.status_code}")
    except Exception as e:
        print(f"[PROATIVO] erro: {e}")


def processar_em_background(dados, service_url, conversation_id, tenant_id):

    try:
        texto = extrair_texto(dados.get("text", ""))
        usuario = dados.get("from", {})
        nome = usuario.get("name", "Desconhecido")
        aad_object_id = usuario.get("aadObjectId", "")

        token_bot = obter_token_bot(tenant_id) or obter_token_bot()

        pdf = extrair_pdf(dados, token_bot)

        if not pdf:
            graph_token = obter_token_graph(MICROSOFT_TENANT_ID)
            if graph_token:
                pdf = buscar_pdf_no_canal(dados, graph_token)

        payload = {
            "nome": nome,
            "aad_object_id": aad_object_id,
            "mensagem": texto
        }

        if pdf:
            resposta_ia = requests.post(
                IA_WEBHOOK_URL,
                data=payload,
                files={"data": (pdf["filename"], pdf["content"], pdf["mime_type"])},
                timeout=120
            )
        else:
            resposta_ia = requests.post(
                IA_WEBHOOK_URL,
                json=payload,
                timeout=120
            )

        try:
            dados_ia = resposta_ia.json()
        except Exception:
            dados_ia = {"message": resposta_ia.text}

        print(f"[IA] status={resposta_ia.status_code} dados={dados_ia}")

        resposta_texto = (
            dados_ia.get("response")
            or dados_ia.get("text")
            or dados_ia.get("message")
            or "Sem resposta da IA."
        )

    except Exception as e:
        print(f"[BG] erro: {e}")
        resposta_texto = "Não consegui processar sua mensagem no momento."

    enviar_resposta_proativa(service_url, conversation_id, resposta_texto, tenant_id)


@app.route("/webhook", methods=["POST"])
def webhook():

    dados = request.json

    if not dados:
        return "", 200

    campos_relevantes = {
        "type": dados.get("type"),
        "text": dados.get("text"),
        "attachments": dados.get("attachments"),
        "channelData": dados.get("channelData"),
        "value": dados.get("value"),
        "entities": dados.get("entities"),
    }
    print(f"[PAYLOAD] {json.dumps(campos_relevantes, ensure_ascii=False)}")

    usuario = dados.get("from", {})
    nome = usuario.get("name", "Desconhecido")
    aad_object_id = usuario.get("aadObjectId", "")
    texto = extrair_texto(dados.get("text", ""))
    tenant_id = (dados.get("channelData") or {}).get("tenant", {}).get("id", "")
    service_url = dados.get("serviceUrl", "")
    conversation_id = (dados.get("conversation") or {}).get("id", "")

    print(
        f"[WEBHOOK] nome={nome} aad_object_id={aad_object_id} texto={texto}"
    )

    thread = threading.Thread(
        target=processar_em_background,
        args=(dados, service_url, conversation_id, tenant_id),
        daemon=True
    )
    thread.start()

    return "", 200


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
