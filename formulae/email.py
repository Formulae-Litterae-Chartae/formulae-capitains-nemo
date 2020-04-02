from flask import current_app
from flask_mail import Message
from threading import Thread
from . import mail


def send_async_email(app, msg):
    with app.app_context():
        mail.send(msg)


def send_email(subject: str, sender: str, recipients: list, text_body: str, html_body: str):
    """ Helper function to send email

    :param subject: Email subject line
    :param sender: Email sender
    :param recipients: List of email recipients
    :param text_body: The plain text body of the email
    :param html_body: The HTML body of the email
    """
    msg = Message(subject, sender=sender, recipients=recipients)
    msg.body = text_body
    msg.html = html_body
    Thread(target=send_async_email, args=(current_app._get_current_object(), msg)).start()

