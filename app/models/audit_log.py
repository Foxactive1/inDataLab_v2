"""
Auditoria do sistema
"""

from datetime import datetime

from app.database.db import db


class AuditLog(db.Model):

    __tablename__ = "audit_logs"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    user_id = db.Column(
        db.Integer,
        nullable=True,
        index=True
    )

    entity_type = db.Column(
        db.String(50),
        nullable=False
    )

    entity_id = db.Column(
        db.Integer,
        nullable=False
    )

    action = db.Column(
        db.String(50),
        nullable=False,
        index=True
    )

    old_data = db.Column(
        db.JSON
    )

    new_data = db.Column(
        db.JSON
    )

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        nullable=False
    )