"""
Service: ExecutionHistoryService
Rastreamento e gerenciamento de execuções de células (histórico)
"""

from datetime import datetime
from typing import Optional, Dict, Any, List, Tuple

from app.database.db import db
from app.models.execution import Execution
from app.models.cell import Cell
from app.models.notebook import Notebook


class ExecutionService:
    """
    Serviço para operações com Execuções (histórico)
    
    Garante:
    - Estado de execução correto
    - Logging de erro/sucesso
    - Timing
    - Autorização
    """
    
    @staticmethod
    def _validate_user_owns_cell(cell_id: int, user_id: int) -> bool:
        """Validar se célula pertence a notebook do usuário"""
        cell = Cell.query.get(cell_id)
        if not cell:
            return False
        notebook = Notebook.query.get(cell.notebook_id)
        return notebook is not None and notebook.user_id == user_id
    
    @staticmethod
    def create_execution(
        cell_id: int,
        status: str = 'pending',
        execution_time: Optional[float] = None,
        logs: Optional[str] = None,
        error_message: Optional[str] = None,
        memory_used: Optional[float] = None
    ) -> Tuple[Optional[Execution], Optional[str]]:
        """
        Criar novo registro de execução
        
        Args:
            cell_id: ID da célula
            status: 'pending', 'running', 'success', 'error'
            execution_time: Tempo em segundos
            logs: Stdout
            error_message: Mensagem de erro
            memory_used: Memória em MB
        
        Returns:
            (Execution, None) ou (None, mensagem_erro)
        """
        
        try:
            # Validar célula existe
            cell = Cell.query.get(cell_id)
            if not cell:
                return None, "Célula não encontrada"
            
            # Validar status
            valid_statuses = ['pending', 'running', 'success', 'error']
            if status not in valid_statuses:
                return None, f"Status inválido. Deve ser um de: {valid_statuses}"
            
            # Criar
            execution = Execution(
                cell_id=cell_id,
                status=status,
                execution_time=execution_time,
                logs=logs,
                error_message=error_message,
                memory_used=memory_used,
                executed_at=datetime.utcnow()
            )
            
            db.session.add(execution)
            db.session.commit()
            
            return execution, None
        
        except Exception as e:
            db.session.rollback()
            return None, f"Erro ao criar execução: {str(e)}"
    
    @staticmethod
    def get_execution(
        execution_id: int,
        user_id: Optional[int] = None
    ) -> Optional[Execution]:
        """
        Buscar execução por ID
        
        Args:
            execution_id: ID da execução
            user_id: Se passar, valida permissão
        
        Returns:
            Execution ou None
        """
        
        execution = Execution.query.get(execution_id)
        
        if not execution:
            return None
        
        # Validar autorização se user_id fornecido
        if user_id:
            cell = Cell.query.get(execution.cell_id)
            if not cell:
                return None
            
            notebook = Notebook.query.get(cell.notebook_id)
            if not notebook or notebook.user_id != user_id:
                return None
        
        return execution
    
    @staticmethod
    def list_cell_executions(
        cell_id: int,
        user_id: int,
        limit: int = 50,
        page: int = 1
    ) -> Tuple[Optional[List[Execution]], Optional[str]]:
        """
        Listar histórico de execuções de uma célula
        
        Args:
            cell_id: ID da célula
            user_id: ID do usuário (validação)
            limit: Quantas retornar
            page: Página (1-indexed)
        
        Returns:
            (executions, None) ou (None, mensagem_erro)
        """
        
        try:
            # Validar que user é dono
            if not ExecutionHistoryService._validate_user_owns_cell(cell_id, user_id):
                return None, "Sem permissão"
            
            # Paginação
            pagination = Execution.query.filter_by(
                cell_id=cell_id
            ).order_by(
                Execution.executed_at.desc()
            ).paginate(
                page=page,
                per_page=limit,
                error_out=False
            )
            
            return pagination.items, None
        
        except Exception as e:
            return None, f"Erro ao listar: {str(e)}"
    
    @staticmethod
    def list_notebook_executions(
        notebook_id: int,
        user_id: int,
        limit: int = 100,
        page: int = 1
    ) -> Tuple[Optional[List[Execution]], Optional[int], Optional[int], Optional[str]]:
        """
        Listar todas as execuções de um notebook (paginado)
        
        Args:
            notebook_id: ID do notebook
            user_id: ID do usuário (validação)
            limit: Por página
            page: Página (1-indexed)
        
        Returns:
            (executions, total, pages, None) ou (None, None, None, mensagem_erro)
        """
        
        try:
            # Validar autorização
            notebook = Notebook.query.filter_by(
                id=notebook_id,
                user_id=user_id
            ).first()
            
            if not notebook:
                return None, None, None, "Notebook não encontrado ou sem permissão"
            
            # Query: executions de cells desse notebook
            pagination = db.session.query(Execution).join(Cell).filter(
                Cell.notebook_id == notebook_id
            ).order_by(
                Execution.executed_at.desc()
            ).paginate(
                page=page,
                per_page=limit,
                error_out=False
            )
            
            return pagination.items, pagination.total, pagination.pages, None
        
        except Exception as e:
            return None, None, None, f"Erro ao listar: {str(e)}"
    
    @staticmethod
    def update_execution(
        execution_id: int,
        user_id: int,
        **kwargs
    ) -> Tuple[Optional[Execution], Optional[str]]:
        """
        Atualizar execução (normalmente após término)
        
        Campos:
        - status
        - execution_time
        - logs
        - error_message
        - memory_used
        
        Args:
            execution_id: ID da execução
            user_id: ID do usuário (validação)
            **kwargs: Campos a atualizar
        
        Returns:
            (Execution, None) ou (None, mensagem_erro)
        """
        
        try:
            execution = ExecutionHistoryService.get_execution(execution_id, user_id)
            
            if not execution:
                return None, "Execução não encontrada ou sem permissão"
            
            allowed_fields = {
                'status', 'execution_time', 'logs',
                'error_message', 'memory_used'
            }
            
            for field, value in kwargs.items():
                if field not in allowed_fields:
                    continue
                
                # Validar status
                if field == 'status':
                    valid_statuses = ['pending', 'running', 'success', 'error']
                    if value not in valid_statuses:
                        return None, f"Status inválido"
                
                setattr(execution, field, value)
            
            db.session.commit()
            
            return execution, None
        
        except Exception as e:
            db.session.rollback()
            return None, f"Erro ao atualizar: {str(e)}"
    
    @staticmethod
    def get_execution_stats(
        cell_id: int,
        user_id: int
    ) -> Optional[Dict[str, Any]]:
        """
        Obter estatísticas de execução de uma célula
        
        Args:
            cell_id: ID da célula
            user_id: ID do usuário (validação)
        
        Returns:
            Dict com stats ou None
        """
        
        try:
            # Validar autorização
            if not ExecutionHistoryService._validate_user_owns_cell(cell_id, user_id):
                return None
            
            # Stats
            executions = Execution.query.filter_by(cell_id=cell_id).all()
            
            if not executions:
                return {
                    'cell_id': cell_id,
                    'total_executions': 0,
                    'successful': 0,
                    'errors': 0,
                    'avg_execution_time': None,
                    'last_execution': None
                }
            
            successful = sum(1 for e in executions if e.status == 'success')
            errors = sum(1 for e in executions if e.status == 'error')
            
            execution_times = [
                e.execution_time for e in executions
                if e.execution_time is not None
            ]
            avg_time = sum(execution_times) / len(execution_times) if execution_times else None
            
            last_execution = max(executions, key=lambda e: e.executed_at)
            
            return {
                'cell_id': cell_id,
                'total_executions': len(executions),
                'successful': successful,
                'errors': errors,
                'success_rate': (successful / len(executions) * 100) if executions else 0,
                'avg_execution_time': avg_time,
                'last_execution': last_execution.executed_at.isoformat(),
                'last_status': last_execution.status
            }
        
        except Exception as e:
            return None