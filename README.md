# SakhiCare AI

This repository contains the FastAPI API in `backend/` and the standalone web prototype in `frontend/`.

The FastAPI backend provides JWT authentication, patient and follow-up workflows, and question answering over records and PDFs. It stores data in PostgreSQL with pgvector and uses OpenAI for chat and embeddings.

## Run with Docker Compose

Create `backend/.env` with the model settings shown below. Start Docker Desktop, then run this from the repository root:

```powershell
docker compose --env-file backend/.env up --build -d
```

Open http://localhost:5173/register for the frontend and http://127.0.0.1:8000/docs for the API. Compose runs PostgreSQL with pgvector, FastAPI, the web frontend, and the PDF indexing worker. Configure the OpenAI key in `backend/.env` before starting.

A fresh install starts with an empty database. Registration creates an ASHA account. Demo records, Super Admin team assignments and guideline PDFs from another system are not included. Use `docker compose down` to stop the stack while keeping its named volumes.

If you already created the PostgreSQL volume with your own credentials, keep using `docker compose --env-file backend/.env up --build -d` so it gets the same password. Stop any local Vite or FastAPI process currently using ports 5173 or 8000 first, or set `SAKHICARE_WEB_PORT` and `SAKHICARE_API_PORT` to free ports. The published ports are loopback-only and intended for local HTTP. For an existing database, apply pending schema upgrades separately.

## Run locally

Keep your existing backend/.env settings for DB_CONNECTION, SECRET_KEY, and ALGORITHM. The bundled Docker Compose service exposes PostgreSQL at 127.0.0.1:5433. If you use the bundled Compose service, set POSTGRES_PASSWORD in backend/.env to the same password used in DB_CONNECTION. From the repository root, with Docker running, execute the following.

```powershell
docker compose --env-file backend/.env up -d --wait postgres
Set-Location backend
uv sync --locked
uv run python -m uvicorn src.main:app --reload
```

For a fresh local database, set `AUTO_CREATE_TABLES=true` in `backend/.env` before starting FastAPI. Startup enables pgvector and creates missing tables. This setting cannot update existing columns or record an Alembic revision. Use Alembic for later schema changes and verify the schema before reconciling its revision history.

Open http://127.0.0.1:8000/docs for the API. If you use a PostgreSQL server other than the bundled container, it needs pgvector installed and the migration account needs permission to enable the extension, unless an administrator already enabled it.

## Load synthetic UI data

After starting Docker Desktop, applying the database migrations, and creating/signing into the `asha_demo_sunita` ASHA account, run this from the repository root to seed the Compose database:

```powershell
docker compose --env-file backend/.env exec -e ALLOW_SYNTHETIC_DATA=1 backend python -m src.patients.seed_demo
```

The idempotent loader adds 12 visibly marked `[TEST]` patients for the existing `asha_demo_sunita` ASHA account, with Hb history, varied screening and anemia assessments, referrals at different stages, and due, overdue, upcoming, and completed follow-ups. It also creates active and completed Care Pathways so their steps can be reviewed in the ASHA app. Repeat runs add only missing fixtures. It refuses non-local databases unless the explicit Docker-only `ALLOW_SYNTHETIC_DATA=1` flag is passed. All records are synthetic and are not clinical data.
## Run the web prototype

From the repository root, with Node.js and npm available:

```powershell
Set-Location frontend
npm ci
npm run dev
```

