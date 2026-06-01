"""
Model: User
Com métodos de hash de senha integrados (werkzeug)
"""

from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from app.database.db import db


class User(db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.Text, nullable=False)

    is_active = db.Column(db.Boolean, default=True, index=True)
    is_superuser = db.Column(db.Boolean, default=False)

    reset_token = db.Column(db.String(100), nullable=True, unique=True)
    reset_token_expiry = db.Column(db.DateTime, nullable=True)

    avatar_url = db.Column(db.Text, nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relacionamentos
    notebooks = db.relationship('Notebook', backref='user', lazy=True, cascade='all, delete-orphan')
    ai_conversations = db.relationship('AIConversation', backref='user', lazy=True, cascade='all, delete-orphan')
    uploaded_datasets = db.relationship('Dataset', backref='uploader', foreign_keys='Dataset.uploaded_by_user_id')

    def set_password(self, password: str):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f'<User {self.email}>'

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'email': self.email,
            'is_active': self.is_active,
            'avatar_url': self.avatar_url,
            'created_at': self.created_at.isoformat(),
        }