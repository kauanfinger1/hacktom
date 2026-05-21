from flask import Flask, request, jsonify
import re
import os
import requests

app = Flask(__name__)

# Variáveis de ambiente do Railway
TENANT_ID     = os.environ.get("AZURE_TENANT_ID")
CLIENT_ID     = os.environ.get("AZURE_CLIENT_ID")
CLIENT_SECRET = os.environ.get("AZURE_CLIENT_SECRET")

def get_access_token():
    """Obtém token de acesso do Microsoft Graph API."""
    url = f"https://login.microsoftonline.com/{TENANT_ID}/oauth2/v2.0/token"
    data = {
        "grant_type":    "client_credentials",
        "client_id":     CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "scope":         "https://graph.microsoft.com/.default"
    }
    response = requests.post(url, data=data)
    return response.json().get("access_token")

def get_user_email(user_id: str) -> str:
    """Busca o e-mail do usuário pelo ID via Graph API."""
    try:
        token = get_access_token()
        headers = {"Authorization": f"Bearer {token}"}
        url = f"https://graph.microsoft.com/v1.0/users/{user_id}"
        response = requests.get(url, headers=headers)
        data = response.json()
        return data.get("mail") or data.get("userPrincipalName", None)
    except Exception as e:
        print(f"Erro ao buscar email: {e}")
        return None

@app.route("/webhook", methods=["POST"])
def webhook():
    dados = request.json

    if not dados:
        return jsonify({"type": "message", "text": "Erro ao processar mensagem."}), 200

    texto = dados.get("text", "")
    texto = re.sub(r"<at>[^<]+<\/at>", "", texto).strip()

    # Dados do usuário
    usuario  = dados.get("from", {})
    nome     = usuario.get("name", "Desconhecido")
    user_id  = usuario.get("id", None)

    # Busca e-mail via Graph API
    email = get_user_email(user_id) if user_id else None

    resposta = processar_mensagem(texto, nome, email)

    return jsonify({
        "type": "message",
        "text": resposta
    })

def processar_mensagem(texto: str, nome: str, email: str) -> str:
    texto_lower = texto.lower()

    if "oi" in texto_lower or "olá" in texto_lower or "hello" in texto_lower:
        return f"Olá, {nome}! Eu sou o bot Deployd. Como posso ajudar?"

    if "meu email" in texto_lower or "meu e-mail" in texto_lower:
        if email:
            return f"Seu e-mail é: **{email}**"
        else:
            return f"Não consegui obter seu e-mail, {nome}."

    if "status" in texto_lower:
        return "✅ Todos os sistemas operando normalmente."

    if "ajuda" in texto_lower or "help" in texto_lower:
        return (
            "Comandos disponíveis:\n"
            "- **oi** → cumprimento\n"
            "- **meu email** → exibe seu e-mail\n"
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