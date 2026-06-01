# app/utils/auth_utils.py
from functools import wraps
from flask import request, jsonify
from flask_jwt_extended import get_jwt_identity, verify_jwt_in_request

def get_current_user_id() -> int:
    """Retorna o user_id do token JWT ou levanta exceção."""
    verify_jwt_in_request()
    return get_jwt_identity()

def jwt_required_optional(f):
    """Decorator que tenta extrair user_id, mas permite None (útil para rotas públicas)."""
    @wraps(f)
    def decorated(*args, **kwargs):
        try:
            verify_jwt_in_request()
            user_id = get_jwt_identity()
        except Exception:
            user_id = None
        return f(user_id=user_id, *args, **kwargs)
    return decorated