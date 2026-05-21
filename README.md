# Deployd Bot — Teams Outgoing Webhook

Bot Python para Microsoft Teams via Outgoing Webhook.

## Como usar

1. Instale as dependências:
```
pip install -r requirements.txt
```

2. Cole o token do Teams em `app.py` na variável `TEAMS_TOKEN`

3. Rode o servidor:
```
python app.py
```

## Endpoints

- `GET /` → health check
- `POST /webhook` → recebe mensagens do Teams
