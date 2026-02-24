# DFS Education — cPanel Deployment Guide (SQLite / Testing)
## Domain: dfsscholarships.com

> **This guide uses SQLite** for quick testing. When you're ready for production,
> switch to MySQL — see the "Switching to MySQL" section at the bottom.

---

## Prerequisites

- cPanel hosting with **Python App support** (Phusion Passenger)
- SSH access to your hosting account
- Domain `dfsscholarships.com` pointed to your hosting nameservers
- SSL certificate (free via Let's Encrypt in cPanel)

---

## Step 1 — Create a Python App in cPanel

1. Log in to **cPanel** → find **Setup Python App** (under Software)
2. Click **+ Create Application**
3. Fill in:

   | Field                    | Value                        |
   |--------------------------|------------------------------|
   | Python version           | `3.12` (or highest ≥ 3.10)  |
   | Application root         | `edu`                        |
   | Application URL          | `/` (root domain)            |
   | Application startup file | `passenger_wsgi.py`          |
   | Application entry point  | `application`                |

4. Click **Create**
5. **Important:** Copy the virtualenv activation command shown at the top — you'll need it. It looks like:
   ```
   source /home/YOUR_USERNAME/virtualenv/edu/3.12/bin/activate
   ```

---

## Step 2 — Upload Project Files

### Option A: Git Clone (Recommended)

SSH into your account:
```bash
ssh YOUR_USERNAME@dfsscholarships.com
```

Navigate to the app root and clone:
```bash
cd ~/edu
# Remove any default files cPanel created
rm -f passenger_wsgi.py

# Clone your repo directly into this folder
git clone https://github.com/mudassir1499/consultant-site.git .
```

### Option B: File Manager / FTP

1. Download the project as a ZIP from GitHub
2. In cPanel → **File Manager**, navigate to `/home/YOUR_USERNAME/edu/`
3. Upload the ZIP and extract it
4. Make sure `manage.py` and `passenger_wsgi.py` are directly inside `~/edu/` (not in a subfolder)

---

## Step 3 — Install Dependencies

```bash
# Activate the virtualenv (use YOUR command from Step 1)
source /home/YOUR_USERNAME/virtualenv/edu/3.12/bin/activate

# Go to project root
cd ~/edu

# Install packages
pip install --upgrade pip
pip install -r requirements.txt
```

This installs Django, Pillow, and python-dotenv. That's all you need for SQLite.

---

## Step 4 — Configure Environment Variables

```bash
cd ~/edu
cp .env.example .env
nano .env
```

Fill in these values:

```ini
# ─── Core Django ─────────────────────────────────────────────
SECRET_KEY=PASTE_A_GENERATED_KEY_HERE
DEBUG=False
ALLOWED_HOSTS=dfsscholarships.com,www.dfsscholarships.com
CSRF_TRUSTED_ORIGINS=https://dfsscholarships.com,https://www.dfsscholarships.com

# ─── Database ────────────────────────────────────────────────
DB_ENGINE=sqlite3

# ─── Email ───────────────────────────────────────────────────
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=mail.dfsscholarships.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=noreply@dfsscholarships.com
EMAIL_HOST_PASSWORD=YOUR_EMAIL_PASSWORD
DEFAULT_FROM_EMAIL=DFS Education <noreply@dfsscholarships.com>

# ─── Security ────────────────────────────────────────────────
SECURE_SSL_REDIRECT=False
```

**Generate a secret key** — run this command:
```bash
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

Save and exit (`Ctrl+X`, then `Y`, then `Enter` in nano).

---

## Step 5 — Run Migrations & Create Admin User

```bash
source /home/YOUR_USERNAME/virtualenv/edu/3.12/bin/activate
cd ~/edu

# Create/update database tables
python manage.py migrate

# Create your admin account
python manage.py createsuperuser
```

You'll be prompted for username, email, and password. This is your admin login.

> **Note:** The SQLite database file `db.sqlite3` is included in the repo with existing test data.
> Running `migrate` will apply any pending migrations. If you want a clean start,
> delete `db.sqlite3` first, then run `migrate` + `createsuperuser`.

---

## Step 6 — Collect Static Files

```bash
python manage.py collectstatic --noinput
```

This copies all CSS, JS, and images into `~/edu/staticfiles/`. You should see:
```
131 static files copied to '/home/YOUR_USERNAME/edu/staticfiles'.
```

---

## Step 7 — Create the `tmp` Folder

Passenger uses this folder to detect restarts:
```bash
mkdir -p ~/edu/tmp
```

---

## Step 8 — Set Up Static & Media File Serving

Apache needs to serve static files and user uploads directly (not through Django).

### Create symlinks:
```bash
# Static files (CSS, JS, images)
ln -s /home/YOUR_USERNAME/edu/staticfiles /home/YOUR_USERNAME/public_html/static

# Media files (user uploads like receipts, documents)
mkdir -p /home/YOUR_USERNAME/edu/media
ln -s /home/YOUR_USERNAME/edu/media /home/YOUR_USERNAME/public_html/files
```

### Copy .htaccess:
```bash
cp ~/edu/.htaccess ~/public_html/.htaccess
```

### Verify the symlinks:
```bash
ls -la ~/public_html/static
# Should show: static -> /home/YOUR_USERNAME/edu/staticfiles

ls -la ~/public_html/files
# Should show: files -> /home/YOUR_USERNAME/edu/media
```

---

## Step 9 — Set File Permissions

SQLite needs write access to the database file and its parent directory:

```bash
chmod 664 ~/edu/db.sqlite3
chmod 775 ~/edu/
mkdir -p ~/edu/media ~/edu/logs
chmod 775 ~/edu/media ~/edu/logs
```

---

## Step 10 — Enable SSL (HTTPS)

1. cPanel → **SSL/TLS** → **Let's Encrypt** (or **AutoSSL**)
2. Issue a free certificate for:
   - `dfsscholarships.com`
   - `www.dfsscholarships.com`
3. Wait a few minutes for it to activate

The `.htaccess` file already handles the HTTP → HTTPS redirect.

---

## Step 11 — Restart the Application

### From cPanel:
Go to **Setup Python App** → click the **Restart** button next to your app.

### From SSH:
```bash
touch ~/edu/tmp/restart.txt
```

---

## Step 12 — Test Everything

Open your browser and check:

| URL | What to expect |
|-----|----------------|
| `https://dfsscholarships.com` | Home page with styling |
| `https://dfsscholarships.com/admin/` | Admin login page |
| `https://dfsscholarships.com/users/register/` | Registration form |
| `https://dfsscholarships.com/static/admin/css/custom_admin.css` | CSS file (not 404) |

### Post-deployment checklist:
- [ ] Site loads with proper Bootstrap styling
- [ ] Admin panel accessible at `/admin/`
- [ ] Can log in with superuser credentials
- [ ] Can register a new student account
- [ ] Can upload files (receipts, documents)
- [ ] Static files load (no broken CSS/images)
- [ ] Set up Site Settings in admin (logo, contact info, footer)
- [ ] Create offices and assign staff

---

## Step 13 — Set Up Email (Optional)

To send real emails (password reset, notifications):

1. cPanel → **Email Accounts** → Create `noreply@dfsscholarships.com`
2. Note the password you set
3. Update `.env`:
   ```ini
   EMAIL_HOST_USER=noreply@dfsscholarships.com
   EMAIL_HOST_PASSWORD=the-password-you-set
   ```
4. Restart: `touch ~/edu/tmp/restart.txt`

---

## Step 14 — Set Up Cron Jobs (Optional)

cPanel → **Cron Jobs** — add for maintenance:

```bash
# Clear expired sessions — daily at 2 AM
0 2 * * * /home/YOUR_USERNAME/virtualenv/edu/3.12/bin/python /home/YOUR_USERNAME/edu/manage.py clearsessions
```

---

## Updating the Site Later

When you push new code to GitHub:

```bash
ssh YOUR_USERNAME@dfsscholarships.com
source /home/YOUR_USERNAME/virtualenv/edu/3.12/bin/activate
cd ~/edu

git pull origin main
python manage.py migrate
python manage.py collectstatic --noinput
touch ~/edu/tmp/restart.txt
```

---

## Switching to MySQL Later

When you're ready for production:

1. cPanel → **MySQL Databases** → Create database + user + assign ALL PRIVILEGES
2. Install the driver:
   ```bash
   pip install mysqlclient
   ```
3. Update `.env`:
   ```ini
   DB_ENGINE=mysql
   DB_NAME=username_dfsdb
   DB_USER=username_dfsuser
   DB_PASSWORD=strong-password
   DB_HOST=localhost
   DB_PORT=3306
   ```
4. Run: `python manage.py migrate`
5. Run: `python manage.py createsuperuser`
6. Restart: `touch ~/edu/tmp/restart.txt`

---

## Troubleshooting

### 500 Internal Server Error
```bash
# Check Django logs
cat ~/edu/logs/django.log

# Check Apache error log
cat ~/logs/dfsscholarships.com.error.log

# Temporarily enable debug mode to see the error
nano ~/edu/.env   # Change DEBUG=True
touch ~/edu/tmp/restart.txt
# Visit the page — full error shown
# REMEMBER to set DEBUG=False after!
```

### Static files return 404
```bash
# Verify collectstatic ran
ls ~/edu/staticfiles/

# Verify symlink
ls -la ~/public_html/static

# Recreate if broken
rm -f ~/public_html/static
ln -s /home/YOUR_USERNAME/edu/staticfiles /home/YOUR_USERNAME/public_html/static
```

### CSRF Verification Failed
- Ensure `.env` has `CSRF_TRUSTED_ORIGINS=https://dfsscholarships.com,https://www.dfsscholarships.com`
- Clear browser cookies
- Restart: `touch ~/edu/tmp/restart.txt`

### "No module named ..." Error
```bash
source /home/YOUR_USERNAME/virtualenv/edu/3.12/bin/activate
pip install -r ~/edu/requirements.txt
touch ~/edu/tmp/restart.txt
```

### Permission Denied on db.sqlite3
```bash
chmod 664 ~/edu/db.sqlite3
chmod 775 ~/edu/
```

### Media uploads not saving
```bash
mkdir -p ~/edu/media
chmod 775 ~/edu/media
```

---

## File Structure on Server

```
/home/YOUR_USERNAME/
│
├── edu/                              ← Your Django project
│   ├── .env                          ← Secret config (NEVER share)
│   ├── db.sqlite3                    ← SQLite database
│   ├── manage.py
│   ├── passenger_wsgi.py             ← Passenger entry point
│   ├── requirements.txt
│   ├── main/                         ← Django settings
│   ├── users/
│   ├── scholarships/
│   ├── finance/
│   ├── office/
│   ├── agent/
│   ├── headquarters/
│   ├── pages/
│   ├── static/                       ← Source static files
│   ├── staticfiles/                  ← Collected static (Step 6)
│   ├── media/                        ← User uploads
│   ├── logs/                         ← Django log files
│   └── tmp/
│       └── restart.txt               ← Touch to restart
│
├── public_html/
│   ├── .htaccess                     ← HTTPS + static rules
│   ├── static → ../edu/staticfiles/  ← Symlink
│   └── files  → ../edu/media/        ← Symlink
│
└── virtualenv/                       ← Created by cPanel
    └── edu/3.12/
```

---

## Quick Reference Commands

```bash
# Activate virtualenv
source /home/YOUR_USERNAME/virtualenv/edu/3.12/bin/activate

# Run migrations
python ~/edu/manage.py migrate

# Create admin user
python ~/edu/manage.py createsuperuser

# Collect static files
python ~/edu/manage.py collectstatic --noinput

# Restart app
touch ~/edu/tmp/restart.txt

# View logs
tail -50 ~/edu/logs/django.log

# Django shell
python ~/edu/manage.py shell

# Generate secret key
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```
