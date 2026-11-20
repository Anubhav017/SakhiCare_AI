# SakhiCare AI

This repository contains the FastAPI API in `backend/` and the standalone web prototype in `frontend/`.

The FastAPI backend currently provides JWT authentication, per-user tasks, and question answering over tasks and PDFs. It stores data in PostgreSQL with pgvector and uses your local Ollama server for embeddings and chat.

## Run with Docker Compose

Start Docker Desktop, then run this from the repository root:

```powershell
docker compose up --build -d
```

Open http://localhost:5173/register for the frontend and http://127.0.0.1:8000/docs for the API. Compose runs PostgreSQL with pgvector, FastAPI, the web frontend, Ollama and the PDF indexing worker. The first start downloads the Ollama models. Use `docker compose logs -f ollama-models` to see download progress. The web app is available independently of model download completion.

A fresh install starts with an empty database. Registration creates an ASHA account. Demo records, Super Admin team assignments and guideline PDFs from another system are not included. Use `docker compose down` to stop the stack while keeping its named volumes.

If you already created the PostgreSQL volume with your own credentials, keep using `docker compose --env-file backend/.env up --build -d` so it gets the same password. Stop any local Vite or FastAPI process currently using ports 5173 or 8000 first, or set `SAKHICARE_WEB_PORT` and `SAKHICARE_API_PORT` to free ports. The published ports are loopback-only and intended for local HTTP. For an existing database, apply pending schema upgrades separately.

## Run locally

Keep your existing backend/.env settings for DB_CONNECTION, SECRET_KEY, and ALGORITHM. The bundled Docker Compose service exposes PostgreSQL at 127.0.0.1:5433. If you use the bundled Compose service, set POSTGRES_PASSWORD in backend/.env to the same password used in DB_CONNECTION. From the repository root, with Docker and Ollama running, execute the following.

```powershell
docker compose --env-file backend/.env up -d --wait postgres
Set-Location backend
uv sync --locked
uv run python -m uvicorn src.main:app --reload
```

For a fresh local database, set `AUTO_CREATE_TABLES=true` in `backend/.env` before starting FastAPI. Startup enables pgvector and creates missing tables. This setting cannot update existing columns or record an Alembic revision. Use Alembic for later schema changes and verify the schema before reconciling its revision history.

Open http://127.0.0.1:8000/docs for the API. If you use a PostgreSQL server other than the bundled container, it needs pgvector installed and the migration account needs permission to enable the extension, unless an administrator already enabled it.

## Run the web prototype

From the repository root, with Node.js and npm available:

```powershell
Set-Location frontend
npm ci
npm run dev
```

Registration and sign-in call FastAPI through Vite. The Patients screen loads and registers patients through FastAPI. PostgreSQL stores each patient under the signed-in ASHA account. Select a patient name to open their record, or open Follow-ups from the workspace navigation. ASHAs can schedule and complete follow-ups for their patients. Super admins can view follow-ups for their assigned team. Follow-ups are stored in PostgreSQL. Measured Hb readings are stored in the patient timeline. The session cookie contains only a signed session token. Remember me keeps it for 24 hours by default (see REMEMBER_ME_HOURS). Use SESSION_COOKIE_SECURE=false only for local HTTP and SESSION_COOKIE_SECURE=true with HTTPS in deployed environments.

## RAG configuration

Ollama uses the same default models as the separate rag_app repo. For a fresh setup, copy backend/.env.example to backend/.env and fill in the database credentials and JWT secret. For an existing setup, add only the variables you want to override. The example lists defaults for Ollama, upload size, chunking, batching, and retrieval. Restart the application after changing environment settings.

If a model is missing, run `ollama pull nomic-embed-text` or `ollama pull llama3.2:3b`.

The documents package owns authenticated PDF uploads, listing, indexing, and storage. The RAG package owns question answering through /api/ask and gathers user-scoped evidence from PDFs and tasks. Both use the shared AI client for Ollama requests.

## Ask SakhiCare

The dashboard's Ask box and dedicated Ask page use the signed-in browser session to search only ready guidelines from the ASHA's assigned Super Admin. Responses include retrieved guideline titles, versions and page numbers, and return a no-match message when there is no supporting passage.

To configure the local guideline library, sign in as Super Admin through the API login and upload a reviewed public guideline with `POST /api/rag/upload`. Once the document worker marks it ready, it is searchable by the assigned team. Use `PUT /api/rag/documents/{document_id}/guideline` to set optional citation and language metadata.

## Document indexing worker

Run the worker in a second terminal from backend/ after applying the migrations:

```powershell
uv run python -m src.documents.worker
```

The API and worker use the same PostgreSQL database and embedding model setting. In a deployment, run the worker as a separate supervised process. The worker claims jobs with a lease, renews it between embedding batches, and retries temporary failures. Pending uploads stay in PostgreSQL when either process restarts.

- `POST /api/rag/upload` stores the original PDF privately in PostgreSQL and returns `202 Accepted` with the document ID, indexing status, and a `Location` header. An already indexed duplicate returns `200 OK`.
- `GET /api/rag/documents/{document_id}` shows `pending`, `processing`, `ready`, or `failed` to the document owner. Failed jobs include an error. Re-upload an identical file to retry a failed job.
- `GET /api/rag/documents` includes the indexing status of each document. `/api/ask` searches ready documents only.

Uploaded PDFs are retained in the database along with their vectors, so include them when sizing and backing up PostgreSQL. Older document records do not have an original PDF until the file is uploaded again.

## Existing data

The migration preserves existing tasks. Legacy tasks with no owner stay in the database and are excluded from per-user endpoints until an owner is assigned. Apply upgrades to existing databases with the online Alembic command shown above.

PDFs previously embedded with OpenAI stay listed in your documents. Re-upload the original PDFs to replace their old vectors and make them searchable with Ollama. Re-upload is also needed when you change the embedding model.
