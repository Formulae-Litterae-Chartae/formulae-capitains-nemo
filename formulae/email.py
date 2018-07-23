from flask import render_template
from flask_mail import Message
from flask_babel import _
from threading import Thread
from .app import mail, flask_app

def send_async_email(app, msg):
    with app.app_context():
        mail.send(msg)

def send_email(subject, sender, recipients, text_body, html_body):
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
    Thread(target=send_async_email, args=(flask_app, msg)).start()

