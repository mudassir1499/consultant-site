# DFS Education — cPanel Deployment Guide
## Domain: dfsscholarships.com

---

## 1. Create a Python App in cPanel

1. Log in to cPanel → **Setup Python App**
2. Click **Create Application**:
   - **Python version**: 3.12 (or highest available, minimum 3.10)
   - **Application root**: `edu` (or wherever you upload files, e.g. `dfsscholarships`)
   - **Application URL**: leave as `/` (root domain)
   - **Application startup file**: `passenger_wsgi.py`
   - **Application entry point**: `application`
3. Click **Create** — cPanel will create a virtualenv automatically.
4. Note the **virtualenv activation command** shown at the top (e.g. `source /home/username/virtualenv/edu/3.12/bin/activate`).

---

## 2. Upload Project Files

### Option A — Git (recommended)
```bash
# SSH into your cPanel account
ssh username@dfsscholarships.com

# Go to the application root
cd ~/edu

# Clone the repo
git clone https://github.com/mudassir1499/consultant-site.git .
```

### Option B — File Manager / FTP
- Upload a ZIP of the project to the application root
- Extract it so that `manage.py`, `passenger_wsgi.py`, etc. are directly inside `~/edu/`

---

## 3. Install Dependencies

SSH into cPanel and activate the virtualenv:

```bash
source /home/username/virtualenv/edu/3.12/bin/activate
cd ~/edu
pip install -r requirements.txt
```

> **Note on mysqlclient**: If `mysqlclient` fails to install, ask your host to install the `mysql-devel` / `libmysqlclient-dev` system package. Alternatively, use `PyMySQL` instead:
> ```bash
> pip install PyMySQL
> ```
> Then add this to `manage.py` and `passenger_wsgi.py` at the top:
> ```python
> import pymysql
> pymysql.install_as_MySQLdb()
> ```

---

## 4. Create MySQL Database

1. cPanel → **MySQL Databases**
2. Create a new database (e.g. `username_dfsdb`)
3. Create a new user (e.g. `username_dfsuser`) with a strong password
4. Add the user to the database with **ALL PRIVILEGES**

---

## 5. Configure Environment Variables

```bash
cd ~/edu
cp .env.example .env
nano .env
```

Fill in all values:

```ini
SECRET_KEY=<generate-a-new-key>
DEBUG=False
ALLOWED_HOSTS=dfsscholarships.com,www.dfsscholarships.com
CSRF_TRUSTED_ORIGINS=https://dfsscholarships.com,https://www.dfsscholarships.com

DB_ENGINE=mysql
DB_NAME=username_dfsdb
DB_USER=username_dfsuser
DB_PASSWORD=your-strong-password
DB_HOST=localhost
DB_PORT=3306

EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=mail.dfsscholarships.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=noreply@dfsscholarships.com
EMAIL_HOST_PASSWORD=your-email-password
DEFAULT_FROM_EMAIL=DFS Education <noreply@dfsscholarships.com>

SECURE_SSL_REDIRECT=False
```

Generate a secret key:
```bash
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

---

## 6. Run Migrations & Create Superuser

```bash
source /home/username/virtualenv/edu/3.12/bin/activate
cd ~/edu

python manage.py migrate
python manage.py createsuperuser
```

---

## 7. Collect Static Files

```bash
python manage.py collectstatic --noinput
```

This copies all static files to `~/edu/staticfiles/`.

---

## 8. Set Up Static & Media File Serving

### Option A — Symlinks (recommended for cPanel)

cPanel serves files from `public_html`. Create symlinks:

```bash
# Static files
ln -s /home/username/edu/staticfiles /home/username/public_html/static

# Media files (uploads)
ln -s /home/username/edu/media /home/username/public_html/files
```

### Option B — cPanel Static Files Configuration

If your Python app root IS `public_html`, the static files will be served
directly by Apache. Make sure the `.htaccess` file is in place.

---

## 9. Copy .htaccess

Make sure the `.htaccess` file is in `public_html/`:
```bash
cp ~/edu/.htaccess ~/public_html/.htaccess
```

This forces HTTPS and lets Apache serve static/media files directly.

---

## 10. Restart the Application

In cPanel → **Setup Python App** → click **Restart** on your application.

Or via SSH:
```bash
touch ~/edu/tmp/restart.txt
```

---

## 11. Enable SSL (HTTPS)

1. cPanel → **SSL/TLS** or **Let's Encrypt**
2. Issue a free SSL certificate for `dfsscholarships.com` and `www.dfsscholarships.com`
3. Enable **Force HTTPS** in cPanel → **Domains** (or the .htaccess handles it)

---

## 12. Set Up Cron Jobs (Optional)

If you need scheduled tasks, go to cPanel → **Cron Jobs**:

```bash
# Example: clear expired sessions daily at 2 AM
0 2 * * * /home/username/virtualenv/edu/3.12/bin/python /home/username/edu/manage.py clearsessions
```

---

## 13. Post-Deployment Checklist

- [ ] Visit https://dfsscholarships.com — site loads
- [ ] Visit https://dfsscholarships.com/admin/ — admin panel works
- [ ] Register a test user — form submits, user created
- [ ] Upload a test file (e.g. receipt) — media files work
- [ ] Check static files load (CSS, images)
- [ ] Test email sending (password reset or notifications)
- [ ] Set up the Site Settings via admin panel (logo, contact info, etc.)
- [ ] Create offices and assign staff/agents

---

## Troubleshooting

### 500 Internal Server Error
- Check `~/edu/logs/django.log`
- Check cPanel → **Error Log** (Apache errors)
- Temporarily set `DEBUG=True` in `.env`, restart, and check the error page

### Static files not loading (404)
- Verify `collectstatic` ran successfully
- Check symlinks: `ls -la ~/public_html/static`
- Verify `STATIC_URL = '/static/'` in settings

### CSRF Verification Failed
- Ensure `CSRF_TRUSTED_ORIGINS` includes both `https://dfsscholarships.com` and `https://www.dfsscholarships.com`
- Clear browser cookies and try again

### Database Connection Error
- Verify credentials in `.env` match cPanel MySQL user/db
- Ensure user has ALL PRIVILEGES on the database
- Check `DB_HOST=localhost`

### Module Not Found
- Make sure virtualenv is activated before running commands
- Re-run `pip install -r requirements.txt`

---

## File Structure on cPanel

```
/home/username/
├── edu/                          ← Application root
│   ├── .env                      ← Environment variables (DO NOT share)
│   ├── manage.py
│   ├── passenger_wsgi.py         ← Passenger entry point
│   ├── requirements.txt
│   ├── main/                     ← Django project settings
│   ├── users/
│   ├── scholarships/
│   ├── finance/
│   ├── office/
│   ├── agent/
│   ├── headquarters/
│   ├── pages/
│   ├── static/                   ← Source static files
│   ├── staticfiles/              ← Collected static (after collectstatic)
│   ├── media/                    ← User uploads
│   ├── logs/                     ← Django logs
│   └── tmp/
│       └── restart.txt           ← Touch to restart Passenger
│
├── public_html/
│   ├── .htaccess                 ← HTTPS redirect + static rules
│   ├── static -> ../edu/staticfiles/  ← Symlink
│   └── files  -> ../edu/media/        ← Symlink
│
└── virtualenv/                   ← Created by cPanel Python App
    └── edu/
        └── 3.12/
```
