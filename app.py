from flask import Flask, request, jsonify
import re

app = Flask(__name__)

@app.route("/webhook", methods=["POST"])
def webhook():
    dados = request.json

    if not dados:
        return jsonify({"type": "message", "text": "Erro ao processar mensagem."}), 200

    texto = dados.get("text", "")

    # Remove a menção @NomeDoBot do texto
    texto = re.sub(r"<at>[^<]+<\/at>", "", texto).strip()

    resposta = processar_mensagem(texto)

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

    return f"Recebi: '{texto}'. Em que posso ajudar?"

@app.route("/", methods=["GET"])
def health():
    return jsonify({"status": "online", "bot": "Deployd"}), 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)