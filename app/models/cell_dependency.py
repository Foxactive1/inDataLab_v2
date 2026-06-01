"""
Modelo de dependência entre células.
Inclui validação de ciclo antes de inserir via CellDependency.create().
"""

from app.database.db import db


class CellDependency(db.Model):
    __tablename__ = 'cell_dependencies'

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    cell_id = db.Column(
        db.Integer,
        db.ForeignKey(
            'cells.id',
            ondelete='CASCADE'
        ),
        nullable=False,
        index=True
    )

    depends_on_cell_id = db.Column(
        db.Integer,
        db.ForeignKey(
            'cells.id',
            ondelete='CASCADE'
        ),
        nullable=False,
        index=True
    )

    dependency_type = db.Column(
        db.String(20),
        default='data',
        nullable=False
    )

    __table_args__ = (
        db.UniqueConstraint(
            'cell_id',
            'depends_on_cell_id',
            name='uq_cell_dependency'
        ),
        db.Index(
            'ix_cell_dependencies_pair',
            'cell_id',
            'depends_on_cell_id'
        ),
    )

    cell = db.relationship(
        'Cell',
        foreign_keys=[cell_id],
        backref='dependencies_as_dependent'
    )

    depends_on_cell = db.relationship(
        'Cell',
        foreign_keys=[depends_on_cell_id],
        backref='dependencies_as_prerequisite'
    )

    def __repr__(self):
        return (
            f'<CellDependency '
            f'{self.cell_id} -> '
            f'{self.depends_on_cell_id}>'
        )

    def to_dict(self):
        return {
            'id': self.id,
            'cell_id': self.cell_id,
            'depends_on_cell_id': self.depends_on_cell_id,
            'dependency_type': self.dependency_type,
        }

    # ------------------------------------------------------------------
    # Métodos de classe
    # ------------------------------------------------------------------

    @classmethod
    def _would_create_cycle(cls, cell_id: int, depends_on_cell_id: int) -> bool:
        """
        BFS a partir de depends_on_cell_id seguindo suas próprias dependências.
        Se cell_id for alcançado, adicionar a dependência criaria um ciclo.

        Exemplo de ciclo que seria bloqueado:
            A → B → C → A  (A depende de C que depende de B que depende de A)
        """
        visited = set()
        queue = [depends_on_cell_id]

        while queue:
            current = queue.pop(0)
            if current == cell_id:
                return True
            if current in visited:
                continue
            visited.add(current)
            children = cls.query.filter_by(cell_id=current).all()
            queue.extend(dep.depends_on_cell_id for dep in children)

        return False

    @classmethod
    def create(
        cls,
        cell_id: int,
        depends_on_cell_id: int,
        dependency_type: str = 'data'
    ) -> tuple["CellDependency | None", "str | None"]:
        """
        Cria uma dependência com validação de ciclo.
        Retorna (instância, None) em sucesso ou (None, mensagem_de_erro).
        """
        if cell_id == depends_on_cell_id:
            return None, "Uma célula não pode depender de si mesma."

        if cls._would_create_cycle(cell_id, depends_on_cell_id):
            return None, (
                f"Dependência cíclica detectada: adicionar "
                f"célula {cell_id} → {depends_on_cell_id} criaria um ciclo."
            )

        existing = cls.query.filter_by(
            cell_id=cell_id,
            depends_on_cell_id=depends_on_cell_id
        ).first()
        if existing:
            return None, "Dependência já existe."

        dep = cls(
            cell_id=cell_id,
            depends_on_cell_id=depends_on_cell_id,
            dependency_type=dependency_type,
        )
        db.session.add(dep)
        db.session.commit()
        return dep, None
