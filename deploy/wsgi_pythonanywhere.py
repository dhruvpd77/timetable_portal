# PythonAnywhere WSGI configuration for Timetable Portal
# Copy this into the Web app's "WSGI configuration file" on PythonAnywhere.
# Replace YOUR_USERNAME with your PythonAnywhere username and YOUR_SECRET_KEY with a real key.

import os
import sys

# Project directory (replace YOUR_USERNAME with your PythonAnywhere username)
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
