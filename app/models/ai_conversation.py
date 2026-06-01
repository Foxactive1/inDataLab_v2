"""
Model: AIConversation – Mensagens individuais de conversas com IA

Relacionamento com AIConversationSession via session_id (FK real).
Mantém campos de compatibilidade (conversation_session_id) para migração gradual.
"""

from datetime import datetime
from app.database.db import db


class AIConversation(db.Model):
    """
    Modelo de Conversa com IA (cada linha = uma mensagem, usuário ou assistente)
    
    Attributes:
        id: Identificador único
        user_id: Usuário dono da mensagem (FK para User)
        notebook_id: Notebook associado (opcional)
        cell_id: Célula associada (opcional)
        session_id: Chave estrangeira para AIConversationSession.id (relacionamento real)
        conversation_session_id: UUID string para compatibilidade com código legado
        role: 'user' ou 'assistant'
        content: Texto da mensagem
        model: Modelo Groq utilizado
        temperature: Parâmetro de criatividade
        tokens_used: Total de tokens da requisição
        input_tokens: Tokens enviados
        output_tokens: Tokens gerados
        processing_time: Tempo de resposta (segundos)
        groq_request_id: ID da requisição no Groq (rastreamento)
        extra_metadata: Metadados extras (JSON string)
        created_at: Data de criação (UTC)
    """
    
    __tablename__ = 'ai_conversations'
    
    id = db.Column(db.Integer, primary_key=True)
    
    user_id = db.Column(
        db.Integer,
        db.ForeignKey('users.id'),
        nullable=False,
        index=True
    )
    
    notebook_id = db.Column(
        db.Integer,
        db.ForeignKey('notebooks.id', ondelete='SET NULL'),
        nullable=True,
        index=True
    )
    
    cell_id = db.Column(
        db.Integer,
        db.ForeignKey('cells.id', ondelete='SET NULL'),
        nullable=True,
        index=True
    )
    
    # ----------------------------------------------------------
    # NOVO: Chave estrangeira real para a tabela de sessões
    # ----------------------------------------------------------
    session_id = db.Column(
        db.Integer,
        db.ForeignKey('ai_conversation_sessions.id', ondelete='SET NULL'),
        nullable=True,
        index=True,
        doc="Relacionamento real com a tabela de sessões (PK)"
    )
    
    # Campo legado – mantido para compatibilidade com APIs antigas
    # Pode ser removido após a migração completa do código.
    conversation_session_id = db.Column(
        db.String(100),
        index=True,
        doc="UUID da sessão (string) – mantido para compatibilidade"
    )
    
    role = db.Column(
        db.String(20),
        nullable=False,
        default='user',
        index=True
    )
    
    content = db.Column(db.Text, nullable=False)
    
    model = db.Column(db.String(100), default='llama-3.3-70b-versatile')
    temperature = db.Column(db.Float, default=0.7)
    
    tokens_used = db.Column(db.Integer)
    input_tokens = db.Column(db.Integer)
    output_tokens = db.Column(db.Integer)
    processing_time = db.Column(db.Float)
    groq_request_id = db.Column(db.String(100))
    extra_metadata = db.Column(db.Text, comment='Metadados adicionais (JSON)')
    
    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        nullable=False,
        index=True
    )
    
    def __repr__(self):
        return f'<AIConversation {self.id} ({self.role})>'
    
    def to_dict(self):
        """Serialização para API (sem expor dados internos sensíveis)"""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'notebook_id': self.notebook_id,
            'cell_id': self.cell_id,
            'session_id': self.session_id,          # ID numérico da sessão
            'conversation_session_id': self.conversation_session_id,  # UUID legado
            'role': self.role,
            'content': self.content,
            'model': self.model,
            'tokens_used': self.tokens_used,
            'processing_time': self.processing_time,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }