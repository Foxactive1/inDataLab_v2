"""Identidade do usuário nas rotas privadas: nunca usar IDs fixos."""
from flask_jwt_extended import get_jwt_identity, verify_jwt_in_request


def get_current_user_id():
    verify_jwt_in_request()
    return int(get_jwt_identity())
