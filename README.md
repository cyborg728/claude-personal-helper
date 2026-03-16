# Claude Personal Helper — Telegram Bot

Personal Telegram assistant bot with AI-powered translation via Google Gemini.

## Features

- **Translator** — automatic translation of business messages (text & voice) using Google Gemini
- **Whitelist** — admin-managed access control
- **Localization** — Russian, English, Korean (fluent-runtime)
- **Webhook mode** — Litestar + uvicorn

## Tech Stack

| Component | Library |
|-----------|---------|
| Telegram | python-telegram-bot 22+ |
| Database ORM | SQLModel + SQLAlchemy (async) |
| Database | PostgreSQL (asyncpg) |
| Web server | Litestar + uvicorn |
| AI / Translation | Google Gemini (google-genai) |
| Settings | pydantic-settings |
| Localization | fluent-runtime |

## Project Structure

```
app/
├── config.py              # Pydantic settings
├── main.py                # Entry point
├── webhook.py             # Litestar webhook server
├── models/
│   ├── database.py        # Async engine & session
│   └── user.py            # SQLModel tables
├── handlers/
│   ├── common.py          # /start, /help
│   ├── admin.py           # /admin — whitelist management
│   └── translator.py      # /translator — translate settings + business messages
├── services/
│   ├── access.py          # Permission checks
│   ├── gemini.py          # Gemini API client
│   └── i18n.py            # Fluent localization
└── locales/
    ├── en/main.ftl
    ├── ru/main.ftl
    └── ko/main.ftl
```

---

## Deployment to Kubernetes (k3s)

### 1. Create imagePullSecret for private GitHub Container Registry

Generate a GitHub Personal Access Token (PAT) with `read:packages` scope, then create the secret:

```bash
kubectl create namespace tg-assistant

kubectl create secret docker-registry ghcr-secret \
  --namespace=tg-assistant \
  --docker-server=ghcr.io \
  --docker-username=YOUR_GITHUB_USERNAME \
  --docker-password=YOUR_GITHUB_PAT \
  --docker-email=YOUR_EMAIL
```

Alternatively, encode and apply manually:

```bash
# Generate the .dockerconfigjson
echo -n '{"auths":{"ghcr.io":{"username":"YOUR_GITHUB_USERNAME","password":"YOUR_GITHUB_PAT","auth":"'$(echo -n "YOUR_GITHUB_USERNAME:YOUR_GITHUB_PAT" | base64)'"}}}' | base64

# Create secret YAML
cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: Secret
metadata:
  name: ghcr-secret
  namespace: tg-assistant
type: kubernetes.io/dockerconfigjson
data:
  .dockerconfigjson: <BASE64_ENCODED_STRING_FROM_ABOVE>
EOF
```

### 2. Configure the bot secret

Edit `k8s/secret.yml` and fill in your actual values:

- `BOT_BOT_TOKEN` — Telegram Bot API token from @BotFather
- `BOT_ADMIN_USERNAME` — your Telegram username (without @)
- `BOT_DATABASE_URL` — PostgreSQL connection string
- `BOT_GEMINI_API_KEY` — Google Gemini API key
- `BOT_GEMINI_MODEL` — Gemini model name (e.g. `gemini-2.0-flash`)
- `BOT_WEBHOOK_SECRET` — random string for webhook verification

### 3. Deploy to k3s

```bash
# Apply all manifests
kubectl apply -f k8s/namespace.yml
kubectl apply -f k8s/secret.yml
kubectl apply -f k8s/postgres.yml
kubectl apply -f k8s/deployment.yml
kubectl apply -f k8s/ingress.yml

# Verify pods are running
kubectl get pods -n tg-assistant

# Check logs
kubectl logs -n tg-assistant -l app=tg-assistant -f
```

### 4. DNS & TLS

Make sure `tg-assistant.f-f.dev` points to your k3s cluster's external IP.

The Ingress manifest expects cert-manager with a `letsencrypt-prod` ClusterIssuer. If you use a different TLS setup, update `k8s/ingress.yml` accordingly.

### 5. Update the bot

After pushing to `main`, GitHub Actions will build and push a new image to `ghcr.io`. Restart the deployment to pick it up:

```bash
kubectl rollout restart deployment/tg-assistant -n tg-assistant
```

---

## Local Development

```bash
# Set environment variables (or use a .env file)
export BOT_BOT_TOKEN="..."
export BOT_ADMIN_USERNAME="..."
export BOT_DATABASE_URL="postgresql+asyncpg://postgres:password@localhost:5432/tg_assistant"
export BOT_GEMINI_API_KEY="..."
export BOT_GEMINI_MODEL="gemini-2.0-flash"
export BOT_WEBHOOK_DOMAIN="tg-assistant.f-f.dev"

# Install dependencies
pip install -e .

# Run
python -m app.main
```
