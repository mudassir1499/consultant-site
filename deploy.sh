#!/bin/bash
# ============================================================
# DFS Education — cPanel Deployment Helper Script
# ============================================================
# Run this script via SSH after uploading files to ~/edu/
#
# Usage:
#   cd ~/edu
#   bash deploy.sh [first|update]
#
#   first  — Full first-time setup (migrations, superuser, etc.)
#   update — Quick update (migrate + collectstatic + restart)
# ============================================================

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

APP_DIR="$(cd "$(dirname "$0")" && pwd)"
USERNAME=$(whoami)

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN} DFS Education — Deployment Script${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

# ─── Detect virtualenv ───────────────────────────────────────
VENV_DIR="/home/${USERNAME}/virtualenv/edu"
if [ -d "$VENV_DIR" ]; then
    # Find highest Python version
    PYTHON_VER=$(ls "$VENV_DIR" | sort -V | tail -1)
    VENV_ACTIVATE="${VENV_DIR}/${PYTHON_VER}/bin/activate"
    if [ -f "$VENV_ACTIVATE" ]; then
        echo -e "${GREEN}✓${NC} Activating virtualenv: ${PYTHON_VER}"
        source "$VENV_ACTIVATE"
    else
        echo -e "${RED}✗ Virtualenv activate script not found at ${VENV_ACTIVATE}${NC}"
        echo "  Make sure you created the Python App in cPanel first."
        exit 1
    fi
else
    echo -e "${YELLOW}⚠ No cPanel virtualenv found. Using current Python.${NC}"
fi

cd "$APP_DIR"
echo -e "${GREEN}✓${NC} Working directory: $(pwd)"
echo ""

# ─── Check .env exists ──────────────────────────────────────
if [ ! -f ".env" ]; then
    echo -e "${YELLOW}⚠ No .env file found. Creating from .env.example...${NC}"
    if [ -f ".env.example" ]; then
        cp .env.example .env
        echo -e "${RED}  IMPORTANT: Edit .env and set your SECRET_KEY and other values!${NC}"
        echo "  Run: nano ~/edu/.env"
        echo ""

        # Generate a secret key automatically
        SECRET=$(python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())" 2>/dev/null || echo "")
        if [ -n "$SECRET" ]; then
            sed -i "s|your-secret-key-here|${SECRET}|g" .env
            echo -e "${GREEN}✓${NC} Generated and set SECRET_KEY automatically"
        fi
    else
        echo -e "${RED}✗ No .env.example either. Cannot continue.${NC}"
        exit 1
    fi
fi

# ─── Function: Full first-time deploy ────────────────────────
first_deploy() {
    echo -e "${GREEN}── First-Time Deployment ──${NC}"
    echo ""

    # Install dependencies
    echo -e "${YELLOW}Installing dependencies...${NC}"
    pip install --upgrade pip --quiet
    pip install -r requirements.txt --quiet
    echo -e "${GREEN}✓${NC} Dependencies installed"

    # Create required directories
    mkdir -p tmp logs media
    echo -e "${GREEN}✓${NC} Created tmp/, logs/, media/ directories"

    # Run migrations
    echo -e "${YELLOW}Running migrations...${NC}"
    python manage.py migrate --noinput
    echo -e "${GREEN}✓${NC} Migrations applied"

    # Configure Site domain for sitemap
    python manage.py shell -c "
from django.contrib.sites.models import Site
site, _ = Site.objects.get_or_create(id=1)
if site.domain != 'dfsscholarships.com':
    site.domain = 'dfsscholarships.com'
    site.name = 'DFS Education'
    site.save()
    print('Site domain set to: dfsscholarships.com')
else:
    print('Site domain already correct: dfsscholarships.com')
" 2>/dev/null
    echo -e "${GREEN}✓${NC} Site domain configured"

    # Collect static files
    echo -e "${YELLOW}Collecting static files...${NC}"
    python manage.py collectstatic --noinput --clear 2>/dev/null
    echo -e "${GREEN}✓${NC} Static files collected to staticfiles/"

    # Set permissions
    chmod 664 db.sqlite3 2>/dev/null || true
    chmod 775 . media logs 2>/dev/null || true
    echo -e "${GREEN}✓${NC} File permissions set"

    # Create symlinks
    PUBLIC_HTML="/home/${USERNAME}/public_html"
    if [ -d "$PUBLIC_HTML" ]; then
        # Static files symlink
        if [ ! -L "${PUBLIC_HTML}/static" ]; then
            ln -sf "${APP_DIR}/staticfiles" "${PUBLIC_HTML}/static"
            echo -e "${GREEN}✓${NC} Created static symlink: public_html/static → staticfiles/"
        else
            echo -e "${GREEN}✓${NC} Static symlink already exists"
        fi

        # Media files symlink
        if [ ! -L "${PUBLIC_HTML}/files" ]; then
            ln -sf "${APP_DIR}/media" "${PUBLIC_HTML}/files"
            echo -e "${GREEN}✓${NC} Created media symlink: public_html/files → media/"
        else
            echo -e "${GREEN}✓${NC} Media symlink already exists"
        fi

        # Copy .htaccess
        if [ -f ".htaccess" ]; then
            cp .htaccess "${PUBLIC_HTML}/.htaccess"
            echo -e "${GREEN}✓${NC} Copied .htaccess to public_html/"
        fi
    else
        echo -e "${YELLOW}⚠ public_html not found. Create symlinks manually (see DEPLOYMENT.md Step 8)${NC}"
    fi

    # Restart app
    touch tmp/restart.txt
    echo -e "${GREEN}✓${NC} Application restarted"

    echo ""
    echo -e "${GREEN}========================================${NC}"
    echo -e "${GREEN} First-time deployment complete!${NC}"
    echo -e "${GREEN}========================================${NC}"
    echo ""
    echo "Next steps:"
    echo "  1. Edit .env if you haven't:  nano ~/edu/.env"
    echo "  2. Create admin user:         python manage.py createsuperuser"
    echo "  3. Visit: https://dfsscholarships.com"
    echo "  4. Check: https://dfsscholarships.com/robots.txt"
    echo "  5. Check: https://dfsscholarships.com/sitemap.xml"
    echo ""
}

# ─── Function: Quick update deploy ───────────────────────────
update_deploy() {
    echo -e "${GREEN}── Update Deployment ──${NC}"
    echo ""

    # Install any new dependencies
    echo -e "${YELLOW}Installing dependencies...${NC}"
    pip install -r requirements.txt --quiet
    echo -e "${GREEN}✓${NC} Dependencies up to date"

    # Run migrations
    echo -e "${YELLOW}Running migrations...${NC}"
    python manage.py migrate --noinput
    echo -e "${GREEN}✓${NC} Migrations applied"

    # Collect static files
    echo -e "${YELLOW}Collecting static files...${NC}"
    python manage.py collectstatic --noinput 2>/dev/null
    echo -e "${GREEN}✓${NC} Static files collected"

    # Restart
    mkdir -p tmp
    touch tmp/restart.txt
    echo -e "${GREEN}✓${NC} Application restarted"

    echo ""
    echo -e "${GREEN}========================================${NC}"
    echo -e "${GREEN} Update complete!${NC}"
    echo -e "${GREEN}========================================${NC}"
    echo ""
    echo "Visit: https://dfsscholarships.com"
    echo ""
}

# ─── Main ────────────────────────────────────────────────────
case "${1:-}" in
    first)
        first_deploy
        ;;
    update)
        update_deploy
        ;;
    *)
        echo "Usage: bash deploy.sh [first|update]"
        echo ""
        echo "  first  — Full first-time setup (install deps, migrate, symlinks, etc.)"
        echo "  update — Quick update after uploading new code"
        echo ""
        # Default to update if files already exist
        if [ -f "db.sqlite3" ] && [ -d "staticfiles" ]; then
            echo -e "${YELLOW}Detected existing deployment. Running update...${NC}"
            echo ""
            update_deploy
        else
            echo -e "${YELLOW}No existing deployment detected. Running first-time setup...${NC}"
            echo ""
            first_deploy
        fi
        ;;
esac
