from flask import Flask, request, jsonify
import re
import os

app = Flask(__name__)

@app.route("/webhook", methods=["POST"])
def webhook():
    dados = request.json

    if not dados:
        return jsonify({"type": "message", "text": "Erro ao processar mensagem."}), 200

    texto = dados.get("text", "")
    texto = re.sub(r"<at>[^<]+<\/at>", "", texto).strip()

    # dados do usuário
    usuario = dados.get("from", {})
    nome = usuario.get("name", "Desconhecido")
    email = usuario.get("email", None)
    user_id = usuario.get("id", None)

    resposta = processar_mensagem(texto, nome, email)

    return jsonify({
        "type": "message",
        "text": resposta
    })

def processar_mensagem(texto: str, nome: str, email: str) -> str:
    texto_lower = texto.lower()

    if "oi" in texto_lower or "olá" in texto_lower or "hello" in texto_lower:
        return "Olá! {nome} Eu sou o bot Deployd. Como posso ajudar?"

    if "status" in texto_lower:
        return "✅ Todos os sistemas operando normalmente."

    if "meu email" in texto_lower or "meu e-mail" in texto_lower:
    if email:
        return f"Seu e-mail é: {email}"
    else:
        return f"Não consegui obter seu e-mail, {nome}. O Teams não enviou essa informação."

    if "ajuda" in texto_lower or "help" in texto_lower:
        return (
            "Comandos disponíveis:\n"
            "- **status** → verifica o status do sistema\n"
            "- **meu email** → exibe seu e-mail\n"
            "- **ajuda** → exibe essa mensagem\n"
            "- **oi** → cumprimento"
        )

    return f"Recebi: '{texto}'. Em que posso ajudar?"

@app.route("/", methods=["GET"])
def health():
    return jsonify({"status": "online", "bot": "Deployd"}), 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)