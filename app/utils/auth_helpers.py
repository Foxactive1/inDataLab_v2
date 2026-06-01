from functools import wraps
from flask import jsonify
from flask_jwt_extended import verify_jwt_in_request, get_jwt_identity

def jwt_required_optional(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        try:
            verify_jwt_in_request(optional=True)
            return f(*args, **kwargs)
        except Exception:
            return f(*args, **kwargs)
    return decorated

def get_current_user_id():
    """
    Retorna o user_id do token JWT.
    Se não houver token (ex: desenvolvimento), pode retornar None ou 1?
    Para produção, sempre exigir token.
    """
    try:
        verify_jwt_in_request()
        user_id = get_jwt_identity()
        return int(user_id)
    except Exception:
        # Em desenvolvimento, você pode retornar um ID fixo (1) APENAS para testes
        # Em produção, levante uma exceção ou retorne None
        return 1  # APENAS PARA MVP - REMOVER EM PRODUÇÃO