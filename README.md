# Timetable Portal

A Django-based web application for managing college timetables, faculty assignments, and generating reports.

## Features

- **Timetable Generation**: Auto-generate timetables with 2-hour pair slots
- **Faculty Management**: Manage faculty, blocks, preferred slots, and course assignments
- **Room & Lab Management**: Track room and lab availability with blocking
- **Reports**: Faculty timetable, batch timetable, analytics, and combined reports
- **Excel Support**: Upload timetables via Excel, export reports to PDF/Excel

## Setup

1. Create and activate a virtual environment:
   ```bash
   python -m venv venv
   venv\Scripts\activate   # Windows
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Run migrations:
   ```bash
   python manage.py migrate
   ```

4. Create a superuser:
   ```bash
   python manage.py createsuperuser
   ```

5. Run the development server:
   ```bash
   python manage.py runserver
   ```

6. Visit http://127.0.0.1:8000/

## Project Structure

- `core/` - Main app (models, views, timetable solver)
- `reports/` - Report generation and analytics
- `erp_timetable/` - Django project settings

## Deployment

See **[DEPLOYMENT.md](DEPLOYMENT.md)** for step-by-step instructions to deploy on PythonAnywhere.

## Configuration

- `ALLOWED_HOSTS` in `settings.py` - Add your server IP if deploying
- Default database: SQLite (change in settings for production)
- For production: set `DJANGO_SECRET_KEY`, `DJANGO_DEBUG=False`, `CSRF_TRUSTED_ORIGINS` via environment variables
