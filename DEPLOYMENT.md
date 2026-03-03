# Deploying Timetable Portal on PythonAnywhere

This guide walks you through deploying the Timetable Portal Django app on PythonAnywhere.

## Prerequisites

- PythonAnywhere account (free tier works)
- GitHub repo: https://github.com/dhruvpd77/timetable_portal

---

## Step 1: Create a PythonAnywhere Account

1. Go to [pythonanywhere.com](https://www.pythonanywhere.com) and sign up (free).
2. Note your username – your site will be at `https://YOURUSERNAME.pythonanywhere.com`.

---

## Step 2: Clone the Repository

1. Open a **Bash** console on PythonAnywhere (Consoles tab → New console → Bash).
2. Clone the repo:

```bash
cd ~
git clone https://github.com/dhruvpd77/timetable_portal.git
cd timetable_portal
```

---

## Step 3: Create Virtual Environment

```bash
python3.10 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

---

## Step 4: Generate Secret Key

Run this to generate a secure secret key:

```bash
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

Save the output – you'll add it in the WSGI file (Step 7).

---

## Step 5: Run Migrations & Create Superuser

```bash
cd ~/timetable_portal
source venv/bin/activate
python manage.py migrate
python manage.py createsuperuser
```

---

## Step 6: Collect Static Files

```bash
python manage.py collectstatic --noinput
```

This creates the `staticfiles/` folder. Note the full path, e.g. `/home/yourusername/timetable_portal/staticfiles`.

---

## Step 7: Configure the Web App

1. Go to the **Web** tab on PythonAnywhere.
2. Click **Add a new web app** (or use existing).
3. Choose **Manual configuration** (not Django wizard).
4. Select **Python 3.10**.
5. Click **Next**.

### Virtualenv

- In "Virtualenv", click the path and enter: `/home/yourusername/timetable_portal/venv`
- Or browse and select the `venv` folder.

### WSGI Configuration

1. Click the **WSGI configuration file** link.
2. Replace the contents with:

```python
import os
import sys

# Add your project directory to the sys.path
path = '/home/yourusername/timetable_portal'
if path not in sys.path:
    sys.path.insert(0, path)

# Set environment variables for production
os.environ['DJANGO_SETTINGS_MODULE'] = 'erp_timetable.settings'
os.environ['DJANGO_SECRET_KEY'] = 'your-secret-key-from-step-4'
os.environ['DJANGO_DEBUG'] = 'False'
os.environ['DJANGO_ALLOWED_HOSTS'] = 'yourusername.pythonanywhere.com'
os.environ['CSRF_TRUSTED_ORIGINS'] = 'https://yourusername.pythonanywhere.com'

from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()
```

**Important:** Replace `yourusername` with your PythonAnywhere username and `your-secret-key-from-step-4` with the key from Step 4.

### Static Files Mapping

In the Web tab, scroll to **Static files**:

| URL        | Directory                                      |
|------------|-------------------------------------------------|
| /static/   | /home/yourusername/timetable_portal/staticfiles |
| /media/    | /home/yourusername/timetable_portal/media       |

### Reload

Click the green **Reload** button.

---

## Step 8: Create Media Directory

```bash
mkdir -p ~/timetable_portal/media
```

---

## Step 9: Initial Setup

1. Visit `https://yourusername.pythonanywhere.com/`
2. If you have no colleges/departments, go to `/admin-setup/` (after logging in) or create them via Django admin at `/admin/`.
3. Create a college, department, and link a user to the department.

---

## Updating the App

When you push changes to GitHub:

```bash
cd ~/timetable_portal
git pull
source venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py collectstatic --noinput
```

Then reload the web app in the Web tab.

---

## Troubleshooting

### pip install fails on pycairo / rlpycairo

The project pins `svglib<1.6` to avoid pycairo compilation (which fails on PythonAnywhere). If you see pycairo build errors, ensure your `requirements.txt` has:

```
svglib>=1.2.1,<1.6
xhtml2pdf>=0.2.13
```

This keeps svglib at 1.5.x, which does not require rlpycairo/pycairo.

### Static files not loading
- Run `collectstatic` again.
- Check the Static files mapping path in the Web tab.
- Ensure the path has no trailing slash in the Directory field.

### 500 Error
- Check the **Error log** in the Web tab.
- Verify `DJANGO_SETTINGS_MODULE` and paths in the WSGI file.
- Ensure the virtualenv has all packages: `pip list`.

### CSRF / Login issues
- Add `https://yourusername.pythonanywhere.com` to `CSRF_TRUSTED_ORIGINS`.
- Ensure `DEBUG=False` in production.

### Database
- The default SQLite database is at `~/timetable_portal/db.sqlite3`.
- Back it up regularly: `cp db.sqlite3 db.sqlite3.backup`
