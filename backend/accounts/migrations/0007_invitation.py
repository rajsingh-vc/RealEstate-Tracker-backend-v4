import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0006_user_phone_number'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Invitation',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('email', models.EmailField(max_length=254)),
                ('phone_number', models.CharField(blank=True, max_length=20)),
                ('token', models.CharField(editable=False, max_length=64, unique=True)),
                ('status', models.CharField(
                    choices=[('pending', 'Pending'), ('accepted', 'Accepted'),
                             ('expired', 'Expired'), ('revoked', 'Revoked')],
                    default='pending', max_length=10,
                )),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('expires_at', models.DateTimeField()),
                ('accepted_by', models.OneToOneField(
                    blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                    related_name='accepted_invitation', to=settings.AUTH_USER_MODEL,
                )),
                ('company', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE, related_name='invitations',
                    to='accounts.company',
                )),
                ('department', models.ForeignKey(
                    blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                    related_name='invitations', to='accounts.department',
                )),
                ('invited_by', models.ForeignKey(
                    blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                    related_name='invitations_sent', to=settings.AUTH_USER_MODEL,
                )),
                ('role', models.ForeignKey(
                    blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                    related_name='invitations', to='accounts.role',
                )),
            ],
            options={
                'unique_together': {('email', 'company')},
            },
        ),
    ]