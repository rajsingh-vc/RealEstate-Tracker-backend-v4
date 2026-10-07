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

    html_message = f"""
    <!DOCTYPE html>
    <html>
    <head><meta charset="utf-8"></head>
    <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #f3f4f6; margin: 0; padding: 24px; color: #111827;">
      <div style="max-width: 560px; margin: 0 auto; background: #ffffff; border: 1px solid #e5e7eb; border-radius: 12px; padding: 32px; box-shadow: 0 1px 3px rgba(0,0,0,0.06);">
        <h2 style="margin-top: 0; color: #1e40af; font-size: 22px;">You're Invited!</h2>
        <p style="font-size: 15px; line-height: 1.5; color: #374151;">Hi <strong>{greeting_name}</strong>,</p>
        <p style="font-size: 15px; line-height: 1.5; color: #374151;">
          You have been invited to join <strong>{invitation.company.name}</strong> on <strong>Real Estate Tracker</strong> as {role_label}{dept_label}.
        </p>
        <div style="background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 12px 16px; margin: 20px 0;">
          <p style="margin: 0; font-size: 14px; color: #475569;">Your assigned username: <strong style="color: #0f172a;">{display_username}</strong></p>
        </div>
        <div style="text-align: center; margin: 28px 0;">
          <a href="{accept_url}" style="display: inline-block; background-color: #2563eb; color: #ffffff; text-decoration: none; padding: 12px 28px; border-radius: 8px; font-weight: 600; font-size: 15px; box-shadow: 0 2px 4px rgba(37,99,235,0.25);">
            Accept Invitation &amp; Set Password
          </a>
        </div>
        <p style="font-size: 13px; color: #64748b; line-height: 1.4;">
          Or copy and paste this link in your browser:<br>
          <a href="{accept_url}" style="color: #2563eb; word-break: break-all;">{accept_url}</a>
        </p>
        <hr style="border: none; border-top: 1px solid #e2e8f0; margin: 24px 0;" />
        <p style="font-size: 12px; color: #94a3b8; margin-bottom: 0;">
          This link will expire on {invitation.expires_at:%d %b %Y, %H:%M} UTC. If you were not expecting this invite, you can safely ignore this email.
        </p>
      </div>
    </body>
    </html>
    """

    from_email = (
        getattr(settings, "DEFAULT_FROM_EMAIL", None)
        or getattr(settings, "EMAIL_HOST_USER", None)
        or "rajbrijeshsingh1804@gmail.com"
    )
    try:
        sent = send_mail(
            subject,
            message,
            from_email,
            [invitation.email],
            html_message=html_message,
            fail_silently=False,
        )
        logger.info(f"Invitation email successfully dispatched to {invitation.email}, status={sent}")
    except Exception as e:
        logger.error(f"Failed to send invitation email to {invitation.email}: {e}")


def send_password_reset_otp_email(user, otp_code, expiry_minutes):
    greeting_name = user.name or user.username

    subject = "Your Real Estate Tracker password reset code"
    message = (
        f"Hi {greeting_name},\n\n"
        f"We received a request to reset your Real Estate Tracker password.\n\n"
        f"Your one-time verification code is: {otp_code}\n\n"
        f"This code expires in {expiry_minutes} minutes. Enter it on the "
        f"reset password page to continue.\n\n"
        f"If you didn't request this, you can safely ignore this email — "
        f"your password will not be changed."
    )
    from_email = getattr(settings, "DEFAULT_FROM_EMAIL", None) or getattr(settings, "EMAIL_HOST_USER", None)
    try:
        send_mail(subject, message, from_email, [user.email], fail_silently=False)
    except Exception as e:
        logger.error(f"Failed to send password reset OTP email to {user.email}: {e}")


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