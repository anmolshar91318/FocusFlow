import os
import ssl
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime, timezone
from pathlib import Path

# Load environment if not already loaded
def _load_env_fallback():
    for p in [Path(__file__).parent / ".env", Path(__file__).parent.parent / ".env"]:
        if p.exists():
            try:
                with open(p, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line or line.startswith("#") or "=" not in line:
                            continue
                        k, v = line.split("=", 1)
                        k = k.strip()
                        v = v.strip().strip("'\"")
                        if k and k not in os.environ:
                            os.environ[k] = v
            except Exception:
                pass

_load_env_fallback()


def get_smtp_config():
    """Returns current SMTP configuration from environment variables."""
    host = os.environ.get("SMTP_HOST", "smtp.gmail.com").strip()
    port_str = os.environ.get("SMTP_PORT", "587").strip()
    try:
        port = int(port_str)
    except ValueError:
        port = 587

    user = os.environ.get("SMTP_USER", "").strip()
    # Strip spaces in case user copied app password with spaces e.g. "abcd efgh ijkl mnop"
    password = os.environ.get("SMTP_PASSWORD", "").replace(" ", "").strip()
    from_email = os.environ.get("SMTP_FROM", "").strip() or user
    from_name = os.environ.get("SMTP_FROM_NAME", "FocusFlow").strip()

    use_ssl = os.environ.get("SMTP_USE_SSL", "").lower() in ("true", "1") or port == 465
    use_tls = os.environ.get("SMTP_USE_TLS", "true" if not use_ssl else "false").lower() in ("true", "1")

    is_configured = bool(user and password)

    return {
        "host": host,
        "port": port,
        "user": user,
        "password": password,
        "from_email": from_email,
        "from_name": from_name,
        "use_ssl": use_ssl,
        "use_tls": use_tls,
        "is_configured": is_configured,
    }


def send_email(to_email: str, subject: str, html_content: str, text_content: str = "") -> dict:
    """
    Sends an email using configured Google SMTP server.
    If SMTP is not configured, logs the email details to server console for testing/development.
    """
    cfg = get_smtp_config()

    if not cfg["is_configured"]:
        print("\n" + "=" * 70)
        print("[FocusFlow Email Service] NOTICE: Google SMTP is not configured yet.")
        print(f"Recipient: {to_email}")
        print(f"Subject:   {subject}")
        print("-" * 70)
        print("Message Preview (Plain text):")
        print(text_content or "(No plain text content)")
        print("=" * 70 + "\n")
        return {
            "success": True,
            "mock": True,
            "message": "SMTP not configured. Verification code logged to server console.",
        }

    try:
        # Build multipart email message
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = f"{cfg['from_name']} <{cfg['from_email']}>" if cfg["from_name"] else cfg["from_email"]
        msg["To"] = to_email

        if text_content:
            msg.attach(MIMEText(text_content, "plain", "utf-8"))
        if html_content:
            msg.attach(MIMEText(html_content, "html", "utf-8"))

        # Connect and send
        if cfg["use_ssl"]:
            context = ssl.create_default_context()
            with smtplib.SMTP_SSL(cfg["host"], cfg["port"], context=context, timeout=15) as server:
                server.login(cfg["user"], cfg["password"])
                server.send_message(msg)
        else:
            with smtplib.SMTP(cfg["host"], cfg["port"], timeout=15) as server:
                server.ehlo()
                if cfg["use_tls"]:
                    context = ssl.create_default_context()
                    server.starttls(context=context)
                    server.ehlo()
                server.login(cfg["user"], cfg["password"])
                server.send_message(msg)

        print(f"[FocusFlow Email Service] Successfully sent email to {to_email} via {cfg['host']}:{cfg['port']}")
        return {"success": True, "mock": False, "message": "Email sent successfully."}

    except smtplib.SMTPAuthenticationError as e:
        err = f"SMTP Authentication failed: {e}. If using Gmail, make sure to use a 16-character Google App Password."
        print(f"[FocusFlow Email Service] ERROR: {err}")
        return {"success": False, "error": err}
    except Exception as e:
        err = f"Failed to send email via SMTP: {e}"
        print(f"[FocusFlow Email Service] ERROR: {err}")
        return {"success": False, "error": err}


def send_verification_email(to_email: str, user_name: str, code: str) -> dict:
    """Sends email verification code to user upon registration or resend request."""
    subject = f"{code} is your FocusFlow verification code"
    display_name = user_name if user_name else "there"

    text_content = f"""Hello {display_name},

Thank you for signing up for FocusFlow!

Your verification code is: {code}

This code will expire in 15 minutes. Enter this code on the verification screen to activate your account.

If you did not create a FocusFlow account, please ignore this email.

Best regards,
The FocusFlow Team
"""

    html_content = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>FocusFlow Email Verification</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #f8fafc; color: #1e293b; margin: 0; padding: 24px; }}
    .container {{ max-width: 540px; margin: 0 auto; background: #ffffff; border-radius: 16px; border: 1px solid #e2e8f0; overflow: hidden; box-shadow: 0 4px 16px rgba(0,0,0,0.04); }}
    .header {{ background: linear-gradient(135deg, #6366f1 0%, #4f46e5 100%); padding: 32px 24px; text-align: center; color: #ffffff; }}
    .header h1 {{ margin: 0; font-size: 24px; font-weight: 800; letter-spacing: -0.5px; }}
    .header p {{ margin: 6px 0 0; font-size: 13px; opacity: 0.9; letter-spacing: 0.5px; text-transform: uppercase; font-weight: 600; }}
    .content {{ padding: 36px 32px; }}
    .greeting {{ font-size: 17px; font-weight: 600; margin-bottom: 12px; color: #0f172a; }}
    .desc {{ font-size: 15px; line-height: 1.6; color: #475569; margin: 0 0 24px; }}
    .code-box {{ background: #f5f3ff; border: 2px dashed #818cf8; border-radius: 12px; padding: 20px; text-align: center; margin: 28px 0; }}
    .code-label {{ font-size: 11px; text-transform: uppercase; letter-spacing: 1.5px; color: #6366f1; font-weight: 700; margin-bottom: 6px; }}
    .code-value {{ font-family: 'Courier New', Courier, monospace; font-size: 36px; font-weight: 800; letter-spacing: 10px; color: #4338ca; margin: 0; }}
    .expires {{ font-size: 13px; color: #64748b; text-align: center; margin-top: 8px; }}
    .footer {{ background: #f8fafc; padding: 20px 32px; text-align: center; font-size: 12px; color: #94a3b8; border-top: 1px solid #f1f5f9; }}
    .footer p {{ margin: 4px 0; }}
  </style>
</head>
<body>
  <div class="container">
    <div class="header">
      <p>FocusFlow Authentication</p>
      <h1>Verify Your Email</h1>
    </div>
    <div class="content">
      <div class="greeting">Hello {display_name},</div>
      <p class="desc">
        Welcome to <strong>FocusFlow</strong>! To finalize your registration and protect your study space, please enter the 6-digit verification code below:
      </p>
      <div class="code-box">
        <div class="code-label">Verification Code</div>
        <div class="code-value">{code}</div>
      </div>
      <p class="expires">⏱ This code is valid for <strong>15 minutes</strong>.</p>
      <p class="desc" style="font-size: 13px; margin-top: 28px; color: #64748b;">
        If you didn't create a FocusFlow account with this email address, you can safely ignore this message.
      </p>
    </div>
    <div class="footer">
      <p>FocusFlow — Plan. Focus. Master.</p>
      <p>Automated security notification, please do not reply to this email.</p>
    </div>
  </div>
</body>
</html>
"""
    return send_email(to_email, subject, html_content, text_content)


def send_password_reset_email(to_email: str, user_name: str, code: str) -> dict:
    """Sends password reset code to user."""
    subject = f"{code} is your FocusFlow password reset code"
    display_name = user_name if user_name else "there"

    text_content = f"""Hello {display_name},

We received a request to reset the password for your FocusFlow account.

Your password reset code is: {code}

This code will expire in 15 minutes. Enter this code on the password reset screen along with your new password.

If you did not request a password reset, please ignore this email. Your current password remains secure.

Best regards,
The FocusFlow Team
"""

    html_content = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>FocusFlow Password Reset</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #f8fafc; color: #1e293b; margin: 0; padding: 24px; }}
    .container {{ max-width: 540px; margin: 0 auto; background: #ffffff; border-radius: 16px; border: 1px solid #e2e8f0; overflow: hidden; box-shadow: 0 4px 16px rgba(0,0,0,0.04); }}
    .header {{ background: linear-gradient(135deg, #e11d48 0%, #be123c 100%); padding: 32px 24px; text-align: center; color: #ffffff; }}
    .header h1 {{ margin: 0; font-size: 24px; font-weight: 800; letter-spacing: -0.5px; }}
    .header p {{ margin: 6px 0 0; font-size: 13px; opacity: 0.9; letter-spacing: 0.5px; text-transform: uppercase; font-weight: 600; }}
    .content {{ padding: 36px 32px; }}
    .greeting {{ font-size: 17px; font-weight: 600; margin-bottom: 12px; color: #0f172a; }}
    .desc {{ font-size: 15px; line-height: 1.6; color: #475569; margin: 0 0 24px; }}
    .code-box {{ background: #fff1f2; border: 2px dashed #fb7185; border-radius: 12px; padding: 20px; text-align: center; margin: 28px 0; }}
    .code-label {{ font-size: 11px; text-transform: uppercase; letter-spacing: 1.5px; color: #e11d48; font-weight: 700; margin-bottom: 6px; }}
    .code-value {{ font-family: 'Courier New', Courier, monospace; font-size: 36px; font-weight: 800; letter-spacing: 10px; color: #9f1239; margin: 0; }}
    .expires {{ font-size: 13px; color: #64748b; text-align: center; margin-top: 8px; }}
    .security-note {{ background: #f1f5f9; border-radius: 8px; padding: 12px 16px; font-size: 13px; color: #475569; margin-top: 24px; border-left: 3px solid #94a3b8; }}
    .footer {{ background: #f8fafc; padding: 20px 32px; text-align: center; font-size: 12px; color: #94a3b8; border-top: 1px solid #f1f5f9; }}
    .footer p {{ margin: 4px 0; }}
  </style>
</head>
<body>
  <div class="container">
    <div class="header">
      <p>FocusFlow Security</p>
      <h1>Reset Your Password</h1>
    </div>
    <div class="content">
      <div class="greeting">Hello {display_name},</div>
      <p class="desc">
        We received a request to reset your <strong>FocusFlow</strong> password. Use the 6-digit code below to set a new password:
      </p>
      <div class="code-box">
        <div class="code-label">Password Reset Code</div>
        <div class="code-value">{code}</div>
      </div>
      <p class="expires">⏱ This code is valid for <strong>15 minutes</strong>.</p>
      <div class="security-note">
        <strong>Security Notice:</strong> If you did not request this password reset, you can safely ignore this email. Your current password remains active and secure.
      </div>
    </div>
    <div class="footer">
      <p>FocusFlow — Plan. Focus. Master.</p>
      <p>Automated security notification, please do not reply to this email.</p>
    </div>
  </div>
</body>
</html>
"""
    return send_email(to_email, subject, html_content, text_content)
