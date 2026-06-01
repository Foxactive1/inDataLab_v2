"""
Services Package (ETAPA 2)
Camada de lógica de negócio: validação, autorização, agregações

Services:
- NotebookService:   CRUD notebooks + stats
- CellService:       CRUD células + reordenação
- ExecutionService:  Histórico + stats execuções
- AIService:         Integração Groq API (ETAPA 1)
"""

from .notebook_service import NotebookService
from .cell_service import CellService
from .execution_service import ExecutionService
from .ai_service import AIService

__all__ = [
    'NotebookService',
    'CellService',
    'ExecutionService',
    'AIService'
]