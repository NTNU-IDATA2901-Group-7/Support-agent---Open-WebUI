# AI Support Agent

An AI-powered support agent built for Solwr, a Norwegian logistics software company. The system extends [Open WebUI](https://github.com/open-webui/open-webui) with a custom RAG pipeline, Jira integration, and Microsoft Entra ID authentication to help support teams resolve recurring issues faster and create better-structured tickets.

Built as a bachelor thesis project at NTNU, 2026.

---

## Prerequisites

- [Docker](https://www.docker.com/) and Docker Compose
- [Node.js](https://nodejs.org/) `vX.X.X` or higher *(fill in version)*
- Access to the following external services:
  - Azure OpenAI (GPT-4.1-mini and text-embedding-3-large)
  - Microsoft Entra ID (for authentication)
  - Atlassian Jira (OAuth 2.0)
  - PostgreSQL with pgvector extension

---

## Getting Started

### 1. Clone the repository

```bash
git clone https://github.com/<your-org>/<your-repo>.git
cd <your-repo>
```

### 2. Configure environment variables

```bash
cp .env.example .env
```

Open `.env` and fill in the required values. See [Environment Variables](#environment-variables) below for a description of each.

### 3. Run the application

```bash
docker compose up
```

The application will be available at `http://localhost:8080`.

For frontend development without Docker, you can run the Svelte frontend separately:

```bash
npm install
npm run dev
```

---

## Environment Variables

The `.env.example` file contains all required variables with placeholder values. The table below describes the ones you need to fill in.

### Azure OpenAI

| Variable | Description |
|---|---|
| `OPENAI_API_KEY` | API key for Azure OpenAI |
| `OPENAI_API_BASE_URL` | Azure OpenAI deployment endpoint for the chat model |
| `RAG_AZURE_OPENAI_API_KEY` | API key for the embedding model (can be the same as above) |
| `RAG_AZURE_OPENAI_BASE_URL` | Azure OpenAI base URL for embeddings |
| `RAG_AZURE_OPENAI_API_VERSION` | API version, e.g. `2024-12-01-preview` |

### Microsoft Entra ID

| Variable | Description |
|---|---|
| `MICROSOFT_CLIENT_ID` | Application (client) ID from Azure AD app registration |
| `MICROSOFT_CLIENT_SECRET` | Client secret from Azure AD app registration |
| `MICROSOFT_CLIENT_TENANT_ID` | Tenant ID of your Microsoft organization |
| `OPENID_PROVIDER_URL` | OpenID configuration URL (replace tenant ID in the URL) |

### Jira Integration

| Variable | Description |
|---|---|
| `JIRA_DOMAIN` | Your Atlassian domain, e.g. `yourcompany.atlassian.net` |
| `JIRA_CLOUD_ID` | Found at `https://<your-domain>/_edge/tenant_info` |
| `JIRA_PROJECT_KEY` | The Jira project key to create tickets in |
| `JIRA_SERVICE_ACCOUNT_EMAIL` | Email of the Jira service account used for sync |
| `JIRA_SERVICE_ACCOUNT_API_TOKEN` | API token for the service account |
| `ATLASSIAN_CLIENT_ID` | OAuth 2.0 client ID from Atlassian developer console |
| `ATLASSIAN_CLIENT_SECRET` | OAuth 2.0 client secret |
| `ATLASSIAN_REDIRECT_URI` | OAuth callback URL, e.g. `http://localhost:8080/oauth/atlassian/callback` |

### Database

| Variable | Description |
|---|---|
| `DATABASE_URL` | PostgreSQL connection string |
| `PGVECTOR_DB_URL` | PostgreSQL connection string for the vector database (can be the same) |

### Testing

| Variable | Description |
|---|---|
| `OPEN_WEBUI_EMAIL` | Test account email used by the agent test runner |
| `OPEN_WEBUI_PASSWORD` | Test account password |
| `TEST_TICKET_KEY` | A known Jira ticket key used by deterministic smoke tests, e.g. `SR-1` |

---

## Running the Test Suite

*Fill in the commands to run the agent test suite here.*

The test suite is described in detail in the thesis (Section 4.5.4). It includes assertion-based tests and LLM-judge evaluation using MRR, Precision, and Recall metrics.

---

## Project Structure

The project is a fork of Open WebUI. Custom code is integrated directly into the existing folder structure rather than kept in a separate module.

```
.
├── .github/          # CI workflows (GitHub Actions)
├── backend/          # FastAPI backend, including custom Jira endpoints and RAG pipeline
├── cypress/          # End-to-end tests
├── docs/             # Documentation
├── scripts/          # Utility scripts
├── src/              # Svelte frontend, including custom components
├── static/           # Static assets
└── tests/            # Agent test suite
```

Custom frontend components are located in `src/lib/components/` alongside the existing Open WebUI components. Custom backend endpoints are located in `backend/open_webui/routers/`.

---

## Built With

- [Open WebUI](https://github.com/open-webui/open-webui) — base platform
- [FastAPI](https://fastapi.tiangolo.com/) — backend framework
- [Svelte](https://svelte.dev/) — frontend framework
- [pgvector](https://github.com/pgvector/pgvector) — vector similarity search
- [Azure OpenAI](https://azure.microsoft.com/en-us/products/ai-services/openai-service) — language and embedding models
- [FastMCP](https://github.com/jlowin/fastmcp) — MCP server framework
