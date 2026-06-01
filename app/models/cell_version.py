"""
Histórico completo de versões das células.
Um registro é criado automaticamente pelo CellService.update_cell
sempre que o content de uma célula é modificado.
"""

from datetime import datetime

from app.database.db import db


class CellVersion(db.Model):

    __tablename__ = "cell_versions"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    cell_id = db.Column(
        db.Integer,
        db.ForeignKey(
            "cells.id",
            ondelete="CASCADE"
        ),
        nullable=False,
        index=True
    )

    # Número da versão no momento do snapshot (antes do update)
    version = db.Column(
        db.Integer,
        nullable=False
    )

    # Conteúdo anterior — necessário para restauração
    content = db.Column(
        db.Text,
        nullable=False
    )

    content_hash = db.Column(
        db.String(64),
        nullable=False,
        index=True
    )

    created_by = db.Column(
        db.Integer,
        nullable=True
    )

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        nullable=False
    )

    cell = db.relationship(
        "Cell",
        backref=db.backref(
            "versions",
            lazy=True,
            cascade="all, delete-orphan",
            order_by="CellVersion.version.desc()"   # mais recente primeiro
        )
    )

    def to_dict(self):
        return {
            "id": self.id,
            "cell_id": self.cell_id,
            "version": self.version,
            "content": self.content,          # necessário para restaurar
            "content_hash": self.content_hash,
            "created_by": self.created_by,
            "created_at": self.created_at.isoformat()
        }
