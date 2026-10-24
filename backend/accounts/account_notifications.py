import os
import logging
from email.mime.image import MIMEImage
from django.conf import settings
from django.core.mail import EmailMultiAlternatives, send_mail
from django.utils import timezone
from django.utils.module_loading import import_string

logger = logging.getLogger(__name__)


def _resolve_invitation_context(invitation):
    """
    Dynamically extracts all organization, corporate hierarchy, project, and
    invitee metadata from the database without any hardcoded details.
    """
    org = getattr(invitation, "company", None)
    org_name = org.name if org else "Konstruct Tracker"

    # 1. Resolve child Company (OrganizationCompany)
    child_companies = list(org.companies.all()) if org else []
    child_company_name = child_companies[0].company_name if child_companies else ""

    # 2. Resolve child Entity
    child_entities = list(org.entities.all()) if org else []
    child_entity_name = child_entities[0].entity_name if child_entities else ""

    # 3. Resolve Project
    projects = []
    if invitation.invited_by:
        try:
            inviter_projects = list(invitation.invited_by.assigned_projects.filter(organization=org))
            if inviter_projects:
                projects = inviter_projects
        except Exception:
            pass

    if not projects and org:
        try:
            projects = list(org.projects.all())
        except Exception:
            pass

    primary_project = projects[0] if projects else None

    # If the project is linked to a specific child company/entity, prioritize that
    if primary_project:
        if getattr(primary_project, "company", None) and primary_project.company.company_name:
            child_company_name = primary_project.company.company_name
        if getattr(primary_project, "entity", None) and primary_project.entity.entity_name:
            child_entity_name = primary_project.entity.entity_name

    if projects:
        if len(projects) == 1:
            project_display = projects[0].name
        else:
            project_display = ", ".join([p.name for p in projects[:2]])
            if len(projects) > 2:
                project_display += f" (+{len(projects) - 2} more)"
    else:
        project_display = "All Organization Projects"

    role_label = invitation.role.name if invitation.role else "Team Member"
    department_label = invitation.department.name if invitation.department else "Operations"
    greeting_name = invitation.name or invitation.username or invitation.email.split("@")[0]
    display_username = invitation.username or invitation.email.split("@")[0]

    # Expiry calculations
    expires_at = invitation.expires_at
    if expires_at:
        expiry_formatted = expires_at.strftime("%A, %d %B %Y at %I:%M %p UTC")
        days_left = max(1, (expires_at - timezone.now()).days)
        expiry_relative = f"Expires in {days_left} day{'s' if days_left != 1 else ''}"
    else:
        expiry_formatted = "within 7 days"
        expiry_relative = "Time-sensitive"

    # Logo resolution & reading
    logo_bytes = None
    logo_mime_subtype = "png"
    logo_filename = "logo.png"
    has_logo = False

    if org and org.logo:
        try:
            if hasattr(org.logo, "path") and os.path.exists(org.logo.path):
                with open(org.logo.path, "rb") as f:
                    logo_bytes = f.read()
            elif hasattr(org.logo, "read"):
                logo_bytes = org.logo.read()

            if logo_bytes:
                has_logo = True
                ext = os.path.splitext(org.logo.name)[1].lower().replace(".", "")
                if ext in ("jpg", "jpeg"):
                    logo_mime_subtype = "jpeg"
                    logo_filename = "logo.jpg"
                elif ext == "png":
                    logo_mime_subtype = "png"
                    logo_filename = "logo.png"
                elif ext == "gif":
                    logo_mime_subtype = "gif"
                    logo_filename = "logo.gif"
                elif ext == "webp":
                    logo_mime_subtype = "webp"
                    logo_filename = "logo.webp"
        except Exception as e:
            logger.warning(f"Could not read organization logo for invitation email: {e}")
            has_logo = False

    # Initials for monogram fallback
    words = [w for w in org_name.split() if w]
    if len(words) >= 2:
        org_initials = (words[0][0] + words[1][0]).upper()
    elif words:
        org_initials = words[0][:2].upper()
    else:
        org_initials = "KT"

    org_address = org.address.strip() if org and org.address else ""

    return {
        "org": org,
        "org_name": org_name,
        "org_initials": org_initials,
        "org_address": org_address,
        "child_company_name": child_company_name,
        "child_entity_name": child_entity_name,
        "project_display": project_display,
        "role_label": role_label,
        "department_label": department_label,
        "greeting_name": greeting_name,
        "display_username": display_username,
        "expiry_formatted": expiry_formatted,
        "expiry_relative": expiry_relative,
        "has_logo": has_logo,
        "logo_bytes": logo_bytes,
        "logo_mime_subtype": logo_mime_subtype,
        "logo_filename": logo_filename,
    }


