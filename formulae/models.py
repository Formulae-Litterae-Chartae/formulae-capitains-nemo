from flask import current_app
from . import db, login
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
from time import time
import jwt
from typing import Tuple


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), index=True, unique=True)
    email = db.Column(db.String(120), index=True, unique=True)
    password_hash = db.Column(db.String(128))
    project_team = db.Column(db.Boolean, index=True, default=False)
    default_locale = db.Column(db.String(32), index=True, default="de")

    def __repr__(self) -> str:
        return '<User {}>'.format(self.username)

    def set_password(self, password: str):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    def get_reset_password_token(self, expires_in: int = 600):
        return jwt.encode({'reset_password': self.id, 'exp': time() + expires_in},
                          current_app.config['SECRET_KEY'], algorithm='HS256')

    def get_reset_email_token(self, new_email: str, expires_in: int = 600):
        return jwt.encode({'user_id': self.id, 'old_email': self.email, 'new_email': new_email,
                           'exp': time() + expires_in},
                          current_app.config['SECRET_KEY'], algorithm='HS256')

    @staticmethod
    def verify_reset_email_token(token: str) -> Tuple['User', str, str]:
        try:
            decoded_token = jwt.decode(token, current_app.config['SECRET_KEY'], algorithms=['HS256'])
            id = decoded_token['user_id']
            old_email = decoded_token['old_email']
            new_email = decoded_token['new_email']
        except:
            return
        return User.query.get(id), old_email, new_email

    @staticmethod
    def verify_reset_password_token(token: str) -> 'User':
        try:
            id = jwt.decode(token, current_app.config['SECRET_KEY'], algorithms=['HS256'])['reset_password']
        except:
            return
        return User.query.get(id)


@login.user_loader
def load_user(id):
    return User.query.get(int(id))
