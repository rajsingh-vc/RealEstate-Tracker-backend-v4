from django.conf import settings
from django.db import models


class Notification(models.Model):
    """
    In-app notification shown in the bell icon. Currently created in two
    ways:

    1. Explicitly — e.g. AcceptInvitationView creates one the moment an
       invited user accepts, notifying whoever sent the invite (and every
       SuperAdmin).
    2. Automatically — ActivityNotificationMiddleware (see middleware.py)
       creates one for every SuperAdmin whenever any authenticated,
       non-superadmin user successfully performs a create/update/delete
       action anywhere in the API, so SuperAdmins get a feed of "whatever
       the user performs on the website" without every view having to know
       about notifications.
    """
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='notifications'
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='notifications_caused'
    )
    verb = models.CharField(max_length=255)
    description = models.CharField(max_length=500, blank=True, default='')
    # Frontend route the notification should deep-link to when clicked,
    # e.g. "/tasks?taskId=14". Optional — left blank when there's nothing
    # sensible to link to.
    target_url = models.CharField(max_length=255, blank=True, default='')
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['recipient', 'is_read']),
        ]

    def __str__(self):
        return f"{self.recipient}: {self.verb}"
