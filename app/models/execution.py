"""
Model: Execution – histórico de execução de células
"""

from datetime import datetime
from app.database.db import db


class Execution(db.Model):
    __tablename__ = 'executions'

    id = db.Column(db.Integer, primary_key=True)
    cell_id = db.Column(db.Integer, db.ForeignKey('cells.id'), nullable=False, index=True)

    status = db.Column(db.String(20), default='pending', index=True)  # pending, running, success, error
    execution_time = db.Column(db.Float)  # segundos

    logs = db.Column(db.Text)             # stdout
    error_message = db.Column(db.Text)    # stderr + traceback (unificado)

    memory_used = db.Column(db.Float)     # MB

    executed_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)  # quando o registro foi criado

    # Índice composto para queries comuns
    __table_args__ = (
        db.Index('ix_executions_cell_status', 'cell_id', 'status'),
    )

    def __repr__(self):
        return f'<Execution {self.id} ({self.status})>'

    def to_dict(self):
        return {
            'id': self.id,
            'cell_id': self.cell_id,
            'status': self.status,
            'execution_time': self.execution_time,
            'logs': self.logs,
            'error_message': self.error_message,
            'executed_at': self.executed_at.isoformat(),
        }