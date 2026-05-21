from flask import Flask, request, jsonify
import hmac
import hashlib
import base64

app = Flask(__name__)

# Cole aqui o token que o Teams vai gerar após criar o webhook
TEAMS_TOKEN = "BeFK408U28ZZ53aXQKKIoq3zEv7GH+k1BsAb5tPVqdU="

def verificar_assinatura(body: bytes, assinatura: str) -> bool:
    try:
        token_bytes = base64.b64decode(TEAMS_TOKEN)
        mac = hmac.new(token_bytes, msg=body, digestmod=hashlib.sha256)
        assinatura_gerada = base64.b64encode(mac.digest()).decode()
        assinatura_recebida = assinatura.replace("HMAC ", "")
        return hmac.compare_digest(assinatura_gerada, assinatura_recebida)
    except Exception:
        return False

@app.route("/webhook", methods=["POST"])
def webhook():
    # Verifica assinatura do Teams
    assinatura = request.headers.get("Authorization", "")
    if not verificar_assinatura(request.data, assinatura):
        return jsonify({"error": "Token inválido"}), 401

    dados = request.json
    texto = dados.get("text", "")

    # Remove a menção @NomeDoBot do texto
    import re
    texto = re.sub(r"<at>[^<]+<\/at>", "", texto).strip()

    # -----------------------------------------------
    # SUA LÓGICA AQUI
    resposta = processar_mensagem(texto)
    # -----------------------------------------------

    return jsonify({
        "type": "message",
        "text": resposta
    })

def processar_mensagem(texto: str) -> str:
    texto = texto.lower()

    if "oi" in texto or "olá" in texto or "hello" in texto:
        return "Olá! Eu sou o bot Deployd. Como posso ajudar?"

    if "status" in texto:
        return "✅ Todos os sistemas operando normalmente."

    if "ajuda" in texto or "help" in texto:
        return (
            "Comandos disponíveis:\n"
            "- **status** → verifica o status do sistema\n"
            "- **ajuda** → exibe essa mensagem\n"
            "- **oi** → cumprimento"
        )

    return f"Recebi sua mensagem: '{texto}'. Em que posso ajudar?"

@app.route("/", methods=["GET"])
def health():
    return jsonify({"status": "online", "bot": "Deployd"}), 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
