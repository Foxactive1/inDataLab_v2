"""
Model: Notebook
Com KernelType enum e validação básica
"""

from datetime import datetime
import enum
from app.database.db import db


class KernelType(enum.Enum):
    PYTHON3 = 'python3'
    R = 'r'
    SQL = 'sql'


class Notebook(db.Model):
    __tablename__ = 'notebooks'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)

    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text)

    is_public = db.Column(db.Boolean, default=False, index=True)
    is_archived = db.Column(db.Boolean, default=False)

    kernel_type = db.Column(db.Enum(KernelType), default=KernelType.PYTHON3, nullable=False)
    default_sql_connection = db.Column(db.String(500), nullable=True, comment="Caminho do banco SQL padrão")

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relacionamentos (soft delete filtrado)
    cells = db.relationship(
        'Cell',
        backref='notebook',
        lazy='dynamic',
        primaryjoin="and_(Cell.notebook_id==Notebook.id, Cell.is_deleted==False)",
        cascade='all, delete-orphan'
    )
    datasets = db.relationship('Dataset', backref='notebook', lazy='dynamic', cascade='all, delete-orphan')
    ai_conversations = db.relationship('AIConversation', backref='notebook', lazy='dynamic')

    def __repr__(self):
        return f'<Notebook {self.title} (id={self.id})>'

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'title': self.title,
            'description': self.description,
            'is_public': self.is_public,
            'is_archived': self.is_archived,
            'kernel_type': self.kernel_type.value if self.kernel_type else None,
            'default_sql_connection': self.default_sql_connection,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }