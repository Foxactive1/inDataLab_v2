from flask import Blueprint, request, jsonify
from flask_jwt_extended import create_access_token
from datetime import datetime, timezone

from app.database.db import db
from app.models.user import User

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')


@auth_bp.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    if not data:
        return jsonify({"error": "Dados não fornecidos"}), 400

    name = data.get('name', '').strip()
    email = data.get('email', '').strip().lower()
    password = data.get('password', '')

    if not name or not email or not password:
        return jsonify({"error": "Nome, e-mail e senha são obrigatórios"}), 400
    if len(password) < 6:
        return jsonify({"error": "A senha deve ter pelo menos 6 caracteres"}), 400

    if User.query.filter_by(email=email).first():
        return jsonify({"error": "E-mail já cadastrado"}), 409

    user = User(
        name=name,
        email=email,
        is_active=True,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc)
    )
    user.set_password(password)   # usa werkzeug

    try:
        db.session.add(user)
        db.session.commit()
        return jsonify({
            "message": "Usuário criado com sucesso",
            "user": user.to_dict()
        }), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"Erro ao registrar: {str(e)}"}), 500


@auth_bp.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    if not data:
        return jsonify({"error": "Dados não fornecidos"}), 400

    email = data.get('email', '').strip().lower()
    password = data.get('password', '')

    if not email or not password:
        return jsonify({"error": "E-mail e senha são obrigatórios"}), 400

    user = User.query.filter_by(email=email).first()
    if not user or not user.check_password(password):
        return jsonify({"error": "Credenciais inválidas"}), 401

    if not user.is_active:
        return jsonify({"error": "Usuário inativo"}), 403

    access_token = create_access_token(identity=str(user.id))  # JWT identity
    return jsonify({
        "access_token": access_token,
        "user": user.to_dict()
    }), 200