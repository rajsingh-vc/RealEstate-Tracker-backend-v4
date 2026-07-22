import logging
from django.conf import settings
from django.core.mail import send_mail
from django.utils.module_loading import import_string

logger = logging.getLogger(__name__)


def send_invitation_email(invitation, accept_url):
    role_label = invitation.role.name if invitation.role else "a team member"
    dept_label = f" in the {invitation.department.name} department" if invitation.department else ""
    greeting_name = invitation.name or invitation.username or invitation.email.split("@")[0]
    display_username = invitation.username or invitation.email.split("@")[0]

    subject = f"You're invited to join {invitation.company.name} on Real Estate Tracker"
    message = (
        f"Hi {greeting_name},\n\n"
        f"You've been invited to join {invitation.company.name} on Real Estate Tracker "
        f"as {role_label}{dept_label}.\n\n"
        f"Your username will be: {display_username}\n\n"
        f"Click the link below to accept the invitation and set up your password:\n"
        f"{accept_url}\n\n"
        f"This link expires on {invitation.expires_at:%d %b %Y, %H:%M} UTC, so please accept it soon.\n\n"
        f"If you weren't expecting this invite, you can safely ignore this email."
    )
    from_email = getattr(settings, "DEFAULT_FROM_EMAIL", None) or getattr(settings, "EMAIL_HOST_USER", None)
    try:
        send_mail(subject, message, from_email, [invitation.email], fail_silently=False)
    except Exception as e:
        logger.error(f"Failed to send invitation email to {invitation.email}: {e}")


def send_invitation_sms(invitation, accept_url):
    backend_path = getattr(settings, "SMS_BACKEND", None)
    if not backend_path or not invitation.phone_number:
        logger.info(
            "Skipping invitation SMS for %s (SMS_BACKEND not configured or no phone number on file).",
            invitation.email,
        )
        return
    try:
        send_fn = import_string(backend_path)
        send_fn(invitation.phone_number, f"You're invited to join {invitation.company.name}: {accept_url}")
    except Exception as e:
        logger.exception(f"Failed to send invitation SMS to {invitation.phone_number}: {e}")