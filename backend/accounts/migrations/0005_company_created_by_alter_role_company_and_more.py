import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def migrate_department_strings_to_fk(apps, schema_editor):
    """
    For every user with an old free-text department_old value, get_or_create
    a real Department row scoped to that user's company, and point the new
    department FK at it. Nothing here is hardcoded — every department name
    comes from whatever text was already in the database.
    """
    User = apps.get_model('accounts', 'User')
    Department = apps.get_model('accounts', 'Department')

    dept_cache = {}
    for user in User.objects.all().iterator():
        old_value = (user.department_old or '').strip()
        if not old_value or not user.company_id:
            continue
        cache_key = (user.company_id, old_value.lower())
        dept_id = dept_cache.get(cache_key)
        if dept_id is None:
            dept, _ = Department.objects.get_or_create(
                company_id=user.company_id,
                name=old_value,
            )
            dept_id = dept.id
            dept_cache[cache_key] = dept_id
        user.department_id = dept_id
        user.save(update_fields=['department'])


def noop_reverse(apps, schema_editor):
    # Not reversible without losing information about which text value
    # each department FK originally came from — intentionally a no-op.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0004_role_and_migrate_data'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Department',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
        ),
        migrations.AddField(
            model_name='company',
            name='created_by',
            field=models.ForeignKey(
                blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                related_name='companies_created', to=settings.AUTH_USER_MODEL,
                help_text="The SuperAdmin who created this organization.",
            ),
        ),
        migrations.AlterField(
            model_name='role',
            name='company',
            field=models.ForeignKey(
                blank=True, null=True, on_delete=django.db.models.deletion.CASCADE,
                related_name='roles', to='accounts.company',
                help_text="Null for global roles (e.g., SuperAdmin)",
            ),
        ),
        migrations.AddField(
            model_name='department',
            name='company',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE, related_name='departments',
                to='accounts.company', default=None,
            ),
            preserve_default=False,
        ),
        migrations.AlterUniqueTogether(
            name='department',
            unique_together={('name', 'company')},
        ),
        # Step 1: move the OLD text column aside instead of altering it in place.
        migrations.RenameField(
            model_name='user',
            old_name='department',
            new_name='department_old',
        ),
        # Step 2: add the NEW real FK column, nullable, alongside the old text column.
        migrations.AddField(
            model_name='user',
            name='department',
            field=models.ForeignKey(
                blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                related_name='users', to='accounts.department',
            ),
        ),
        # Step 3: dynamic data migration — backfills the new FK from the old text.
        migrations.RunPython(migrate_department_strings_to_fk, noop_reverse),
        # Step 4: the old text column has done its job — drop it.
        migrations.RemoveField(
            model_name='user',
            name='department_old',
        ),
    ]