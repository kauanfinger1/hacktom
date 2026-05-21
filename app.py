from flask import Flask, request, jsonify
import re
import os
import requests

app = Flask(__name__)

IA_WEBHOOK_URL = "https://main-production-8edf.up.railway.app/webhook-test/5733cc81-06cf-4a08-b68b-8ad3d3b134b3"

def extrair_texto(texto: str) -> str:
    texto = re.sub(r'<a[^>]*href="mailto:([^"]+)"[^>]*>.*?</a>', r'\1', texto)
    texto = re.sub(r"<at>[^<]+<\/at>", "", texto)
    texto = re.sub(r"<[^>]+>", "", texto)
    texto = texto.replace("&nbsp;", " ").strip()
    return texto

@app.route("/webhook", methods=["POST"])
def webhook():
    dados = request.json

    if not dados:
        return jsonify({"type": "message", "text": "Erro ao processar mensagem."}), 200

    texto         = extrair_texto(dados.get("text", ""))
    usuario       = dados.get("from", {})
    nome          = usuario.get("name", "Desconhecido")
    aad_object_id = usuario.get("aadObjectId", "")

    print(f"[WEBHOOK] nome={nome} aad_object_id={aad_object_id} texto={texto}")

    # Envia para a IA
    payload = {
        "nome": nome,
        "aad_object_id": aad_object_id,
        "mensagem": texto
    }

    try:
        resposta_ia = requests.post(IA_WEBHOOK_URL, json=payload, timeout=10)
        print(f"[IA] status={resposta_ia.status_code} resposta={resposta_ia.text}")
        resposta_texto = resposta_ia.json().get("text") or resposta_ia.json().get("message") or resposta_ia.text
    except Exception as e:
        print(f"[IA] Erro: {e}")
        resposta_texto = "Não consegui processar sua mensagem no momento."

    return jsonify({
        "type": "message",
        "text": resposta_texto
    })

@app.route("/", methods=["GET"])
def health():
    return jsonify({"status": "online", "bot": "Deployd"}), 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)