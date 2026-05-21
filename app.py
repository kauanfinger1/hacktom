from flask import Flask, request, jsonify
import re
import os

app = Flask(__name__)

# Dicionário em memória: aadObjectId -> email
usuarios_emails = {}

def extrair_texto(texto: str) -> str:
    """Remove tags HTML e extrai texto limpo incluindo emails linkados."""
    # Extrai e-mail de links mailto
    texto = re.sub(r'<a[^>]*href="mailto:([^"]+)"[^>]*>.*?</a>', r'\1', texto)
    # Remove menções @Bot
    texto = re.sub(r"<at>[^<]+<\/at>", "", texto)
    # Remove demais tags HTML
    texto = re.sub(r"<[^>]+>", "", texto)
    # Remove &nbsp; e espaços extras
    texto = texto.replace("&nbsp;", " ").strip()
    return texto

@app.route("/webhook", methods=["POST"])
def webhook():
    dados = request.json

    if not dados:
        return jsonify({"type": "message", "text": "Erro ao processar mensagem."}), 200

    texto_raw = dados.get("text", "")
    texto = extrair_texto(texto_raw)

    usuario       = dados.get("from", {})
    nome          = usuario.get("name", "Desconhecido")
    aad_object_id = usuario.get("aadObjectId", "")

    print(f"[WEBHOOK] texto_raw={texto_raw}")
    print(f"[WEBHOOK] texto_limpo={texto}")

    resposta = processar_mensagem(texto, nome, aad_object_id)

    return jsonify({
        "type": "message",
        "text": resposta
    })

def processar_mensagem(texto: str, nome: str, user_id: str) -> str:
    texto_lower = texto.lower()

    # Cadastro de e-mail
    if texto_lower.startswith("meu email:") or texto_lower.startswith("meu e-mail:"):
        email_informado = texto.split(":", 1)[1].strip()
        if "@" in email_informado:
            usuarios_emails[user_id] = email_informado
            return f"✅ E-mail **{email_informado}** cadastrado com sucesso, {nome}!"
        else:
            return "❌ E-mail inválido. Tente: `meu email: seuemail@empresa.com`"

    if "oi" in texto_lower or "olá" in texto_lower or "hello" in texto_lower:
        return f"Olá, {nome}! Eu sou o bot Deployd. Como posso ajudar?"

    if "meu email" in texto_lower or "meu e-mail" in texto_lower:
        email = usuarios_emails.get(user_id)
        if email:
            return f"Seu e-mail cadastrado é: **{email}**"
        else:
            return (
                f"Ainda não tenho seu e-mail cadastrado, {nome}.\n"
                "Para cadastrar, envie:\n"
                "`meu email: seuemail@empresa.com`"
            )

    if "status" in texto_lower:
        return "✅ Todos os sistemas operando normalmente."

    if "ajuda" in texto_lower or "help" in texto_lower:
        return (
            "Comandos disponíveis:\n"
            "- **oi** → cumprimento\n"
            "- **meu email** → exibe seu e-mail cadastrado\n"
            "- **meu email: x@y.com** → cadastra seu e-mail\n"
            "- **status** → verifica o status do sistema\n"
            "- **ajuda** → exibe essa mensagem"
        )

    return f"Recebi: '{texto}'. Em que posso ajudar?"

@app.route("/", methods=["GET"])
def health():
    return jsonify({"status": "online", "bot": "Deployd"}), 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)