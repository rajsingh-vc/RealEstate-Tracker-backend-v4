import io
from django.core.management.base import BaseCommand
from django.core.management import call_command
from core.models import DatabaseBackup

class Command(BaseCommand):
    def handle(self, *args, **options):
        buffer = io.StringIO()
        call_command(
            'dumpdata',
            natural_foreign=True,
            natural_primary=True,
            exclude=['contenttypes', 'auth.Permission'],
            indent=2,
            stdout=buffer
        )
        DatabaseBackup.objects.create(data=buffer.getvalue())
        self.stdout.write(self.style.SUCCESS('Backup stored in DB'))