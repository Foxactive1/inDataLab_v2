import os
from flask import current_app

def resolve_upload_path(relative_path: str) -> str:
    """Converte caminho relativo de upload para absoluto"""
    if not relative_path:
        return None
    if os.path.isabs(relative_path):
        return relative_path
    return os.path.join(current_app.config['UPLOAD_FOLDER'], relative_path)

def get_relative_path_from_upload(abs_path: str) -> str:
    """Extrai caminho relativo a partir de um caminho absoluto dentro de UPLOAD_FOLDER"""
    base = current_app.config['UPLOAD_FOLDER']
    if abs_path.startswith(base):
        return os.path.relpath(abs_path, base)
    return abs_path  # fallback