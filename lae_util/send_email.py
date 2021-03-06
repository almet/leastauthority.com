
from cStringIO import StringIO
from email.mime.text import MIMEText

from twisted.internet import defer
from twisted.internet.reactor import connectTCP
from twisted.mail.smtp import messageid, rfc822date, ESMTPSenderFactory
from twisted.python.filepath import FilePath


SENDER_DOMAIN = "leastauthority.com"
FROM_EMAIL = "info@leastauthority.com"
FROM_ADDRESS = "Least Authority <%s>" % (FROM_EMAIL,)
SUPPORT_ADDRESS = "Least Authority Support <support@leastauthority.com>"
USER_AGENT = "Least Authority e-mail sender"
CONTENT_TYPE = 'text/plain; charset="utf-8"'

PGP_NOTIFICATION_EMAIL = "zancas@leastauthority.com"

SMTP_HOST = "smtp.googlemail.com"
SMTP_PORT = 25
SMTP_USERNAME = FROM_EMAIL
SMTP_PASSWORD_PATH = "../secret_config/smtppassword"
REQUIRE_AUTH = True
REQUIRE_TRANSPORT_SECURITY = True


def send_plain_email(fromEmail, toEmail, content, headers):
    if REQUIRE_AUTH:
        password = FilePath(SMTP_PASSWORD_PATH).getContent().strip()
    else:
        password = None

    msg = MIMEText(content)

    # Setup the mail headers
    for (header, value) in headers.items():
        msg[header] = value

    headkeys = [k.lower() for k in headers.keys()]

    # Add required headers if not present
    if "message-id" not in headkeys:
        msg["Message-ID"] = messageid()
    if "date" not in headkeys:
        msg["Date"] = rfc822date()
    if "from" not in headkeys and "sender" not in headkeys:
        msg["From"] = fromEmail
    if "to" not in headkeys and "cc" not in headkeys and "bcc" not in headkeys:
        msg["To"] = toEmail
    if "reply-to" not in headkeys:
        msg["Reply-To"] = SUPPORT_ADDRESS
    if "user-agent" not in headkeys:
        msg["User-Agent"] = USER_AGENT
    if "content-type" not in headkeys:
        msg["Content-Type"] = CONTENT_TYPE

    # send message
    f = StringIO(msg.as_string())
    d = defer.Deferred()
    factory = ESMTPSenderFactory(SMTP_USERNAME, password, fromEmail, toEmail, f, d,
                                 requireAuthentication=REQUIRE_AUTH,
                                 requireTransportSecurity=REQUIRE_TRANSPORT_SECURITY)
    factory.domain = SENDER_DOMAIN
    connectTCP(SMTP_HOST, SMTP_PORT, factory)

    return d
