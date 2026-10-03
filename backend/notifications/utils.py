"""
Small helpers for creating Notifications, used both by explicit call sites
(e.g. AcceptInvitationView) and by ActivityNotificationMiddleware.
"""
from django.contrib.auth import get_user_model


def notify(recipient, verb, actor=None, description="", target_url=""):
    """Create a single notification. No-op if there's no recipient, or the
    recipient would just be notifying themselves about their own action."""
    from .models import Notification

    if recipient is None:
        return None
    if actor is not None and getattr(actor, "pk", None) == recipient.pk:
        return None

    return Notification.objects.create(
        recipient=recipient,
        actor=actor,
        verb=verb,
        description=description,
        target_url=target_url,
    )


def notify_superadmins(verb, actor=None, description="", target_url="", exclude=None):
    """Notify every SuperAdmin (is_superuser=True). `exclude` is typically
    the actor themself, when the actor may also be a superadmin, so they
    don't get notified about their own action."""
    User = get_user_model()
    qs = User.objects.filter(is_superuser=True)
    if exclude is not None:
        qs = qs.exclude(pk=exclude.pk)
    for superadmin in qs:
        notify(superadmin, verb, actor=actor, description=description, target_url=target_url)
