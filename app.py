from flask import Flask, request, jsonify
import re
import os
import requests
import threading

app = Flask(__name__)

IA_WEBHOOK_URL = "https://main-production-8edf.up.railway.app/webhook/5733cc81-06cf-4a08-b68b-8ad3d3b134b3"

def extrair_texto(texto: str) -> str:
    texto = re.sub(r'<a[^>]*href="mailto:([^"]+)"[^>]*>.*?</a>', r'\1', texto)
    texto = re.sub(r"<at>[^<]+<\/at>", "", texto)
    texto = re.sub(r"<[^>]+>", "", texto)
    texto = texto.replace("&nbsp;", " ").strip()
    return texto

def chamar_ia_e_responder(payload, service_url, conversation_id):
    """Chama a IA em background e envia resposta ao Teams."""
    try:
        resposta_ia = requests.post(IA_WEBHOOK_URL, json=payload, timeout=30)
        dados_ia = resposta_ia.json()
        print(f"[IA] status={resposta_ia.status_code} dados={dados_ia}")
        resposta_texto = dados_ia.get("response") or dados_ia.get("text") or dados_ia.get("message", "Sem resposta da IA.")
    except Exception as e:
        print(f"[IA] Erro: {e}")
        resposta_texto = "Não consegui processar sua mensagem no momento."

    # Envia resposta ao Teams via serviceUrl
    try:
        url = f"{service_url}v3/conversations/{conversation_id}/activities"
        r = requests.post(url, json={"type": "message", "text": resposta_texto}, timeout=10)
        print(f"[TEAMS] status={r.status_code}")
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

    print(f"[WEBHOOK] nome={nome} aad_object_id={aad_object_id} texto={texto}")

    payload = {
        "nome": nome,
        "aad_object_id": aad_object_id,
        "mensagem": texto
    }

    # Processa em background para não estourar o timeout do Teams
    thread = threading.Thread(target=chamar_ia_e_responder, args=(payload, service_url, conversation_id))
    thread.start()

    # Responde imediatamente ao Teams
    return jsonify({"type": "message", "text": "⏳ Processando..."}), 200

@app.route("/", methods=["GET"])
def health():
    return jsonify({"status": "online", "bot": "Deployd"}), 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)