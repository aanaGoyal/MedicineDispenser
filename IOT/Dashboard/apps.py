# Dashboard/apps.py

from django.apps import AppConfig

class DashboardConfig(AppConfig): # Change this class name
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'Dashboard' # Change this name
    
    def ready(self):
        import Dashboard.signals # Change this import path