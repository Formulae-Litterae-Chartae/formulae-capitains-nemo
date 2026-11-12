from logging.handlers import SMTPHandler
import socket

class ErrorSMTPHandler(SMTPHandler):
    def __init__(self, hostname, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.hostname = hostname

    def getSubject(self, record):
        exc = "Error"
        if record.exc_info:
            exc = record.exc_info[0].__name__
        return f"{self.hostname} - {exc}"