Registration and sign-in call FastAPI through Vite. The Patients screen loads and registers patients through FastAPI. PostgreSQL stores each patient under the signed-in ASHA account. Patient registration records the ASHA's consent confirmation and checks for likely duplicate records before allowing a separate registration. Patient pages show Hb history and trend, anemia assessment, referral status/outcome, follow-ups, Care Pathway steps, and activity history. A moderate/high-risk Hb result or a new referral starts a persistent pathway; recording attendance/outcome advances its steps. Super Admins can view pathways for their managed team, while only the assigned ASHA can mark steps complete. Ask Records uses a constrained, read-only tool call for questions the fixed query parser cannot map; the tool selects typed filters, and the backend executes scoped SQL. It never sends returned rows to the model or accepts arbitrary SQL. Supported patient-care changes use a separate preview and require ASHA Save/Cancel confirmation. The session cookie contains only a signed session token. Remember me keeps it for 24 hours by default (see REMEMBER_ME_HOURS). Use SESSION_COOKIE_SECURE=false only for local HTTP and SESSION_COOKIE_SECURE=true with HTTPS in deployed environments.

### Apply database upgrades

Existing databases need pending Alembic upgrades before using the new consent and patient activity fields. From the repository root, run:

```powershell
Set-Location backend
uv run alembic upgrade head
```

For a brand-new local database, `AUTO_CREATE_TABLES=true` creates the current tables. Alembic is the path for upgrading an existing database; `AUTO_CREATE_TABLES` does not alter existing tables.

### Pregnancy, ANC, and IFA tracking

Patient records support one active pregnancy episode at a time. ASHAs enter LMP and EDD from the care record; SakhiCare does not estimate dates or prescribe an IFA regimen. Planned ANC visits also appear in the existing follow-up list and can be marked completed or cancelled. Record IFA source/instructions from an authorized provider, then log only explicitly reported daily intake (`taken`, `missed`, or `unknown`). Three consecutive explicitly missed entries surface a check-in notice; unlogged days are never inferred as missed. Ask can prepare these changes as previews and requires ASHA Save/Cancel confirmation before writing. The patient page and Ask actions require current patient consent and enforce the existing ASHA patient scope.

## Android emulator setup (Windows)

SakhiCare's Android development preview uses Capacitor and the running web app. The Android project is in `frontend/android`.

### 1. Install Android tools