def send_invitation_email(invitation, accept_url):
    """
    Dispatches a responsive, organization-branded HTML & plain-text invitation
    email with dynamic logo, corporate hierarchy, project, role, and security details.
    Compatible across Gmail, Outlook (MSO), Apple Mail, and mobile screens.
    """
    ctx = _resolve_invitation_context(invitation)

    org_name = ctx["org_name"]
    greeting_name = ctx["greeting_name"]
    display_username = ctx["display_username"]
    role_label = ctx["role_label"]
    department_label = ctx["department_label"]
    project_display = ctx["project_display"]
    child_company_name = ctx["child_company_name"]
    child_entity_name = ctx["child_entity_name"]
    expiry_formatted = ctx["expiry_formatted"]
    expiry_relative = ctx["expiry_relative"]
    org_initials = ctx["org_initials"]
    org_address = ctx["org_address"]
    has_logo = ctx["has_logo"]

    subject = f"You're invited to join {org_name} on Konstruct Tracker"

    # Optional corporate hierarchy rows
    company_row_html = ""
    if child_company_name:
        company_row_html = f"""
        <tr>
          <td width="36%" valign="top" style="padding: 9px 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; font-size: 13px; color: #64748B; font-weight: 500;">
            Company
          </td>
          <td width="64%" valign="top" style="padding: 9px 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; font-size: 13px; font-weight: 600; color: #1E293B;">
            {child_company_name}
          </td>
        </tr>
        """

    entity_row_html = ""
    if child_entity_name:
        entity_row_html = f"""
        <tr>
          <td width="36%" valign="top" style="padding: 9px 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; font-size: 13px; color: #64748B; font-weight: 500;">
            Entity
          </td>
          <td width="64%" valign="top" style="padding: 9px 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; font-size: 13px; font-weight: 600; color: #1E293B;">
            {child_entity_name}
          </td>
        </tr>
        """

    # Logo vs Monogram Header Element
    if has_logo:
        logo_header_html = f"""
        <img src="cid:org_logo" alt="{org_name}" width="160" style="display: block; max-width: 180px; max-height: 48px; width: auto; height: auto; border: 0; outline: none; text-decoration: none;" />
        """
    else:
        logo_header_html = f"""
        <table role="presentation" cellpadding="0" cellspacing="0" border="0">
          <tr>
            <td align="center" valign="middle" style="width: 42px; height: 42px; border-radius: 8px; background-color: #2563EB; color: #FFFFFF; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; font-size: 17px; font-weight: 700; text-align: center; letter-spacing: 0.5px;">
              {org_initials}
            </td>
            <td style="padding-left: 12px; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; font-size: 17px; font-weight: 700; color: #0F172A; letter-spacing: -0.2px;">
              {org_name}
            </td>
          </tr>
        </table>
        """

    address_footer_html = f"<p style='margin: 4px 0 0 0;'>{org_address}</p>" if org_address else ""

    # --------------------------------------------------------------------------
    # Plain text version
    # --------------------------------------------------------------------------
    plain_company = f"• Company:          {child_company_name}\n" if child_company_name else ""
    plain_entity = f"• Entity:           {child_entity_name}\n" if child_entity_name else ""

    message = (
        f"================================================================================\n"
        f"KONSTRUCT TRACKER — INVITATION TO JOIN {org_name.upper()}\n"
        f"================================================================================\n\n"
        f"Hi {greeting_name},\n\n"
        f"You have been invited to join {org_name} on Konstruct Tracker (Real Estate & Construction Task Management).\n\n"
        f"MEMBERSHIP & ACCESS DETAILS:\n"
        f"--------------------------------------------------------------------------------\n"
        f"• Organization:     {org_name}\n"
        f"{plain_company}"
        f"{plain_entity}"
        f"• Assigned Project: {project_display}\n"
        f"• Assigned Role:    {role_label}\n"
        f"• Department:       {department_label}\n"
        f"• Assigned Username:{display_username}\n"
        f"• Target Email:     {invitation.email}\n\n"
        f"ACCEPT INVITATION & SET PASSWORD:\n"
        f"--------------------------------------------------------------------------------\n"
        f"Click the link below or copy-paste it into your browser to activate your account:\n"
        f"{accept_url}\n\n"
        f"SECURITY NOTICE:\n"
        f"--------------------------------------------------------------------------------\n"
        f"This link is unique and expires on {expiry_formatted} ({expiry_relative}).\n"
        f"If you were not expecting this invitation, you can safely disregard this email.\n\n"
        f"--\n"
        f"{org_name} · Konstruct Tracker\n"
    )

    # --------------------------------------------------------------------------
    # Responsive, Organization-Branded HTML Email
    # --------------------------------------------------------------------------
    html_message = f"""<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
<html xmlns="http://www.w3.org/1999/xhtml" lang="en">
<head>
  <meta http-equiv="Content-Type" content="text/html; charset=utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <meta name="color-scheme" content="light dark" />
  <meta name="supported-color-schemes" content="light dark" />
  <title>Invitation to Join {org_name}</title>
  <!--[if mso]>
  <style type="text/css">
    body, table, td, h1, h2, h3, p, a {{ font-family: Arial, sans-serif !important; }}
    table {{ border-collapse: collapse; }}
  </style>
  <![endif]-->
  <style type="text/css">
    /* Reset & Base Styles */
    body {{
      margin: 0 !important;
      padding: 0 !important;
      -webkit-text-size-adjust: 100% !important;
      -ms-text-size-adjust: 100% !important;
      background-color: #F1F5F9;
    }}
    table {{
      border-spacing: 0;
      mso-table-lspace: 0pt;
      mso-table-rspace: 0pt;
    }}
    img {{
      border: 0;
      height: auto;
      line-height: 100%;
      outline: none;
      text-decoration: none;
      -ms-interpolation-mode: bicubic;
    }}
    a {{
      text-decoration: none;
    }}
    /* Mobile Responsive */
    @media only screen and (max-width: 620px) {{
      .wrapper-table {{
        width: 100% !important;
      }}
      .mobile-padding {{
        padding-left: 20px !important;
        padding-right: 20px !important;
      }}
      .mobile-header-padding {{
        padding: 18px 20px !important;
      }}
      .mobile-button {{
        width: 100% !important;
        display: block !important;
        padding-left: 12px !important;
        padding-right: 12px !important;
        box-sizing: border-box !important;
      }}
    }}
  </style>
</head>
<body style="margin: 0; padding: 0; background-color: #F1F5F9; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; -webkit-font-smoothing: antialiased;">

  <!-- Outer Background Container -->
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="background-color: #F1F5F9; width: 100%; min-width: 100%;">
    <tr>
      <td align="center" style="padding: 36px 12px;">

        <!--[if mso]>
        <table role="presentation" width="600" align="center" style="width:600px;">
        <tr>
        <td>
        <![endif]-->

        <!-- Main Card (600px max width) -->
        <table role="presentation" class="wrapper-table" width="100%" cellpadding="0" cellspacing="0" border="0" style="max-width: 600px; width: 100%; background-color: #FFFFFF; border-radius: 14px; overflow: hidden; border: 1px solid #E2E8F0; box-shadow: 0 4px 16px rgba(15, 23, 42, 0.06);">
          
          <!-- Top Accent Banner -->
          <tr>
            <td height="5" style="background: #2563EB; font-size: 0px; line-height: 0px;">&nbsp;</td>
          </tr>

          <!-- 1. Organization Header Bar -->
          <tr>
            <td class="mobile-header-padding" style="padding: 24px 32px; background-color: #FFFFFF; border-bottom: 1px solid #F1F5F9;">
              <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">
                <tr>
                  <td align="left" valign="middle">
                    {logo_header_html}
                  </td>
                  <td align="right" valign="middle">
                    <span style="display: inline-block; padding: 5px 12px; background-color: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 9999px; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; font-size: 11px; font-weight: 700; color: #475569; letter-spacing: 0.6px; text-transform: uppercase;">
                      Konstruct Tracker
                    </span>
                  </td>
                </tr>
              </table>
            </td>
          </tr>

          <!-- 2. Hero Greeting Section -->
          <tr>
            <td class="mobile-padding" style="padding: 32px 32px 20px 32px; background-color: #FFFFFF;">
              <h1 style="margin: 0 0 14px 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; font-size: 23px; font-weight: 700; color: #0F172A; line-height: 1.3; letter-spacing: -0.3px;">
                You're invited to join {org_name}
              </h1>
              <p style="margin: 0 0 8px 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; font-size: 15px; color: #334155; line-height: 1.6;">
                Hi <strong>{greeting_name}</strong>,
              </p>
              <p style="margin: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; font-size: 15px; color: #475569; line-height: 1.6;">
                You have been invited to join the project workspace for <strong>{org_name}</strong> on <strong>Konstruct Tracker</strong>. Your account has been provisioned with the following role and project credentials:
              </p>
            </td>
          </tr>

          <!-- 3. Dynamic Assignment & Access Table -->
          <tr>
            <td class="mobile-padding" style="padding: 0 32px 24px 32px;">
              <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="background-color: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 10px; overflow: hidden;">
                <tr>
                  <td style="padding: 14px 20px; background-color: #F1F5F9; border-bottom: 1px solid #E2E8F0;">
                    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">
                      <tr>
                        <td align="left" style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; font-size: 11px; font-weight: 700; color: #475569; text-transform: uppercase; letter-spacing: 0.8px;">
                          Membership &amp; Workspace Access
                        </td>
                      </tr>
                    </table>
                  </td>
                </tr>
                <tr>
                  <td style="padding: 12px 20px;">
                    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">
                      <!-- Organization -->
                      <tr>
                        <td width="36%" valign="top" style="padding: 9px 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; font-size: 13px; color: #64748B; font-weight: 500;">
                          Organization
                        </td>
                        <td width="64%" valign="top" style="padding: 9px 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; font-size: 14px; font-weight: 700; color: #0F172A;">
                          {org_name}
                        </td>
                      </tr>
                      {company_row_html}
                      {entity_row_html}
                      <!-- Project -->
                      <tr>
                        <td width="36%" valign="top" style="padding: 9px 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; font-size: 13px; color: #64748B; font-weight: 500;">
                          Assigned Project
                        </td>
                        <td width="64%" valign="top" style="padding: 9px 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; font-size: 13px; font-weight: 600; color: #1E293B;">
                          {project_display}
                        </td>
                      </tr>
                      <!-- Role & Department -->
                      <tr>
                        <td width="36%" valign="top" style="padding: 9px 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; font-size: 13px; color: #64748B; font-weight: 500;">
                          Role &amp; Department
                        </td>
                        <td width="64%" valign="top" style="padding: 9px 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; font-size: 13px; color: #1E293B;">
                          <span style="display: inline-block; padding: 3px 8px; border-radius: 4px; background-color: #DBEAFE; color: #1E40AF; font-size: 12px; font-weight: 700;">
                            {role_label}
                          </span>
                          <span style="color: #64748B; font-size: 12px; margin-left: 4px;">
                            ({department_label})
                          </span>
                        </td>
                      </tr>
                      <!-- Invitee Name -->
                      <tr>
                        <td width="36%" valign="top" style="padding: 9px 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; font-size: 13px; color: #64748B; font-weight: 500;">
                          Invitee Name
                        </td>
                        <td width="64%" valign="top" style="padding: 9px 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; font-size: 13px; font-weight: 600; color: #1E293B;">
                          {greeting_name}
                        </td>
                      </tr>
                      <!-- Username -->
                      <tr>
                        <td width="36%" valign="top" style="padding: 9px 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; font-size: 13px; color: #64748B; font-weight: 500;">
                          Assigned Username
                        </td>
                        <td width="64%" valign="top" style="padding: 9px 0; font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, Courier, monospace; font-size: 13px; font-weight: 700; color: #2563EB;">
                          {display_username}
                        </td>
                      </tr>
                    </table>
                  </td>
                </tr>
              </table>
            </td>
          </tr>

          <!-- 4. Prominent CTA Button (Bulletproof VML for Outlook) -->
          <tr>
            <td class="mobile-padding" align="center" style="padding: 10px 32px 28px 32px;">
              <table role="presentation" cellpadding="0" cellspacing="0" border="0" align="center">
                <tr>
                  <td align="center" style="border-radius: 8px; background-color: #2563EB;">
                    <!--[if mso]>
                    <v:roundrect xmlns:v="urn:schemas-microsoft-com:vml" xmlns:w="urn:schemas-microsoft-com:office:word" href="{accept_url}" style="height:52px;v-text-anchor:middle;width:300px;" arcsize="16%" stroke="f" fillcolor="#2563EB">
                      <w:anchorlock/>
                      <center style="color:#ffffff;font-family:Arial,sans-serif;font-size:15px;font-weight:bold;">
                        Accept Invitation &amp; Set Password
                      </center>
                    </v:roundrect>
                    <![endif]-->
                    <!--[if !mso]><!-->
                    <a href="{accept_url}" target="_blank" class="mobile-button" style="display: inline-block; background-color: #2563EB; color: #FFFFFF; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; font-size: 15px; font-weight: 700; text-decoration: none; padding: 15px 34px; border-radius: 8px; border: 1px solid #1D4ED8; box-shadow: 0 4px 6px -1px rgba(37, 99, 235, 0.25), 0 2px 4px -2px rgba(37, 99, 235, 0.25); text-align: center; letter-spacing: 0.3px;">
                      Accept Invitation &amp; Set Password &rarr;
                    </a>
                    <!--<![endif]-->
                  </td>
                </tr>
              </table>
            </td>
          </tr>

          <!-- 5. Expiry & Security Notice Banner -->
          <tr>
            <td class="mobile-padding" style="padding: 0 32px 24px 32px;">
              <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="background-color: #FEF3C7; border: 1px solid #FCD34D; border-radius: 8px;">
                <tr>
                  <td style="padding: 14px 18px;">
                    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">
                      <tr>
                        <td width="26" valign="top" style="font-size: 16px; line-height: 1.3;">
                          &#9200;
                        </td>
                        <td valign="middle" style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; font-size: 12.5px; color: #92400E; line-height: 1.5;">
                          <strong>Security &amp; Expiry Notice:</strong> This invitation is unique to your email and expires on <strong>{expiry_formatted}</strong> ({expiry_relative}). Please accept it promptly to complete onboarding.
                        </td>
                      </tr>
                    </table>
                  </td>
                </tr>
              </table>
            </td>
          </tr>

          <!-- 6. Direct Link Fallback Box -->
          <tr>
            <td class="mobile-padding" style="padding: 0 32px 32px 32px;">
              <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="background-color: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 8px;">
                <tr>
                  <td style="padding: 14px 18px;">
                    <p style="margin: 0 0 6px 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; font-size: 12px; color: #64748B; font-weight: 600;">
                      Having trouble with the button? Copy and paste this URL into your browser:
                    </p>
                    <p style="margin: 0; font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, Courier, monospace; font-size: 11.5px; color: #2563EB; word-break: break-all; line-height: 1.4;">
                      <a href="{accept_url}" target="_blank" style="color: #2563EB; text-decoration: underline;">{accept_url}</a>
                    </p>
                  </td>
                </tr>
              </table>
            </td>
          </tr>

          <!-- 7. Footer -->
          <tr>
            <td class="mobile-padding" style="padding: 24px 32px 32px 32px; background-color: #F8FAFC; border-top: 1px solid #E2E8F0;">
              <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">
                <tr>
                  <td align="center" style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; font-size: 12px; color: #94A3B8; line-height: 1.6;">
                    <p style="margin: 0 0 4px 0; font-weight: 600; color: #64748B;">
                      {org_name} &bull; Konstruct Tracker
                    </p>
                    {address_footer_html}
                    <p style="margin: 10px 0 0 0; font-size: 11px; color: #94A3B8;">
                      This automated invitation was sent to <strong>{invitation.email}</strong>. If you were not expecting this invitation, no action is required and you may safely delete this email.
                    </p>
                  </td>
                </tr>
              </table>
            </td>
          </tr>

        </table>

        <!--[if mso]>
        </td>
        </tr>
        </table>
        <![endif]-->

      </td>
    </tr>
  </table>

</body>
</html>"""

    from_email = (
        getattr(settings, "DEFAULT_FROM_EMAIL", None)
        or getattr(settings, "EMAIL_HOST_USER", None)
        or "rajbrijeshsingh1804@gmail.com"
    )

    try:
        msg = EmailMultiAlternatives(
            subject=subject,
            body=message,
            from_email=from_email,
            to=[invitation.email],
        )
        msg.attach_alternative(html_message, "text/html")

        # Attach organization logo as inline CID MIMEImage for maximum email client compatibility
        if has_logo and ctx.get("logo_bytes"):
            try:
                image_part = MIMEImage(ctx["logo_bytes"], _subtype=ctx.get("logo_mime_subtype", "png"))
                image_part.add_header("Content-ID", "<org_logo>")
                image_part.add_header("Content-Disposition", "inline", filename=ctx.get("logo_filename", "logo.png"))
                msg.attach(image_part)
            except Exception as e:
                logger.warning(f"Could not attach inline logo image to invitation email: {e}")

        sent = msg.send(fail_silently=False)
        logger.info(f"Invitation email successfully dispatched to {invitation.email}, status={sent}")
    except Exception as e:
        logger.error(f"Failed to send invitation email to {invitation.email}: {e}")
        # Graceful fallback: try basic send_mail if multi-alternatives or MIME attachment failed
        try:
            send_mail(
                subject,
                message,
                from_email,
                [invitation.email],
                html_message=html_message,
                fail_silently=True,
            )
        except Exception:
            pass


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
