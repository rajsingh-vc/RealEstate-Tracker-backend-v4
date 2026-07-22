# accounts/migrations/0004_role_and_migrate_data.py

from django.db import migrations, models
import django.db.models.deletion

def create_roles_and_migrate(apps, schema_editor):
    Role = apps.get_model('accounts', 'Role')
    User = apps.get_model('accounts', 'User')
    Permission = apps.get_model('auth', 'Permission')
    ContentType = apps.get_model('contenttypes', 'ContentType')

    # Get content type for User
    user_ct = ContentType.objects.get_for_model(User)

    # Create custom permission
    can_manage_users, _ = Permission.objects.get_or_create(
        codename='can_manage_users',
        name='Can manage users',
        content_type=user_ct,
    )

    # Create roles (global, company=None)
    role_mapping = {}
    for role_name in ['SuperAdmin', 'Admin', 'CEO', 'Project Director', 'HOD', 'Site Engineer', 'Vendor']:
        role, _ = Role.objects.get_or_create(name=role_name, company=None)
        role_mapping[role_name] = role

    # Assign permissions
    superadmin_role = role_mapping['SuperAdmin']
    superadmin_role.permissions.set(Permission.objects.all())

    for name in ['Admin', 'CEO', 'Project Director']:
        role = role_mapping[name]
        role.permissions.add(can_manage_users)

    # Migrate each user
    for user in User.objects.all():
        old_role = user.role_old  # the old CharField
        if old_role in role_mapping:
            user.role = role_mapping[old_role]
            user.save(update_fields=['role'])

def reverse_migrate(apps, schema_editor):
    # No reverse needed – keep roles as they are
    pass

class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0003_user_name'),   # ✅ correct dependency
    ]

    operations = [
        # 1. Rename old CharField to role_old
        migrations.RenameField(
            model_name='user',
            old_name='role',
            new_name='role_old',
        ),

        # 2. Create the Role model
        migrations.CreateModel(
            name='Role',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=50, unique=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('company', models.ForeignKey(
                    blank=True,
                    help_text='Null for global roles (e.g., SuperAdmin)',
                    null=True,
                    on_delete=django.db.models.deletion.CASCADE,
                    to='accounts.company'
                )),
                ('permissions', models.ManyToManyField(blank=True, to='auth.permission')),
            ],
        ),

        # 3. Add new ForeignKey (nullable)
        migrations.AddField(
            model_name='user',
            name='role',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                to='accounts.Role',
            ),
        ),

        # 4. Data migration – populate roles & assign
        migrations.RunPython(create_roles_and_migrate, reverse_migrate),

        # 5. Drop the temporary old column
        migrations.RemoveField(
            model_name='user',
            name='role_old',
        ),
    ]