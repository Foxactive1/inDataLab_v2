"""
Cache de execução de células indexado por content_hash.
TTL padrão: 24 horas. Limpeza via CellCache.purge_expired().
"""

from datetime import datetime, timedelta

from app.database.db import db

CACHE_TTL_HOURS = 24


class CellCache(db.Model):

    __tablename__ = "cell_cache"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    # Chave do cache — SHA-256 do conteúdo da célula
    content_hash = db.Column(
        db.String(64),
        unique=True,
        nullable=False,
        index=True
    )

    output = db.Column(
        db.Text
    )

    output_json = db.Column(
        db.JSON
    )

    execution_time = db.Column(
        db.Float
    )

    rows_returned = db.Column(
        db.Integer
    )

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        nullable=False
    )

    last_accessed_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        nullable=False
    )

    # Expiração explícita — necessária para evitar crescimento ilimitado
    expires_at = db.Column(
        db.DateTime,
        nullable=False,
        index=True,
        default=lambda: datetime.utcnow() + timedelta(hours=CACHE_TTL_HOURS)
    )

    # ------------------------------------------------------------------
    # Métodos de instância
    # ------------------------------------------------------------------

    @property
    def is_expired(self) -> bool:
        """Retorna True se o cache já passou do prazo de validade."""
        return datetime.utcnow() > self.expires_at

    def touch(self) -> None:
        """
        Atualiza last_accessed_at e prorroga o TTL a partir de agora.
        Chame este método sempre que um hit de cache for utilizado.
        """
        now = datetime.utcnow()
        self.last_accessed_at = now
        self.expires_at = now + timedelta(hours=CACHE_TTL_HOURS)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "content_hash": self.content_hash,
            "output": self.output,
            "output_json": self.output_json,
            "execution_time": self.execution_time,
            "rows_returned": self.rows_returned,
            "created_at": self.created_at.isoformat(),
            "last_accessed_at": self.last_accessed_at.isoformat(),
            "expires_at": self.expires_at.isoformat(),
            "is_expired": self.is_expired,
        }

    # ------------------------------------------------------------------
    # Métodos de classe
    # ------------------------------------------------------------------

    @classmethod
    def get(cls, content_hash: str) -> "CellCache | None":
        """
        Busca entrada no cache pelo hash.
        Retorna None se não existir ou se estiver expirada (e a remove).
        """
        entry = cls.query.filter_by(content_hash=content_hash).first()
        if entry is None:
            return None
        if entry.is_expired:
            db.session.delete(entry)
            db.session.commit()
            return None
        entry.touch()
        db.session.commit()
        return entry

    @classmethod
    def set(
        cls,
        content_hash: str,
        output: str = None,
        output_json=None,
        execution_time: float = None,
        rows_returned: int = None,
        ttl_hours: int = CACHE_TTL_HOURS,
    ) -> "CellCache":
        """
        Cria ou substitui uma entrada no cache.
        Executa purge_expired() antes de inserir para manter a tabela enxuta.
        """
        cls.purge_expired()

        # Upsert: remove entrada antiga se existir
        existing = cls.query.filter_by(content_hash=content_hash).first()
        if existing:
            db.session.delete(existing)
            db.session.flush()

        entry = cls(
            content_hash=content_hash,
            output=output,
            output_json=output_json,
            execution_time=execution_time,
            rows_returned=rows_returned,
            expires_at=datetime.utcnow() + timedelta(hours=ttl_hours),
        )
        db.session.add(entry)
        db.session.commit()
        return entry

    @classmethod
    def purge_expired(cls) -> int:
        """
        Remove todas as entradas expiradas.
        Retorna o número de registros deletados.
        """
        deleted = cls.query.filter(
            cls.expires_at < datetime.utcnow()
        ).delete(synchronize_session=False)
        db.session.commit()
        return deleted
