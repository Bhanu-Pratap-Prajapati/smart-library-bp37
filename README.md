# Smart Library Management System

Production-ready auth stack added on top of the existing Smart Library app:
- Backend: Flask + MySQL
- Frontend: React (in `frontend/pages/login.html`) + Tailwind
- Auth: bcrypt password hashing, JWT auth, Google OAuth 2.0

## Auth Features
- Email/password signup (`name`, `email`, `password`) with duplicate email protection
- Strong password rules (min 8, uppercase, lowercase, number, special char)
- Login with JWT token issuance
- Google OAuth login/signup with account auto-provisioning
- JWT-protected private APIs
- Environment-driven secrets/config

## Key Auth APIs
- `POST /api/signup`
- `POST /api/login`
- `GET /api/auth/google`
- `GET /api/auth/google/callback`

Compatibility routes kept:
- `POST /api/register` (legacy frontend compatibility)

## Database
`users` table includes:
- `id`
- `full_name` (name)
- `email` (unique)
- `password_hash` (bcrypt hash)
- `google_id` (nullable, unique)
- `created_at`

Schema file: `database/schema.sql`

## Folder Structure
- `backend/`
- `frontend/`
- `database/schema.sql`

## Setup (Windows)
1. Create virtual env and install deps
```bash
python -m venv .venv
.\.venv\Scripts\activate
pip install -r backend\requirements.txt
```

2. Configure env
- Copy `backend/.env.example` to `backend/.env`
- Fill MySQL + JWT + Google OAuth values

3. Create Google OAuth credentials
- In Google Cloud Console, create OAuth client (Web application)
- Authorized redirect URI must include:
  - `http://127.0.0.1:5000/api/auth/google/callback`

4. Initialize DB and seed baseline data
```bash
python backend\init_db.py
```

5. Run backend
```bash
python backend\app.py
```

6. Open frontend
- Serve/open `frontend/pages/login.html` from your frontend host (for example `http://127.0.0.1:5500/frontend/pages/login.html`)

## Frontend Auth Integration
- Login/Signup form posts to backend auth APIs
- Google button redirects to `/api/auth/google`
- OAuth callback stores:
  - `smartLibraryToken` in `localStorage`
  - `smartLibraryUser` in `localStorage`

## Notes
- Private routes rely on `Authorization: Bearer <jwt>`
- Update `FRONTEND_URL` and `FRONTEND_LOGIN_PATH` in `.env` if your frontend runs on a different host/path
