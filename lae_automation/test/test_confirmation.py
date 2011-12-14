
from cStringIO import StringIO

from mock import Mock

from twisted.trial import unittest
from twisted.python.filepath import FilePath
from foolscap.api import eventually

from lae_automation import confirmation
from lae_automation.confirmation import send_signup_confirmation


class MarkerException(Exception):
    pass


class TestConfirmation(unittest.TestCase):
    SMTP_HOST = confirmation.SMTP_HOST
    SMTP_PORT = confirmation.SMTP_PORT
    SMTP_USERNAME = confirmation.SMTP_USERNAME
    SMTP_PASSWORD = 'supersekret'
    SENDER_DOMAIN = confirmation.SENDER_DOMAIN
    FROM_EMAIL = confirmation.FROM_EMAIL
    CUSTOMER_NAME = 'Fred Bloggs'
    CUSTOMER_EMAIL = 'fbloggs@example.net'
    PGP_NOTIFICATION_EMAIL = confirmation.PGP_NOTIFICATION_EMAIL
    EXTERNAL_INTRODUCER_FURL = 'pb://foo@bar/baz'

    def setUp(self):
        FilePath('smtppassword').setContent(self.SMTP_PASSWORD)

    def _call_ESMTPSenderFactory_non_PGP(self, username, password, fromEmail, toEmail, f, d):
        self.failUnlessEqual(username, self.SMTP_USERNAME)
        self.failUnlessEqual(password, self.SMTP_PASSWORD)
        self.failUnlessEqual(fromEmail, self.FROM_EMAIL)
        self.failUnlessEqual(toEmail, self.CUSTOMER_EMAIL)
        f.seek(0, 0)
        # assume f can be read in one call
        message = f.read()
        assert f.read() == ''

        # although MIME specifies CRLF line endings, it is just LF at this point
        (headers, sep, body) = message.partition('\n\n')
        self.failUnlessEqual(sep, '\n\n')
        self.failUnlessIn('Message-ID: ', headers)
        self.failUnlessIn('Date: ', headers)
        self.failUnlessIn('Subject: ', headers)
        self.failUnlessIn('From: ', headers)
        self.failUnlessIn('To: ', headers)
        # FIXME: test for UTF-8
        self.failUnlessIn('Content-Type: text/plain', headers)
        self.failUnlessIn(self.CUSTOMER_NAME, body)
        self.failUnlessIn('https://leastauthority.com/howtoconfigure', body)
        self.failUnlessIn(self.EXTERNAL_INTRODUCER_FURL, body)

        eventually(d.callback, None)
        return self.the_factory

    def _call_ESMTPSenderFactory_PGP(self, username, password, fromEmail, toEmail, f, d):
        self.failUnlessEqual(username, self.SMTP_USERNAME)
        self.failUnlessEqual(password, self.SMTP_PASSWORD)
        self.failUnlessEqual(fromEmail, self.FROM_EMAIL)
        self.failUnlessEqual(toEmail, self.PGP_NOTIFICATION_EMAIL)
        f.seek(0, 0)
        # assume f can be read in one call
        message = f.read()
        assert f.read() == ''

        # although MIME specifies CRLF line endings, it is just LF at this point
        (headers, sep, body) = message.partition('\n\n')
        self.failUnlessEqual(sep, '\n\n')
        self.failUnlessIn('Message-ID: ', headers)
        self.failUnlessIn('Date: ', headers)
        self.failUnlessIn('Subject: ', headers)
        self.failUnlessIn('From: ', headers)
        self.failUnlessIn('To: ', headers)
        # FIXME: test for UTF-8
        self.failUnlessIn('Content-Type: text/plain', headers)
        self.failUnlessIn(self.CUSTOMER_NAME, body)
        self.failUnlessIn(self.CUSTOMER_EMAIL, body)
        self.failIfIn(self.EXTERNAL_INTRODUCER_FURL, body)

        eventually(d.callback, None)
        return self.the_factory

    def _test_send_signup_confirmation_success(self, call_factory, customer_keyinfo):
        self.the_factory = Mock()
        self.patch(confirmation, 'ESMTPSenderFactory', call_factory)

        connected = {}
        def call_connectTCP(smtphost, port, factory):
            self.failUnlessEqual(smtphost, self.SMTP_HOST)
            self.failUnlessEqual(port, self.SMTP_PORT)
            self.failUnlessEqual(factory, self.the_factory)
            self.failUnlessEqual(factory.domain, self.SENDER_DOMAIN)
            connected['flag'] = True
        self.patch(confirmation, 'connectTCP', call_connectTCP)

        stdout = StringIO()
        stderr = StringIO()
        d = send_signup_confirmation(self.CUSTOMER_NAME, self.CUSTOMER_EMAIL, self.EXTERNAL_INTRODUCER_FURL,
                                     customer_keyinfo, stdout, stderr, password_path='smtppassword')
        def _check(ign):
            self.failUnless('flag' in connected)
            out = stdout.getvalue()
            self.failUnlessIn("confirmation e-mail", out)
            self.failUnlessIn(self.CUSTOMER_EMAIL, out)
            self.failUnlessIn("sent.", out)
        d.addCallback(_check)
        return d

    def test_send_signup_confirmation_success_non_PGP(self):
        return self._test_send_signup_confirmation_success(self._call_ESMTPSenderFactory_non_PGP, '')

    def test_send_signup_confirmation_success_PGP(self):
        return self._test_send_signup_confirmation_success(self._call_ESMTPSenderFactory_PGP, '1234 ... ABCD')

    def test_send_signup_confirmation_factory_exception(self):
        stdout = StringIO()
        stderr = StringIO()

        def call_ESMTPSenderFactory(username, password, fromEmail, toEmail, f, d):
            raise MarkerException()
        self.patch(confirmation, 'ESMTPSenderFactory', call_ESMTPSenderFactory)

        d = send_signup_confirmation(self.CUSTOMER_NAME, self.CUSTOMER_EMAIL, self.EXTERNAL_INTRODUCER_FURL,
                                     '', stdout, stderr, password_path='smtppassword')
        def _bad_success(ign):
            self.fail("should have got a failure")
        def _check_failure(f):
            f.trap(MarkerException)
            out = stdout.getvalue()
            self.failUnlessIn("Sending of e-mail failed", out)
        d.addCallbacks(_bad_success, _check_failure)
        return d

    def test_send_signup_confirmation_factory_failure(self):
        stdout = StringIO()
        stderr = StringIO()

        def call_ESMTPSenderFactory(username, password, fromEmail, toEmail, f, d):
            eventually(d.errback, MarkerException())
            return Mock()
        self.patch(confirmation, 'ESMTPSenderFactory', call_ESMTPSenderFactory)

        def call_connectTCP(smtphost, port, factory):
            pass
        self.patch(confirmation, 'connectTCP', call_connectTCP)

        d = send_signup_confirmation(self.CUSTOMER_NAME, self.CUSTOMER_EMAIL, self.EXTERNAL_INTRODUCER_FURL,
                                     '', stdout, stderr, password_path='smtppassword')
        def _bad_success(ign):
            self.fail("should have got a failure")
        def _check_failure(f):
            f.trap(MarkerException)
            out = stdout.getvalue()
            self.failUnlessIn("Sending of e-mail failed", out)
        d.addCallbacks(_bad_success, _check_failure)
        return d

    def test_send_signup_confirmation_connect_exception(self):
        stdout = StringIO()
        stderr = StringIO()

        def call_ESMTPSenderFactory(username, password, fromEmail, toEmail, f, d):
            eventually(d.callback, None)
            return Mock()
        self.patch(confirmation, 'ESMTPSenderFactory', call_ESMTPSenderFactory)

        def call_connectTCP(smtphost, port, factory):
            raise MarkerException()
        self.patch(confirmation, 'connectTCP', call_connectTCP)

        d = send_signup_confirmation(self.CUSTOMER_NAME, self.CUSTOMER_EMAIL, self.EXTERNAL_INTRODUCER_FURL,
                                     '', stdout, stderr, password_path='smtppassword')
        def _bad_success(ign):
            self.fail("should have got a failure")
        def _check_failure(f):
            f.trap(MarkerException)
            out = stdout.getvalue()
            self.failUnlessIn("Sending of e-mail failed", out)
        d.addCallbacks(_bad_success, _check_failure)
        return d