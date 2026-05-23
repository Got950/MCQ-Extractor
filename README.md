# MCQ Extractor

Production-grade web app that extracts multiple-choice questions from academic
PDFs using an LLM, stores them in MongoDB Atlas, and exposes a review/edit UI
with MathJax.

- **Backend (Render):** FastAPI + PyMongo
- **Database:** MongoDB Atlas (`MONGODB_URI`)
- **Frontend (Netlify):** Vite + React
- **Auth:** Email + password, bcrypt, JWT (HS256); superadmin seeded on deploy
- **Job queue:** Redis + RQ (optional) / in-process BackgroundTasks (default)
- **Storage:** Local disk (dev) / S3-compatible (prod on Render)

## Repository layout

```
mcq-extractor/
├── backend/           FastAPI API (deploy to Render)
│   ├── main.py
│   ├── database.py    MongoDB connection + indexes
│   ├── repos.py       Data access
│   ├── models.py
│   └── scripts/init_database.py
├── frontend/          React SPA (deploy to Netlify)
│   ├── netlify.toml
│   └── src/api/client.js   VITE_API_URL → Render API
├── render.yaml        Render blueprint (API + optional worker)
└── .github/workflows/ci.yml
```

## Local development

### 1. MongoDB

Use [MongoDB Atlas](https://www.mongodb.com/cloud/atlas) (free tier) or local
MongoDB. Copy `backend/.env.example` to `backend/.env` and set `MONGODB_URI`.

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m scripts.init_database   # indexes + superadmin (if env vars set)
uvicorn main:app --reload --port 8000
```

### 2. Frontend

```bash
cd frontend
npm install
npm run dev    # http://localhost:5173 — proxies /api to :8000
```

## Deployment

### Backend — Render

1. Push the repo and create a **Blueprint** from `render.yaml` (or a Web Service
   with root directory `backend`).
2. In Render **Environment**, set:
   - `MONGODB_URI` — Atlas connection string (`mongodb+srv://…`)
   - `MONGODB_DB_NAME` — e.g. `mcq_extractor`
   - `SUPERADMIN_EMAIL` / `SUPERADMIN_PASSWORD` — created on first deploy build
   - `ALLOWED_ORIGIN` — your Netlify URL, e.g. `https://your-app.netlify.app`
   - `APP_SECRET` — long random string (or use Render generate)
   - `GEMINI_API_KEY` — required for extraction
3. Build runs `python -m scripts.init_database` then starts `uvicorn`.
4. Note the public URL, e.g. `https://mcq-extractor-api.onrender.com`.

**Render filesystem is ephemeral.** Use S3/R2 (`S3_BUCKET`, etc.) for PDF storage
in production, or accept that PDFs are lost on redeploy (extracted questions stay
in MongoDB).

### Frontend — Netlify

1. **Site settings → Build:** base directory `frontend`, publish `dist` (or use
   `netlify.toml` in that folder).
2. **Environment variables:**
   - `VITE_API_URL` = `https://YOUR-RENDER-SERVICE.onrender.com/api`
3. Deploy. The SPA calls the Render API directly; CORS must include your Netlify
   origin in `ALLOWED_ORIGIN` on Render.

### MongoDB Atlas setup

1. Create a free cluster → **Database Access** → add a database user.
2. **Network Access** → allow `0.0.0.0/0` (or Render’s egress IPs if restricted).
3. **Connect** → Drivers → copy the connection string into `MONGODB_URI`.
4. Replace `<password>` with the user password (URL-encode special characters).

## Environment variables

| Var | Where | Purpose |
|-----|--------|---------|
| `MONGODB_URI` | Render | Atlas connection string |
| `MONGODB_DB_NAME` | Render | Database name (default `mcq_extractor`) |
| `SUPERADMIN_EMAIL` | Render | Initial admin login |
| `SUPERADMIN_PASSWORD` | Render | Initial admin password |
| `ALLOWED_ORIGIN` | Render | Netlify URL(s), comma-separated |
| `VITE_API_URL` | Netlify | `https://…onrender.com/api` |
| `APP_SECRET` | Render | JWT signing |
| `GEMINI_API_KEY` | Render | LLM extraction |

See `backend/.env.example` and `frontend/.env.example` for the full list.

## Superadmin

On deploy, Render’s build command runs `init_database`, which creates the
superadmin user if `SUPERADMIN_EMAIL` / `SUPERADMIN_PASSWORD` are set and the
email does not exist yet. Superadmins get a higher upload limit
(`SUPERADMIN_MAX_UPLOADS`, default 100).

Regular users can still register via `/api/auth/register` unless you restrict
that in your product policy.

## Tests

```bash
cd backend
pytest -q
```

Tests use in-memory `mongomock://` — no Atlas connection required for CI.

## API surface

All `/api/*` routes except health, providers, and auth require
`Authorization: Bearer <jwt>`.

| Method | Path | Auth |
|--------|------|------|
| `GET` | `/api/health` | No |
| `GET` | `/api/ready` | No |
| `POST` | `/api/auth/register` | No |
| `POST` | `/api/auth/login` | No |
| `GET` | `/api/auth/me` | Yes |
| `POST` | `/api/upload` | Yes |
| `GET` | `/api/jobs` | Yes |
| `GET` | `/api/jobs/{id}` | Yes |
| `GET` | `/api/jobs/{id}/questions` | Yes |
| `PUT` | `/api/questions/{id}` | Yes |
