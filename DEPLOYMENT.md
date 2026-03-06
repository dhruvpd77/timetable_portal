# Deploy Timetable Portal on PythonAnywhere

Step-by-step guide to deploy the Timetable Portal Django app on PythonAnywhere.

**Repo:** https://github.com/dhruvpd77/timetable_portal  
**Your site will be:** `https://YOUR_USERNAME.pythonanywhere.com`

---

## 1. Create a PythonAnywhere account

1. Go to [pythonanywhere.com](https://www.pythonanywhere.com) and sign up (free tier is enough).
2. Note your **username** — you will use it in paths and the WSGI file.

---

## 2. Connect to GitHub and get the code

Open a **Bash** console (Consoles → New console → Bash), then run:

```bash
cd ~
git clone https://github.com/dhruvpd77/timetable_portal.git
cd timetable_portal
```

If the repo is **private**, use a Personal Access Token:

```bash
git clone https://YOUR_GITHUB_USERNAME:YOUR_TOKEN@github.com/dhruvpd77/timetable_portal.git
```

---

## 3. Create and use a virtual environment

**Option A – Virtualenv inside the project (recommended):**

```bash
cd ~/timetable_portal
python3.10 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

**Option B – Use an existing virtualenv (e.g. `myenv`):**

```bash
cd ~/timetable_portal
source ~/.virtualenvs/myenv/bin/activate
pip install -r requirements.txt
```

Note the virtualenv path for the Web tab later:
- Option A: `/home/YOUR_USERNAME/timetable_portal/venv`
- Option B: `/home/YOUR_USERNAME/.virtualenvs/myenv`

---

## 4. Generate a Django secret key

```bash
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

Copy the output; you will paste it into the WSGI file.

---

## 5. Database and superuser

```bash
cd ~/timetable_portal
source venv/bin/activate   # or: source ~/.virtualenvs/myenv/bin/activate
python manage.py migrate
python manage.py createsuperuser
```

Enter username, email, and password when asked.

---

## 6. Static and media files

```bash
python manage.py collectstatic --noinput
mkdir -p media
```

If you get **Disk quota exceeded**, skip `collectstatic` for now; the app can still run. You can run it again after freeing space or upgrading.

---

## 7. Configure the Web app on PythonAnywhere

1. Open the **Web** tab.
2. Click **Add a new web app** (or use an existing one).
3. Choose **Manual configuration** (not the Django wizard).
4. Select **Python 3.10** and finish.

### 7.1 Virtualenv

- In the **Virtualenv** section, enter the path you noted in step 3, e.g.  
  `/home/YOUR_USERNAME/timetable_portal/venv`  
  or  
  `/home/YOUR_USERNAME/.virtualenvs/myenv`

### 7.2 WSGI file

1. Click the **WSGI configuration file** link.
2. **Replace the entire file** with the contents of `deploy/wsgi_pythonanywhere.py`, then replace:
   - `YOUR_USERNAME` → your PythonAnywhere username (in all 4 places)
   - `YOUR_SECRET_KEY` → the secret key from step 4

Or paste this and edit the same placeholders:

```python
import os
import sys

path = '/home/YOUR_USERNAME/timetable_portal'
if path not in sys.path:
    sys.path.insert(0, path)

os.environ['DJANGO_SETTINGS_MODULE'] = 'erp_timetable.settings'
os.environ['DJANGO_SECRET_KEY'] = 'YOUR_SECRET_KEY'
os.environ['DJANGO_DEBUG'] = 'False'
os.environ['DJANGO_ALLOWED_HOSTS'] = 'YOUR_USERNAME.pythonanywhere.com'
os.environ['CSRF_TRUSTED_ORIGINS'] = 'https://YOUR_USERNAME.pythonanywhere.com'

from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()
```

Save the file.

### 7.3 Static files (Web tab)

In **Static files**, add:

| URL       | Directory |
|----------|-----------|
| /static/ | /home/YOUR_USERNAME/timetable_portal/staticfiles |
| /media/  | /home/YOUR_USERNAME/timetable_portal/media       |

Use your real username; no trailing slash in the Directory field.

### 7.4 Reload

Click the green **Reload** button for your web app.

---

## 8. First use

1. Open `https://YOUR_USERNAME.pythonanywhere.com/`
2. Log in with the superuser account you created.
3. If needed, go to `/admin-setup/` or Django admin to create a college and department and link your user.

---

## Updating after code changes on GitHub

```bash
cd ~/timetable_portal
git pull origin master
source venv/bin/activate   # or: source ~/.virtualenvs/myenv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py collectstatic --noinput   # skip if disk quota error
```

Then click **Reload** in the Web tab.

---

## Troubleshooting

### ortools / Disk quota exceeded

The app works **without** ortools: reports, faculty, settings, etc. Only **Generate Timetable** needs ortools. If `pip install ortools` fails with disk quota:

- Free space: `pip cache purge`, remove old virtualenvs.
- Or run without ortools and use the rest of the app; timetable generation will show an error with instructions.

### Static files not loading

- Run `collectstatic` again.
- In the Web tab, check Static files URL and Directory (no trailing slash).

### 500 error

- Open the **Error log** in the Web tab.
- Check that the WSGI path and `YOUR_USERNAME` / `YOUR_SECRET_KEY` are correct.
- Confirm packages: `pip list` (with virtualenv active).

### CSRF / login issues

- In WSGI, `CSRF_TRUSTED_ORIGINS` must be `https://YOUR_USERNAME.pythonanywhere.com`.
- With `DEBUG=False`, ensure the secret key and allowed hosts are set in WSGI.

### Database

- SQLite file: `~/timetable_portal/db.sqlite3`
- Back up: `cp db.sqlite3 db.sqlite3.backup`

### svglib / pycairo

The project pins `svglib==1.5.1` so you don’t need pycairo. If you see pycairo errors, ensure `requirements.txt` has `svglib==1.5.1` and reinstall.
