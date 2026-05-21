from flask import Flask, request, jsonify
import re
import os
import requests

app = Flask(__name__)

CLIENT_ID     = os.environ.get("AZURE_CLIENT_ID")
CLIENT_SECRET = os.environ.get("AZURE_CLIENT_SECRET")

def get_access_token(tenant_id: str):
    """Obtém token para o tenant específico do usuário."""
    url = f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"
    data = {
        "grant_type":    "client_credentials",
        "client_id":     CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "scope":         "https://graph.microsoft.com/.default"
    }
    response = requests.post(url, data=data)
    result = response.json()
    print(f"[TOKEN] status={response.status_code} erro={result.get('error')}")
    return result.get("access_token")

def get_user_email(aad_object_id: str, tenant_id: str) -> str:
    """Busca e-mail pelo aadObjectId no tenant correto."""
    try:
        token = get_access_token(tenant_id)
        if not token:
            return None

        headers = {"Authorization": f"Bearer {token}"}
        url = f"https://graph.microsoft.com/v1.0/users/{aad_object_id}?$select=mail,userPrincipalName,displayName"
        response = requests.get(url, headers=headers)
        data = response.json()
        print(f"[EMAIL] status={response.status_code} data={data}")
        return data.get("mail") or data.get("userPrincipalName")
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
    # Remove tags HTML
    texto = re.sub(r"<[^>]+>", "", texto).strip()

    usuario       = dados.get("from", {})
    nome          = usuario.get("name", "Desconhecido")
    aad_object_id = usuario.get("aadObjectId")
    tenant_id     = dados.get("conversation", {}).get("tenantId") or \
                    dados.get("channelData", {}).get("tenant", {}).get("id")

    print(f"[WEBHOOK] nome={nome} aadObjectId={aad_object_id} tenantId={tenant_id}")

    email = get_user_email(aad_object_id, tenant_id) if aad_object_id and tenant_id else None

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