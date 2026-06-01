"""
Service: NotebookService
CRUD de notebooks com validação, autorização e serialização segura
Compatível com model Notebook (KernelType enum)
"""

from datetime import datetime
from typing import Optional, Dict, Any, List, Tuple

from app.database.db import db
from app.models.notebook import Notebook, KernelType
from app.models.cell import Cell


class NotebookService:
    """
    Serviço para operações com Notebooks
    """
    
    @staticmethod
    def create_notebook(
        user_id: int,
        title: str,
        description: Optional[str] = None,
        is_public: bool = False,
        kernel_type: str = 'python3',
        default_sql_connection: Optional[str] = None
    ) -> Tuple[Optional[Notebook], Optional[str]]:
        """
        Criar novo notebook.
        kernel_type deve ser 'python3', 'r' ou 'sql'.
        """
        try:
            if not title or len(title.strip()) == 0:
                return None, "Título é obrigatório"
            if len(title) > 255:
                return None, "Título muito longo (máx 255 caracteres)"
            
            # Converte string para Enum
            try:
                kernel_enum = KernelType(kernel_type)
            except ValueError:
                return None, f"Tipo de kernel inválido: {kernel_type}. Use 'python3', 'r' ou 'sql'."
            
            notebook = Notebook(
                user_id=user_id,
                title=title.strip(),
                description=description.strip() if description else None,
                is_public=is_public,
                kernel_type=kernel_enum,
                default_sql_connection=default_sql_connection
            )
            db.session.add(notebook)
            db.session.commit()
            return notebook, None
        except Exception as e:
            db.session.rollback()
            return None, f"Erro ao criar notebook: {str(e)}"
    
    @staticmethod
    def get_notebook(
        notebook_id: int,
        user_id: Optional[int] = None
    ) -> Optional[Notebook]:
        """Buscar notebook por ID, com validação opcional de propriedade."""
        notebook = Notebook.query.get(notebook_id)
        if not notebook:
            return None
        if user_id and notebook.user_id != user_id:
            return None
        return notebook
    
    @staticmethod
    def list_notebooks(
        user_id: int,
        is_archived: Optional[bool] = None,
        page: int = 1,
        per_page: int = 20
    ) -> Tuple[List[Dict[str, Any]], int, int]:
        """
        Listar notebooks do usuário (paginado).
        Retorna lista de dicionários serializados (seguro para JSON).
        """
        try:
            query = Notebook.query.filter_by(user_id=user_id)
            if is_archived is not None:
                query = query.filter_by(is_archived=is_archived)
            
            pagination = query.order_by(
                Notebook.created_at.desc()
            ).paginate(page=page, per_page=per_page, error_out=False)
            
            notebooks = pagination.items
            total = pagination.total
            pages = pagination.pages
            
            # Serialização manual segura
            result = []
            for nb in notebooks:
                # Contagem de células ativas (não deletadas) via relationship
                cell_count = nb.cells.count()  # já filtra is_deleted=False
                
                result.append({
                    'id': nb.id,
                    'user_id': nb.user_id,
                    'title': nb.title,
                    'description': nb.description,
                    'is_public': nb.is_public,
                    'is_archived': nb.is_archived,
                    'kernel_type': nb.kernel_type.value if nb.kernel_type else None,
                    'default_sql_connection': nb.default_sql_connection,
                    'created_at': nb.created_at.isoformat() if nb.created_at else None,
                    'updated_at': nb.updated_at.isoformat() if nb.updated_at else None,
                    'cell_count': cell_count,
                })
            return result, total, pages
        except Exception as e:
            db.session.rollback()
            raise
    
    @staticmethod
    def update_notebook(
        notebook_id: int,
        user_id: int,
        **kwargs
    ) -> Tuple[Optional[Notebook], Optional[str]]:
        """
        Atualizar notebook.
        Campos permitidos: title, description, is_public, is_archived, kernel_type, default_sql_connection.
        """
        try:
            notebook = Notebook.query.get(notebook_id)
            if not notebook:
                return None, "Notebook não encontrado"
            if notebook.user_id != user_id:
                return None, "Sem permissão"
            
            allowed_fields = {
                'title', 'description', 'is_public',
                'is_archived', 'kernel_type', 'default_sql_connection'
            }
            
            for field, value in kwargs.items():
                if field not in allowed_fields:
                    continue
                
                if field == 'title':
                    if not value or len(value.strip()) == 0:
                        return None, "Título é obrigatório"
                    if len(value) > 255:
                        return None, "Título muito longo"
                    value = value.strip()
                
                if field == 'description' and value:
                    value = value.strip()
                
                if field == 'kernel_type':
                    try:
                        value = KernelType(value)
                    except ValueError:
                        return None, f"Tipo de kernel inválido: {value}. Use 'python3', 'r' ou 'sql'."
                
                setattr(notebook, field, value)
            
            notebook.updated_at = datetime.utcnow()
            db.session.commit()
            return notebook, None
        except Exception as e:
            db.session.rollback()
            return None, f"Erro ao atualizar: {str(e)}"
    
    @staticmethod
    def delete_notebook(
        notebook_id: int,
        user_id: int
    ) -> Tuple[bool, Optional[str]]:
        """Hard delete do notebook (cascade deleta cells, executions, datasets, etc)."""
        try:
            notebook = Notebook.query.get(notebook_id)
            if not notebook:
                return False, "Notebook não encontrado"
            if notebook.user_id != user_id:
                return False, "Sem permissão"
            db.session.delete(notebook)
            db.session.commit()
            return True, None
        except Exception as e:
            db.session.rollback()
            return False, f"Erro ao deletar: {str(e)}"
    
    @staticmethod
    def get_notebook_stats(notebook_id: int, user_id: int) -> Optional[Dict[str, Any]]:
        """
        Estatísticas do notebook.
        Conta células dos tipos: python, sql, markdown, ai (ignora 'code' obsoleto).
        """
        notebook = NotebookService.get_notebook(notebook_id, user_id)
        if not notebook:
            return None
        
        # Células totais (não deletadas) – usamos a relationship que já filtra is_deleted=False
        total_cells = notebook.cells.count()
        
        # Contagem por tipo
        python_count = notebook.cells.filter_by(cell_type='python').count()
        sql_count = notebook.cells.filter_by(cell_type='sql').count()
        markdown_count = notebook.cells.filter_by(cell_type='markdown').count()
        ai_count = notebook.cells.filter_by(cell_type='ai').count()
        
        # Total de execuções
        from app.models.execution import Execution
        execution_count = db.session.query(Execution).join(Cell).filter(
            Cell.notebook_id == notebook_id,
            Cell.is_deleted == False
        ).count()
        
        return {
            'notebook_id': notebook_id,
            'total_cells': total_cells,
            'python_cells': python_count,
            'sql_cells': sql_count,
            'markdown_cells': markdown_count,
            'ai_cells': ai_count,
            'total_executions': execution_count,
            'created_at': notebook.created_at.isoformat() if notebook.created_at else None,
            'updated_at': notebook.updated_at.isoformat() if notebook.updated_at else None,
        }