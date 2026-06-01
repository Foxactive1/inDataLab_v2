"""
Service: CellService
CRUD de células com validação, ordenação, suporte a tags JSON e soft delete
"""

from datetime import datetime
from typing import Optional, List, Tuple, Union

from app.database.db import db
from app.models.cell import Cell
from app.models.cell_version import CellVersion
from app.models.notebook import Notebook


class CellService:
    """
    Serviço para operações com Células
    Tipos suportados: python, sql, markdown, ai
    """
    
    @staticmethod
    def _validate_user_owns_notebook(notebook_id: int, user_id: int) -> bool:
        notebook = Notebook.query.filter_by(id=notebook_id, user_id=user_id).first()
        return notebook is not None
    
    @staticmethod
    def _normalize_tags(tags: Union[str, List[str], None]) -> List[str]:
        """
        Converte tags nos formatos aceitos para lista de strings.
        - str: "tag1, tag2" → ["tag1", "tag2"]
        - list: ["tag1", "tag2"] → mantém
        - None → []
        """
        if not tags:
            return []
        if isinstance(tags, str):
            return [t.strip() for t in tags.split(',') if t.strip()]
        if isinstance(tags, list):
            return [str(t).strip() for t in tags if t]
        return []
    
    @staticmethod
    def create_cell(
        notebook_id: int,
        user_id: int,
        cell_type: str,
        content: str,
        position: Optional[int] = None,
        tags: Optional[Union[str, List[str]]] = None,
        sql_connection: Optional[str] = None
    ) -> Tuple[Optional[Cell], Optional[str]]:
        """
        Criar nova célula.
        cell_type: python, sql, markdown, ai (aceita 'code' como compatibilidade)
        tags: string CSV ou lista de strings
        """
        try:
            if not CellService._validate_user_owns_notebook(notebook_id, user_id):
                return None, "Sem permissão"
            
            # Compatibilidade com frontend antigo
            if cell_type == 'code':
                cell_type = 'python'
            
            valid_types = ['python', 'sql', 'markdown', 'ai']
            if cell_type not in valid_types:
                return None, f"cell_type deve ser um de: {valid_types}"
            
            if not content or len(content.strip()) == 0:
                return None, "Conteúdo é obrigatório"
            
            # Determinar posição
            if position is None:
                max_pos = db.session.query(db.func.max(Cell.position)).filter_by(
                    notebook_id=notebook_id, is_deleted=False
                ).scalar() or -1
                position = max_pos + 1
            
            tags_normalized = CellService._normalize_tags(tags)
            
            cell = Cell(
                notebook_id=notebook_id,
                cell_type=cell_type,
                content=content.strip(),
                position=position,
                tags=tags_normalized,
                execution_count=0,
                sql_connection=sql_connection
            )
            
            db.session.add(cell)
            db.session.commit()
            return cell, None
        
        except Exception as e:
            db.session.rollback()
            return None, f"Erro ao criar célula: {str(e)}"
    
    @staticmethod
    def get_cell(cell_id: int, user_id: Optional[int] = None) -> Optional[Cell]:
        cell = Cell.query.get(cell_id)
        if not cell or cell.is_deleted:
            return None
        if user_id:
            notebook = Notebook.query.get(cell.notebook_id)
            if not notebook or notebook.user_id != user_id:
                return None
        return cell
    
    @staticmethod
    def list_cells(
        notebook_id: int,
        user_id: int,
        cell_type: Optional[str] = None
    ) -> Tuple[Optional[List[Cell]], Optional[str]]:
        try:
            if not CellService._validate_user_owns_notebook(notebook_id, user_id):
                return None, "Sem permissão"
            
            query = Cell.query.filter_by(notebook_id=notebook_id, is_deleted=False)
            if cell_type:
                valid_types = ['python', 'sql', 'markdown', 'ai']
                if cell_type not in valid_types:
                    return None, f"cell_type inválido. Use um de: {valid_types}"
                query = query.filter_by(cell_type=cell_type)
            
            cells = query.order_by(Cell.position.asc()).all()
            return cells, None
        except Exception as e:
            return None, f"Erro ao listar: {str(e)}"
    
    @staticmethod
    def update_cell(
        cell_id: int,
        user_id: int,
        **kwargs
    ) -> Tuple[Optional[Cell], Optional[str]]:
        try:
            cell = CellService.get_cell(cell_id, user_id)
            if not cell:
                return None, "Célula não encontrada ou sem permissão"

            allowed_fields = {
                'content', 'cell_type', 'output', 'output_json', 'position',
                'is_hidden', 'tags', 'sql_connection'
            }

            content_changed = False

            for field, value in kwargs.items():
                if field not in allowed_fields:
                    continue

                if field == 'content':
                    if not value or len(value.strip()) == 0:
                        return None, "Conteúdo é obrigatório"
                    value = value.strip()
                    if value != cell.content:
                        content_changed = True
                        # Snapshot do conteúdo anterior antes de sobrescrever
                        snapshot = CellVersion(
                            cell_id=cell.id,
                            version=cell.version,
                            content=cell.content,
                            content_hash=cell.content_hash,
                            created_by=user_id,
                        )
                        db.session.add(snapshot)
                        cell.version += 1
                    cell.set_content(value)
                    continue

                if field == 'cell_type':
                    if value == 'code':
                        value = 'python'
                    valid_types = ['python', 'sql', 'markdown', 'ai']
                    if value not in valid_types:
                        return None, f"cell_type inválido. Use: {valid_types}"

                if field == 'position':
                    if not isinstance(value, int) or value < 0:
                        return None, "position inválida"

                if field == 'tags':
                    value = CellService._normalize_tags(value)

                setattr(cell, field, value)

            # updated_at gerenciado pelo onupdate do modelo — não setar manualmente
            db.session.commit()
            return cell, None

        except Exception as e:
            db.session.rollback()
            return None, f"Erro ao atualizar: {str(e)}"
    
    @staticmethod
    def move_cell(cell_id: int, user_id: int, direction: str) -> Tuple[bool, Optional[str]]:
        """
        Move uma célula para cima ou para baixo, trocando de posição com a célula vizinha.
        Usa índice na lista ordenada (não aritmética de posição) para ser robusto a lacunas.
        direction: 'up' ou 'down'
        """
        try:
            cell = CellService.get_cell(cell_id, user_id)
            if not cell:
                return False, "Célula não encontrada ou sem permissão"

            notebook_id = cell.notebook_id

            # Carrega todas as células ordenadas — ignora lacunas de posição
            cells = Cell.query.filter_by(
                notebook_id=notebook_id, is_deleted=False
            ).order_by(Cell.position.asc()).all()

            idx = next((i for i, c in enumerate(cells) if c.id == cell_id), None)
            if idx is None:
                return False, "Célula não encontrada na lista"

            if direction == 'up' and idx == 0:
                return False, "Já é a primeira célula"
            if direction == 'down' and idx == len(cells) - 1:
                return False, "Já é a última célula"

            neighbour = cells[idx - 1] if direction == 'up' else cells[idx + 1]

            # Troca as posições entre as duas células
            cell.position, neighbour.position = neighbour.position, cell.position

            # Renormaliza todas as posições do notebook (elimina lacunas acumuladas)
            updated = Cell.query.filter_by(
                notebook_id=notebook_id, is_deleted=False
            ).order_by(Cell.position.asc()).all()

            for new_idx, c in enumerate(updated):
                c.position = new_idx

            db.session.commit()
            return True, None

        except Exception as e:
            db.session.rollback()
            return False, f"Erro ao mover célula: {str(e)}"
    
    @staticmethod
    def delete_cell(cell_id: int, user_id: int) -> Tuple[bool, Optional[str]]:
        """
        Soft delete da célula e renormalização completa das posições do notebook.
        Garante sequência contígua 0, 1, 2... mesmo se já havia lacunas anteriores.
        """
        try:
            cell = CellService.get_cell(cell_id, user_id)
            if not cell:
                return False, "Célula não encontrada ou sem permissão"

            notebook_id = cell.notebook_id

            # Soft delete
            cell.soft_delete()
            db.session.flush()  # aplica o delete antes de consultar as restantes

            # Renormaliza todas as posições do zero (elimina lacunas acumuladas)
            remaining = Cell.query.filter_by(
                notebook_id=notebook_id, is_deleted=False
            ).order_by(Cell.position.asc()).all()

            for idx, c in enumerate(remaining):
                c.position = idx

            db.session.commit()
            return True, None

        except Exception as e:
            db.session.rollback()
            return False, f"Erro ao deletar: {str(e)}"
    
    @staticmethod
    def reorder_cells(
        notebook_id: int,
        user_id: int,
        cell_order: List[int]
    ) -> Tuple[bool, Optional[str]]:
        """
        Reordena as células (apenas as não deletadas).
        cell_order: lista de IDs de células na nova ordem.
        """
        try:
            if not CellService._validate_user_owns_notebook(notebook_id, user_id):
                return False, "Sem permissão"
            
            cells_dict = {}
            for cell_id in cell_order:
                cell = Cell.query.filter_by(
                    id=cell_id, notebook_id=notebook_id, is_deleted=False
                ).first()
                if not cell:
                    return False, f"Célula {cell_id} não encontrada ou deletada"
                cells_dict[cell_id] = cell
            
            for new_pos, cell_id in enumerate(cell_order):
                cells_dict[cell_id].position = new_pos
            
            db.session.commit()
            return True, None
        except Exception as e:
            db.session.rollback()
            return False, f"Erro ao reordenar: {str(e)}"
    
    @staticmethod
    def increment_execution_count(cell_id: int) -> bool:
        try:
            cell = Cell.query.get(cell_id)
            if cell and not cell.is_deleted:
                cell.execution_count += 1
                db.session.commit()
                return True
            return False
        except Exception as e:
            db.session.rollback()
            import logging
            logging.error(f"Failed to increment execution count for cell {cell_id}: {e}")
            return False