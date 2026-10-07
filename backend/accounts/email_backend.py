"""
Custom SMTP email backend that uses the operating system's native
certificate trust store (Windows Certificate Store via schannel) instead
of certifi's bundled CA list.

Why: certifi only trusts public CAs. On many Windows machines, antivirus
software (Kaspersky, Avast, Bitdefender, etc.) intercepts HTTPS/SMTP
traffic to scan it, re-signing connections with its own local root
certificate. That cert is legitimately trusted by Windows (the antivirus
installs it into the OS trust store) but is NOT in certifi's bundle,
which is why certifi raises "self-signed certificate in certificate
chain" even though the connection is fine. Using truststore.SSLContext
delegates trust decisions to Windows itself, which already knows about
and trusts that certificate.
"""

import ssl
from django.core.mail.backends.smtp import EmailBackend as SMTPBackend

try:
    import truststore
    HAS_TRUSTSTORE = True
except ImportError:
    HAS_TRUSTSTORE = False


class CertifiEmailBackend(SMTPBackend):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if HAS_TRUSTSTORE:
            try:
                self.ssl_context = truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
                return
            except Exception:
                pass
        self.ssl_context = ssl.create_default_context()