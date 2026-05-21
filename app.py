from flask import Flask, request, jsonify
import re
import os

app = Flask(__name__)

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

    texto = extrair_texto(dados.get("text", ""))
    usuario       = dados.get("from", {})
    nome          = usuario.get("name", "Desconhecido")
    aad_object_id = usuario.get("aadObjectId", "")

    print(f"[WEBHOOK] nome={nome} aad_object_id={aad_object_id} texto={texto}")

    return jsonify({
        "type": "message",
        "text": f"nome: {nome}\naad_object_id: {aad_object_id}\nmensagem: {texto}"
    })

@app.route("/", methods=["GET"])
def health():
    return jsonify({"status": "online", "bot": "Deployd"}), 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)