- Install [Android Studio](https://developer.android.com/studio/install) and finish the Setup Wizard.
- In **SDK Manager**, install **Android SDK Platform 36**, **Android SDK Platform-Tools**, **Android Emulator**, and a system image for your virtual device.
- In **Device Manager**, [create and start an Android Virtual Device](https://developer.android.com/studio/run/managing-avds). Wait for the Android home screen.

### 2. Start SakhiCare on the host

Use [Docker Compose](#run-with-docker-compose), or start the [backend](#run-locally) and [web frontend](#run-the-web-prototype) in separate terminals. Confirm the [web login](http://localhost:5173/login) loads on Windows. The emulator uses `10.0.2.2` to reach the Windows host and uses the same backend and database as the web app.

### 3. Build and run

From the repository root in a new PowerShell terminal:

```powershell
Set-Location frontend
$env:ANDROID_HOME = "$env:USERPROFILE\AppData\Local\Android\Sdk"
$env:SAKHICARE_ANDROID_URL = "http://10.0.2.2:5173"
npm.cmd ci
npm.cmd run android:run
```

If the SDK uses a different directory, set `ANDROID_HOME` to the **Android SDK Location** shown in SDK Manager. If the frontend uses a different port, update `SAKHICARE_ANDROID_URL` to match. Keep the host services running while you test.

To launch from Android Studio, run `npm.cmd run android:sync` and `npm.cmd run android:open` in the same terminal, then select the virtual device and click **Run**.

### Troubleshooting

| Error | What to check |
| --- | --- |
| `npm` or `npm.cmd` is not recognized | Open a new terminal after installing Node.js. If Node is installed in the standard Windows location, run `$env:Path = "C:\Program Files\nodejs;$env:Path"` and retry. |
| `ERR_SDK_NOT_FOUND` | Install the SDK in Android Studio. Set `ANDROID_HOME` to its actual location before running Capacitor. |
| No Android target found | Start the virtual device and run `& "$env:ANDROID_HOME\platform-tools\adb.exe" devices`. The emulator should appear as `device`. |
| The app opens but sign-in cannot reach the API | Check the frontend URL on Windows and confirm FastAPI is running. Verify the emulator URL uses `10.0.2.2` and the correct frontend port. |

The local HTTP rule applies to the Android debug build. A release build needs its own API and deployment configuration.

## RAG configuration

Set `CHAT_MODEL` and `EMBEDDING_MODEL` in `backend/.env` to models available on your OpenAI account, and set `MODEL_API_KEY` in that same backend environment. With Docker, pass `--env-file backend/.env` when starting Compose. Restart the API and worker after changing model settings.

Changing chat alone keeps existing embeddings. Changing the embedding provider or model requires re-uploading the PDFs to reindex them. OpenAI chat sends the question and retrieved excerpts to OpenAI. OpenAI embeddings send the question and document text used for indexing. Use public guidelines with hosted providers and keep patient details out of Ask Guidelines.


For a fresh manual setup, create `backend/.env` directly with these settings. Replace both password placeholders with the same password and use a unique random secret. URL-encode the password in `DB_CONNECTION` if it contains reserved URL characters.

```dotenv
POSTGRES_PASSWORD=replace-me
DB_CONNECTION=postgresql+psycopg://postgres:replace-me@127.0.0.1:5433/sakhicare
SECRET_KEY=replace-with-a-long-random-secret
ALGORITHM=HS256
AUTO_CREATE_TABLES=true
SESSION_COOKIE_SECURE=false
CHAT_MODEL=gpt-4.1-mini
EMBEDDING_MODEL=text-embedding-3-small
MODEL_API_KEY=
```

The frontend defaults to the local API on port 8000. For a different API address, set `BACKEND_URL` in `frontend/.env`.

The documents package owns authenticated PDF uploads, listing, indexing, and storage. Ask Guidelines answers from approved guideline PDFs; Ask Records reads patient and care-workflow data through scoped, structured queries. Ask does not use generic task records.

## Ask SakhiCare

The dashboard's Ask box and dedicated Ask page use the signed-in browser session to search only ready guidelines from the ASHA's assigned Super Admin. Responses include retrieved guideline titles, versions and page numbers, and return a no-match message when there is no supporting passage.

To configure the local guideline library, sign in as Super Admin through the API login and upload a reviewed public guideline with `POST /api/rag/upload`. Once the document worker marks it ready, it is searchable by the assigned team. Use `PUT /api/rag/documents/{document_id}/guideline` to set optional citation and language metadata.

### Ask Records changes

Ask Records can also prepare a care-record change. An ASHA reviews the patient and exact values, then explicitly selects **Save change** or **Cancel**. Nothing is written while the preview is being prepared. LangGraph pauses at this review step and stores its opaque workflow checkpoint in PostgreSQL; the protected application draft holds the actual patient details and expires after 15 minutes. Saving rechecks the ASHA's patient scope and the record's current values, then writes the change and patient activity event in one transaction.

Supported Ask changes include patient registration with confirmed consent, patient name/village/age correction, Hb screening, anemia assessment, consent updates, follow-up scheduling/completion/cancellation, and referral creation or progress updates. Cancelling a follow-up archives it so it disappears from active lists while staying in history. Ask does not hard-delete patient, Hb, referral, or consent history. Super Admin remains read-only in Ask Records.

The Docker API entrypoint applies Alembic migrations before starting, including the Ask draft and follow-up archive schema. For a local backend started directly with `uv`, run `uv run alembic upgrade head` from `backend/` after pulling schema changes.

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

The generic task API has been retired from the SakhiCare app. The historical baseline migration and any existing `user_tasks` table are retained so existing databases and task data are not dropped; this table is no longer exposed by the API or used by Ask.

PDFs indexed with a different embedding model stay listed, but must be re-uploaded to regenerate vectors for the configured OpenAI embedding model.
