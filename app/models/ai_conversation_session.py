"""
Model: AIConversationSession – Sessões de conversa com IA

Cada sessão agrupa várias mensagens (AIConversation) e mantém estatísticas agregadas.
Relacionamento com AIConversation via session_id (FK).
"""

import uuid
from datetime import datetime, timezone
from app.database.db import db


class AIConversationSession(db.Model):
    """
    Sessão de conversa com IA (agrupador lógico de mensagens)
    
    Attributes:
        id: Chave primária numérica
        session_uuid: Identificador único público (UUID string)
        user_id: Dono da sessão (FK para User)
        title: Título descritivo da sessão (ex: "Notebook 42")
        summary: Resumo gerado pela IA (opcional)
        primary_model: Modelo padrão usado na sessão
        total_tokens: Soma de tokens consumidos em todas as mensagens
        created_at: Data de criação (UTC)
        updated_at: Data da última atualização (UTC)
        conversations: Relacionamento com as mensagens da sessão
    """
    
    __tablename__ = "ai_conversation_sessions"
    
    id = db.Column(db.Integer, primary_key=True)
    
    session_uuid = db.Column(
        db.String(36),
        default=lambda: str(uuid.uuid4()),
        unique=True,
        nullable=False,
        index=True,
        doc="Identificador público (UUID) usado nas APIs"
    )
    
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=False,
        index=True
    )
    
    title = db.Column(db.String(255), doc="Título amigável da sessão")
    summary = db.Column(db.Text, doc="Resumo da conversa (gerado por IA)")
    primary_model = db.Column(db.String(100), doc="Modelo mais usado na sessão")
    total_tokens = db.Column(db.Integer, default=0, doc="Soma de tokens de todas as mensagens")
    
    created_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False
    )
    
    # ----------------------------------------------------------
    # RELACIONAMENTO CORRIGIDO: usa a FK session_id em AIConversation
    # ----------------------------------------------------------
    conversations = db.relationship(
        "AIConversation",
        backref="session",               # Permite acesso session.conversations e conversation.session
        lazy=True,
        foreign_keys="[AIConversation.session_id]",
        cascade="all, delete-orphan"     # Ao deletar a sessão, deleta todas as mensagens
    )
    
    def add_tokens(self, amount: int):
        """Incrementa o total de tokens da sessão."""
        self.total_tokens = (self.total_tokens or 0) + amount
        # O updated_at será atualizado automaticamente pelo onupdate
    
    def to_dict(self):
        """Serialização para API."""
        return {
            "id": self.id,
            "session_uuid": self.session_uuid,
            "user_id": self.user_id,
            "title": self.title,
            "summary": self.summary,
            "primary_model": self.primary_model,
            "total_tokens": self.total_tokens,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
    
    def __repr__(self):
        return f"<AIConversationSession {self.id} - {self.title or 'sem título'}>"