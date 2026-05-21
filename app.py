from flask import Flask, request, jsonify
import re
import os
import requests
import threading

app = Flask(__name__)

IA_WEBHOOK_URL = "https://main-production-8edf.up.railway.app/webhook/5733cc81-06cf-4a08-b68b-8ad3d3b134b3"
CLIENT_ID      = os.environ.get("AZURE_CLIENT_ID")
CLIENT_SECRET  = os.environ.get("AZURE_CLIENT_SECRET")
TENANT_ID      = os.environ.get("AZURE_TENANT_ID", "botframework.com")

def get_teams_token():
    """Obtém token para chamar a API do Teams."""
    url = f"https://login.microsoftonline.com/{TENANT_ID}/oauth2/v2.0/token"
    data = {
        "grant_type":    "client_credentials",
        "client_id":     CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "scope":         "https://api.botframework.com/.default"
    }
    response = requests.post(url, data=data)
    body = response.json()
    token = body.get("access_token")
    if not token:
        print(f"[TOKEN] status={response.status_code} erro={body}")
    else:
        print(f"[TOKEN] status={response.status_code} obtido=sim")
    return token

def extrair_texto(texto: str) -> str:
    texto = re.sub(r'<a[^>]*href="mailto:([^"]+)"[^>]*>.*?</a>', r'\1', texto)
    texto = re.sub(r"<at>[^<]+<\/at>", "", texto)
    texto = re.sub(r"<[^>]+>", "", texto)
    texto = texto.replace("&nbsp;", " ").strip()
    return texto

def chamar_ia_e_responder(payload, service_url, conversation_id, activity_id, bot, user, channel_data):
    try:
        resposta_ia = requests.post(IA_WEBHOOK_URL, json=payload, timeout=30)
        dados_ia = resposta_ia.json()
        print(f"[IA] status={resposta_ia.status_code} dados={dados_ia}")
        resposta_texto = dados_ia.get("response") or dados_ia.get("text") or dados_ia.get("message", "Sem resposta da IA.")
    except Exception as e:
        print(f"[IA] Erro: {e}")
        resposta_texto = "Não consegui processar sua mensagem no momento."

    try:
        token = get_teams_token()
        url = f"{service_url.rstrip('/')}/v3/conversations/{conversation_id}/activities"
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        body = {
            "type": "message",
            "from": bot,
            "recipient": user,
            "conversation": {"id": conversation_id},
            "replyToId": activity_id,
            "text": resposta_texto,
            "textFormat": "markdown",
            "channelData": channel_data
        }
        r = requests.post(url, json=body, headers=headers, timeout=10)
        print(f"[TEAMS] status={r.status_code} resposta={r.text}")
    except Exception as e:
        print(f"[TEAMS] Erro ao enviar resposta: {e}")

@app.route("/webhook", methods=["POST"])
def webhook():
    dados = request.json

    if not dados:
        return jsonify({"type": "message", "text": "Erro ao processar mensagem."}), 200

    texto           = extrair_texto(dados.get("text", ""))
    usuario         = dados.get("from", {})
    nome            = usuario.get("name", "Desconhecido")
    aad_object_id   = usuario.get("aadObjectId", "")
    service_url     = dados.get("serviceUrl", "")
    conversation_id = dados.get("conversation", {}).get("id", "")
    activity_id     = dados.get("id", "")
    bot             = dados.get("recipient", {})
    user            = dados.get("from", {})
    channel_data    = dados.get("channelData", {})

    print(f"[WEBHOOK] nome={nome} aad_object_id={aad_object_id} texto={texto}")

    payload = {
        "nome": nome,
        "aad_object_id": aad_object_id,
        "mensagem": texto
    }

    thread = threading.Thread(
        target=chamar_ia_e_responder,
        args=(payload, service_url, conversation_id, activity_id, bot, user, channel_data)
    )
    thread.start()

    return jsonify({"status": "ok"}), 200

@app.route("/", methods=["GET"])
def health():
    return jsonify({"status": "online", "bot": "Deployd"}), 200

print(f"[STARTUP] CLIENT_ID={CLIENT_ID} TENANT_ID={TENANT_ID} SECRET={'***' if CLIENT_SECRET else 'NAO_DEFINIDO'}")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)