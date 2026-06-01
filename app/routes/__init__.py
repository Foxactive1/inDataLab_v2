# routes/__init__.py
from .notebooks_blueprint import notebooks_bp
from .cells_blueprint import cells_bp
from .executions_blueprint import executions_bp
from .copilot_blueprint import bp as copilot_bp
from .datasets_blueprint import bp as datasets_bp   # <-- ADICIONE ESTA LINHA

__all__ = [
    'notebooks_bp',
    'cells_bp',
    'executions_bp',
    'copilot_bp',
    'datasets_bp'   # <-- ADICIONE AQUI TAMBÉM
]