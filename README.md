# DFS Education — Scholarship Consultancy Platform

A Django-based platform that manages the full lifecycle of international scholarship
applications for an education consultancy — from a student applying, through
multi-level document review, payment verification, university submission, and
commission payouts to agents and headquarters.

## Tech stack

- **Django 6.0** (Python 3.12)
- **SQLite** for development, **MySQL** supported for production (`DB_ENGINE=mysql`)
- **Bootstrap 5** UI, **WhiteNoise** for static file serving
- Deployment: cPanel / Passenger WSGI (see `DEPLOYMENT.md`)

## Roles & panels

| Role | Login URL | Responsibility |
|------|-----------|----------------|
| **Student** (`user`) | `/users/login/` | Browse scholarships, apply, upload documents, pay |
| **Office** (`office`) | `/office/login/` | Branch staff — create/review applications, verify documents & payments, forward to agent |
| **Main Agent** (`agent`) | `/agent/login/` | Approve applications, review admission letters & JW02 forms, **add scholarships**, earn commission (wallet) |
| **Headquarters** (`headquarters`) | `/hq/login/` | Submit to university, upload admission letters & JW02 forms, earn commission |
| **Admin** (superuser) | `/admin-portal/` | Full operations console: users, offices, banks, scholarships, payments, withdrawals, site settings |

## Application workflow

```
draft → submitted → under_review → documents_verified → payment_verified
      → approved (agent) → in_progress (HQ) → admission_letter_uploaded
      → admission_letter_approved (agent → wallet: upcoming)
      → jw02_uploaded → jw02_approved (agent → wallet: balance) → complete
```

Every transition is written to `ApplicationStatusHistory` (audit trail) and notifies
the relevant users. Commissions flow through the wallet:
`upcoming → current_balance → withdrawal request → admin approval → paid out`.

## Local setup

```bash
# 1. Virtual environment
python -m venv venv
venv\Scripts\activate            # Windows
# source venv/bin/activate       # macOS/Linux

# 2. Dependencies
pip install -r requirements.txt

# 3. Environment — copy the example and set values
cp .env.example .env             # set SECRET_KEY, DEBUG=True, DB_ENGINE=sqlite3

# 4. Database + demo data
python manage.py migrate
python manage.py seed_data --flush

# 5. Run
python manage.py runserver
```

Then open http://127.0.0.1:8000/.

## Seeded demo logins

Created by `python manage.py seed_data`:

| Role | Username | Password |
|------|----------|----------|
| Admin | `admin` | `admin123` |
| Office | `sarah_office` | `office123` |
| Agent | `li_agent` | `agent123` |
| Headquarters | `chen_hq` | `hq123` |
| Student | `john_doe` | `student123` |

## Running the tests

```bash
python manage.py test
```

The suite covers the end-to-end application workflow and the wallet
commission/withdrawal math.

## Environment variables

Key settings read from `.env` (see `.env.example`):

- `SECRET_KEY` — **required** when `DEBUG=False`
- `DEBUG` — `True`/`False`
- `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS` — comma-separated
- `DB_ENGINE` — `sqlite3` (default) or `mysql` (+ `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT`)
- `EMAIL_*` — SMTP configuration (defaults to console backend)

## Deployment

See [`DEPLOYMENT.md`](DEPLOYMENT.md) for the cPanel / Passenger deployment guide.
