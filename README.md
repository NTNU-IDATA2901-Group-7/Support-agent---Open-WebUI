# AI Support Agent

An AI-powered support agent built for Solwr, a Norwegian logistics software company. The system extends [Open WebUI](https://github.com/open-webui/open-webui) with a custom RAG pipeline, Jira integration, Microsoft Entra ID authentication, and AI-assisted ticket creation.

The goal of the system is to help support teams resolve recurring issues faster by retrieving relevant information from historical Jira tickets and internal documentation, while also helping users create better-structured support tickets.

Built as a bachelor thesis project at NTNU, 2026.

---

## Prerequisites

- [Docker](https://www.docker.com/) and Docker Compose
- [Node.js](https://nodejs.org/) `v22.14.0` or higher
- Python `3.11`
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

Open `.env` and fill in the required values. See [Environment Variables](#environment-variables) for a description of the most important variables.

### 3. Run the application with Docker

The first time you run the application, use:

```bash
docker compose up --build
```

This builds the required containers and starts the full application stack.

For later runs, you can usually use:

```bash
docker compose up
```

The application will be available at:

```text
http://localhost:8080
```

---

## Local Development Setup

The project can also be run locally without Docker during development. In this setup, the frontend and backend are started in separate terminals.

### Frontend

From the project root:

```bash
npm install
npm run build
npm run dev
```

The frontend development server starts at:

```text
http://localhost:5173
```

### Backend

Open a second terminal and navigate to the backend folder:

```bash
cd backend
```

Create and activate a Python 3.11 environment.

#### Option A: Conda

```bash
conda create --name open-webui python=3.11
conda activate open-webui
```

#### Option B: venv

```bash
python3 -m venv venv
source venv/bin/activate
```

On Windows:

```bash
venv\Scripts\activate
```

Install backend dependencies:

```bash
pip install -r requirements.txt -U
```

Start the backend:

```bash
sh dev.sh
```

If `sh dev.sh` does not work, start the backend manually with Uvicorn:

```bash
uvicorn open_webui.main:app --reload --host 0.0.0.0 --port 8080
```

The backend starts at:

```text
http://localhost:8080
```

After the backend has started, refresh the frontend at:

```text
http://localhost:5173
```

---

## Environment Variables

The `.env.example` file contains the required variables with placeholder values. The table below describes the most important variables that must be configured.

### Azure OpenAI

| Variable                       | Description                                                               |
| ------------------------------ | ------------------------------------------------------------------------- |
| `OPENAI_API_KEY`               | API key for Azure OpenAI                                                  |
| `OPENAI_API_BASE_URL`          | Azure OpenAI deployment endpoint for the chat model                       |
| `RAG_AZURE_OPENAI_API_KEY`     | API key for the embedding model. This can be the same as `OPENAI_API_KEY` |
| `RAG_AZURE_OPENAI_BASE_URL`    | Azure OpenAI base URL for embeddings                                      |
| `RAG_AZURE_OPENAI_API_VERSION` | Azure OpenAI API version, for example `2024-12-01-preview`                |

### Microsoft Entra ID

| Variable                     | Description                                                        |
| ---------------------------- | ------------------------------------------------------------------ |
| `MICROSOFT_CLIENT_ID`        | Application/client ID from the Microsoft Entra ID app registration |
| `MICROSOFT_CLIENT_SECRET`    | Client secret from the Microsoft Entra ID app registration         |
| `MICROSOFT_CLIENT_TENANT_ID` | Tenant ID of the Microsoft organization                            |
| `OPENID_PROVIDER_URL`        | OpenID configuration URL for the Microsoft tenant                  |

### Jira Integration

| Variable                         | Description                                                                      |
| -------------------------------- | -------------------------------------------------------------------------------- |
| `JIRA_DOMAIN`                    | Atlassian domain, for example `yourcompany.atlassian.net`                        |
| `JIRA_CLOUD_ID`                  | Jira cloud ID, found at `https://<your-domain>/_edge/tenant_info`                |
| `JIRA_PROJECT_KEY`               | Jira project key where support tickets are created                               |
| `JIRA_SERVICE_ACCOUNT_EMAIL`     | Email of the Jira service account used for synchronization                       |
| `JIRA_SERVICE_ACCOUNT_API_TOKEN` | API token for the Jira service account                                           |
| `ATLASSIAN_CLIENT_ID`            | OAuth 2.0 client ID from the Atlassian developer console                         |
| `ATLASSIAN_CLIENT_SECRET`        | OAuth 2.0 client secret                                                          |
| `ATLASSIAN_REDIRECT_URI`         | OAuth callback URL, for example `http://localhost:8080/oauth/atlassian/callback` |

### Database

| Variable          | Description                                                                                  |
| ----------------- | -------------------------------------------------------------------------------------------- |
| `DATABASE_URL`    | PostgreSQL connection string                                                                 |
| `PGVECTOR_DB_URL` | PostgreSQL connection string for the vector database. This can be the same as `DATABASE_URL` |

### Testing

| Variable              | Description                                                                 |
| --------------------- | --------------------------------------------------------------------------- |
| `OPEN_WEBUI_EMAIL`    | Test account email used by the agent test runner                            |
| `OPEN_WEBUI_PASSWORD` | Test account password                                                       |
| `TEST_TICKET_KEY`     | Known Jira ticket key used by deterministic smoke tests, for example `SR-1` |

---

## Running the Test Suite

The project includes an agent test suite using DeepEval. The tests are located in the test suite directory and include assertion-based retrieval tests and LLM-based evaluation.

Run the full assertion-based retrieval collection:

```bash
deepeval test run assertion_based/test_retrieval.py
```

Run one specific test:

```bash
deepeval test run 'assertion_based/test_retrieval.py::test_retrieval[missing_packing_slip_tm]'
```

The test suite is described in more detail in the bachelor thesis. It includes assertion-based tests and LLM-judge evaluation for assessing retrieval quality and agent behavior.

---

## Project Structure

The project is a fork of Open WebUI. Custom code is integrated directly into the existing Open WebUI folder structure rather than being kept as a separate module.

```text
.
├── .github/          # CI workflows using GitHub Actions
├── backend/          # FastAPI backend, custom Jira endpoints, RAG pipeline, and MCP integration
├── cypress/          # End-to-end tests
├── docs/             # Documentation
├── scripts/          # Utility scripts
├── src/              # Svelte frontend, including custom components
├── static/           # Static assets
└── tests/            # Agent test suite
```

Custom frontend components are located in `src/lib/components/` alongside the existing Open WebUI components.

Custom backend endpoints are located in `backend/open_webui/routers/`.

---

## Built With

- [Open WebUI](https://github.com/open-webui/open-webui) — base platform
- [FastAPI](https://fastapi.tiangolo.com/) — backend framework
- [Svelte](https://svelte.dev/) — frontend framework
- [PostgreSQL](https://www.postgresql.org/) — relational database
- [pgvector](https://github.com/pgvector/pgvector) — vector similarity search
- [Azure OpenAI](https://azure.microsoft.com/en-us/products/ai-services/openai-service) — language and embedding models
- [Atlassian Jira](https://www.atlassian.com/software/jira) — ticket management
- [Microsoft Entra ID](https://www.microsoft.com/en-us/security/business/identity-access/microsoft-entra-id) — authentication
- [FastMCP](https://github.com/jlowin/fastmcp) — MCP server framework
- [DeepEval](https://github.com/confident-ai/deepeval) — LLM application testing

---

## Main Features

- Microsoft Entra ID login using OpenID Connect
- Atlassian Jira OAuth 2.0 connection
- Chat-based support interface
- Retrieval-augmented generation using historical Jira tickets and internal documentation
- Hybrid retrieval using keyword and vector search
- Reranking of retrieved tickets
- AI-assisted Jira ticket drafting
- Jira ticket creation directly from the chat interface
- Attachment handling when creating Jira tickets
- Admin interface for synchronizing Jira tickets into the vector database
- Docker-based local deployment
- Agent test suite using DeepEval

---

## License and Attribution

This project is based on [Open WebUI](https://github.com/open-webui/open-webui), which is licensed under the Open WebUI License.

The original Open WebUI copyright and license notices are preserved in accordance with the original project license. This bachelor project extends Open WebUI with additional functionality for Microsoft authentication, Jira integration, retrieval-augmented support workflows, AI-assisted ticket creation, and support-specific evaluation.

This project was developed as a bachelor thesis proof of concept at NTNU in collaboration with Solwr.

### Open WebUI License

```text
Open WebUI License

Copyright (c) 2023- Open WebUI Inc. [Created by Timothy Jaeryang Baek]
All rights reserved.

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are met:

1. Redistributions of source code must retain the above copyright notice, this
   list of conditions and the following disclaimer.

2. Redistributions in binary form must reproduce the above copyright notice,
   this list of conditions and the following disclaimer in the documentation
   and/or other materials provided with the distribution.

3. Neither the name of the copyright holder nor the names of its
   contributors may be used to endorse or promote products derived from
   this software without specific prior written permission.

4. Notwithstanding any other provision of this License, and as a material
   condition of the rights granted herein, licensees are strictly prohibited
   from altering, removing, obscuring, or replacing any "Open WebUI"
   branding, including but not limited to the name, logo, or any visual,
   textual, or symbolic identifiers that distinguish the software and its
   interfaces, in any deployment or distribution, except in the following
   circumstances: (i) deployments or distributions where the total number
   of end users (defined as individual natural persons with direct access
   to the application) does not exceed fifty (50) within any rolling
   thirty (30) day period; (ii) the licensee has obtained specific prior
   written permission from the copyright holder; or (iii) where the
   licensee has obtained a duly executed enterprise license expressly
   permitting such modification. For all other cases, any removal or
   alteration of the "Open WebUI" branding shall constitute a material
   breach of license.

Materials governed by prior licenses retain those original license
terms, as specified in LICENSE_HISTORY.

By contributing to this project, you agree to the project's Contributor
License Agreement (CONTRIBUTOR_LICENSE_AGREEMENT).

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
DAMAGES INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION HOWEVER
CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
OR TORT INCLUDING NEGLIGENCE OR OTHERWISE ARISING IN ANY WAY OUT OF THE USE
OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
```

---

## Project Status

This repository represents the MVP/proof-of-concept release developed as part of the bachelor thesis.

The system demonstrates the feasibility of an AI-assisted support workflow, but it is not intended as a production-ready deployment without further testing, security review, and operational hardening.

Known limitations include:

- The system has not been evaluated through large-scale production deployment.
- AI-generated answers and ticket drafts should be reviewed by a human user.
- Data isolation and organizational separation require further work before multi-customer production use.
- External services such as Jira, Microsoft Entra ID, and Azure OpenAI are required for full functionality.
- Retrieval quality depends on the quality and structure of the available Jira tickets and documentation.
