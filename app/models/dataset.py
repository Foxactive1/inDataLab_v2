"""
Model: Dataset - Adaptado para portabilidade entre dispositivos
"""

import os
from datetime import datetime
from flask import current_app
from app.database.db import db
from app.utils.json_utils import sanitize_json


class Dataset(db.Model):
    __tablename__ = 'datasets'

    id = db.Column(db.Integer, primary_key=True)
    notebook_id = db.Column(db.Integer, db.ForeignKey('notebooks.id'), nullable=False, index=True)

    filename = db.Column(db.String(255), nullable=False)
    file_type = db.Column(db.String(20), nullable=False)

    # CAMPO ALTERADO: agora armazena caminho RELATIVO ao diretório de uploads
    relative_path = db.Column(db.String(500), nullable=False, unique=True)

    file_size = db.Column(db.BigInteger)
    rows = db.Column(db.Integer)
    columns = db.Column(db.Integer)
    column_names = db.Column(db.JSON)
    description = db.Column(db.Text)
    is_public = db.Column(db.Boolean, default=False)
    is_sql_database = db.Column(db.Boolean, default=False)
    file_hash = db.Column(db.String(64), nullable=True)
    uploaded_by_user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    extra_metadata = db.Column(db.JSON)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    cells = db.relationship('Cell', backref='dataset_ref', lazy=True, foreign_keys='Cell.dataset_id')

    def __repr__(self):
        return f'<Dataset {self.filename}>'

    @property
    def is_empty(self):
        return (self.rows or 0) == 0

    # PROPRIEDADE QUE RETORNA O CAMINHO ABSOLUTO DINAMICAMENTE
    @property
    def file_path(self):
        """
        Constrói o caminho absoluto a partir do relative_path e da configuração de upload.
        Funciona em qualquer dispositivo, desde que UPLOAD_FOLDER esteja configurado.
        """
        base_dir = current_app.config.get('UPLOAD_FOLDER')
        if not base_dir:
            raise RuntimeError("UPLOAD_FOLDER não configurado na aplicação")
        return os.path.join(base_dir, self.relative_path)

    @file_path.setter
    def file_path(self, absolute_path):
        """
        Ao atribuir um caminho absoluto, extrai e armazena apenas a parte relativa.
        Exige que UPLOAD_FOLDER esteja definido para calcular o relativo.
        """
        base_dir = current_app.config.get('UPLOAD_FOLDER')
        if not base_dir:
            raise RuntimeError("UPLOAD_FOLDER não configurado na aplicação")
        # Normaliza e calcula o caminho relativo
        self.relative_path = os.path.relpath(absolute_path, base_dir)

    def to_dict(self):
        # Retorna o caminho absoluto para compatibilidade com APIs existentes
        return {
            'id': self.id,
            'notebook_id': self.notebook_id,
            'filename': self.filename,
            'file_type': self.file_type,
            'file_path': self.file_path,          # caminho absoluto resolvido
            'relative_path': self.relative_path,  # opcional: para depuração
            'file_size': self.file_size,
            'file_hash': self.file_hash,
            'rows': self.rows,
            'columns': self.columns,
            'column_names': sanitize_json(self.column_names),
            'description': self.description,
            'is_public': self.is_public,
            'is_sql_database': self.is_sql_database,
            'uploaded_by_user_id': self.uploaded_by_user_id,
            'extra_metadata': sanitize_json(self.extra_metadata),
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }