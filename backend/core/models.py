from django.db import models

class DatabaseBackup(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    data = models.TextField()