from django.db import migrations


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("projects", "0006_alter_project_status"),
    ]

    operations = [
        migrations.CreateModel(
            name="Category",
            fields=[],
            options={
                "verbose_name": "Category",
                "verbose_name_plural": "Categories",
                "proxy": True,
                "indexes": [],
                "constraints": [],
            },
            bases=("projects.tower",),
        ),
        migrations.CreateModel(
            name="SubCategory",
            fields=[],
            options={
                "verbose_name": "Sub Category",
                "verbose_name_plural": "Sub Categories",
                "proxy": True,
                "indexes": [],
                "constraints": [],
            },
            bases=("projects.floor",),
        ),
    ]
