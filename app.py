from flask import Flask, request, jsonify
import re
import os
import requests

app = Flask(__name__)

TENANT_ID     = os.environ.get("AZURE_TENANT_ID")
CLIENT_ID     = os.environ.get("AZURE_CLIENT_ID")
CLIENT_SECRET = os.environ.get("AZURE_CLIENT_SECRET")

def get_access_token():
    url = f"https://login.microsoftonline.com/{TENANT_ID}/oauth2/v2.0/token"
    data = {
        "grant_type":    "client_credentials",
        "client_id":     CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "scope":         "https://graph.microsoft.com/.default"
    }
    response = requests.post(url, data=data)
    return response.json().get("access_token")

def get_user_email_by_name(nome: str) -> str:
    """Busca o e-mail do usuário pelo nome via Graph API."""
    try:
        token = get_access_token()
        if not token:
            print("[EMAIL] Token não obtido!")
            return None

        headers = {"Authorization": f"Bearer {token}"}

        # Busca pelo nome do usuário
        url = f"https://graph.microsoft.com/v1.0/users?$filter=displayName eq '{nome}'&$select=mail,userPrincipalName,displayName"
        response = requests.get(url, headers=headers)
        data = response.json()
        print(f"[EMAIL] status={response.status_code} resposta={data}")

        usuarios = data.get("value", [])
        if usuarios:
            user = usuarios[0]
            return user.get("mail") or user.get("userPrincipalName")

        return None
    except Exception as e:
        print(f"[EMAIL] Exceção: {e}")
        return None

@app.route("/webhook", methods=["POST"])
def webhook():
    dados = request.json

    if not dados:
        return jsonify({"type": "message", "text": "Erro ao processar mensagem."}), 200

    texto = dados.get("text", "")
    texto = re.sub(r"<at>[^<]+<\/at>", "", texto).strip()

    usuario  = dados.get("from", {})
    nome     = usuario.get("name", "Desconhecido")

    print(f"[WEBHOOK] nome={nome}")

    email = get_user_email_by_name(nome)

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