from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("checklists", "0002_checklist_subtask"),
    ]

    operations = [
        migrations.AlterField(
            model_name="checklist",
            name="status",
            field=models.CharField(blank=True, default="Pending", max_length=32),
        ),
        migrations.AlterField(
            model_name="subtask",
            name="status",
            field=models.CharField(blank=True, default="Pending", max_length=32),
        ),
    ]