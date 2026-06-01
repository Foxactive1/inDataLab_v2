"""
InDataLab - API Utilities (Refatorado)
Response Handling, Validation and Serialization
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple, Type, Union

from app.utils.json_utils import sanitize_json
# ============================================================================
# API RESPONSE
# ============================================================================

class APIResponse:
    """Standard API Response Handler"""

    @staticmethod
    def _utc_now() -> str:
        """Retorna timestamp UTC atual no formato ISO 8601."""
        return datetime.now(timezone.utc).isoformat()

    @classmethod
    def build(
        cls,
        success: bool,
        status_code: int,
        data: Any = None,
        message: Optional[str] = None,
        error: Optional[str] = None,
        details: Optional[Dict] = None,
        meta: Optional[Dict] = None,
    ) -> Tuple[Dict, int]:
        response = {
            "success": success,
            "status_code": status_code,
            "timestamp": cls._utc_now(),
        }

        if success:
            if data is not None:
                response["data"] = data
            if message:
                response["message"] = message
        else:
            if error:
                response["error"] = error
            if details:
                response["details"] = details

        if meta:
            response["meta"] = meta

        return response, status_code

    # --- Success responses ---
    @classmethod
    def success(
        cls,
        data: Any = None,
        message: str = "Operação realizada com sucesso",
        status_code: int = 200,
        meta: Optional[Dict] = None,
    ) -> Tuple[Dict, int]:
        return cls.build(
            success=True,
            status_code=status_code,
            data=data,
            message=message,
            meta=meta,
        )

    @classmethod
    def created(
        cls, data: Any = None, message: str = "Recurso criado com sucesso"
    ) -> Tuple[Dict, int]:
        return cls.success(data=data, message=message, status_code=201)

    @classmethod
    def deleted(cls, message: str = "Recurso removido com sucesso") -> Tuple[Dict, int]:
        return cls.success(data=None, message=message, status_code=200)

    # --- Error responses ---
    @classmethod
    def error(
        cls,
        error: str,
        status_code: int = 400,
        details: Optional[Dict] = None,
    ) -> Tuple[Dict, int]:
        return cls.build(
            success=False,
            status_code=status_code,
            error=error,
            details=details,
        )

    @classmethod
    def bad_request(cls, message: str = "Requisição inválida") -> Tuple[Dict, int]:
        return cls.error(message, 400)

    @classmethod
    def unauthorized(cls, message: str = "Não autorizado") -> Tuple[Dict, int]:
        return cls.error(message, 401)

    @classmethod
    def forbidden(cls, message: str = "Acesso negado") -> Tuple[Dict, int]:
        return cls.error(message, 403)

    @classmethod
    def not_found(cls, resource: str = "Recurso") -> Tuple[Dict, int]:
        return cls.error(f"{resource} não encontrado", 404)

    @classmethod
    def conflict(cls, message: str = "Conflito de dados") -> Tuple[Dict, int]:
        return cls.error(message, 409)

    @classmethod
    def validation_error(cls, errors: Dict[str, Any]) -> Tuple[Dict, int]:
        return cls.error(
            error="Erro de validação",
            status_code=422,
            details={"validation_errors": errors},
        )

    @classmethod
    def internal_error(cls, message: str = "Erro interno do servidor") -> Tuple[Dict, int]:
        return cls.error(message, 500)


# ============================================================================
# VALIDATORS
# ============================================================================

class ValidateRequest:
    """Request Validation Utilities"""

    @staticmethod
    def required_fields(data: Dict, fields: List[str]) -> Optional[Tuple[Dict, int]]:
        missing = [f for f in fields if not data.get(f) and data.get(f) != 0]
        if missing:
            return APIResponse.validation_error({"missing_fields": missing})
        return None

    @staticmethod
    def field_type(
        data: Dict,
        field: str,
        expected_type: Type,
        allow_none: bool = False,
    ) -> Optional[Tuple[Dict, int]]:
        if field not in data:
            return None
        value = data[field]
        if value is None and allow_none:
            return None
        if not isinstance(value, expected_type):
            return APIResponse.validation_error(
                {field: f"Deve ser do tipo {expected_type.__name__}"}
            )
        return None

    @staticmethod
    def field_length(
        data: Dict,
        field: str,
        min_length: Optional[int] = None,
        max_length: Optional[int] = None,
    ) -> Optional[Tuple[Dict, int]]:
        if field not in data:
            return None
        value = str(data[field])
        errors = {}
        if min_length is not None and len(value) < min_length:
            errors[field] = f"Mínimo de {min_length} caracteres"
        if max_length is not None and len(value) > max_length:
            errors[field] = f"Máximo de {max_length} caracteres"
        return APIResponse.validation_error(errors) if errors else None


# ============================================================================
# SERIALIZERS
# ============================================================================

class Serializer:
    """Model Serialization Utilities (SQLAlchemy compatible)"""

    @staticmethod
    def model(model_obj: Any, exclude: Optional[List[str]] = None) -> Dict:
        exclude = set(exclude or [])

        # Prioriza método to_dict se existir
        if hasattr(model_obj, "to_dict") and callable(model_obj.to_dict):
            data = model_obj.to_dict()
            if exclude:
                return {k: v for k, v in data.items() if k not in exclude}
            return data

        # Fallback para SQLAlchemy
        result = {}
        for column in model_obj.__table__.columns:
            if column.name in exclude:
                continue
            value = getattr(model_obj, column.name)
            if isinstance(value, datetime):
                value = value.isoformat()
            result[column.name] = value
        return result

    @staticmethod
    def models(models: List[Any], exclude: Optional[List[str]] = None) -> List[Dict]:
        return [Serializer.model(m, exclude) for m in models]


# ============================================================================
# BACKWARD COMPATIBILITY
# ============================================================================

def serialize_model(model_obj: Any, exclude: Optional[List[str]] = None) -> Dict:
    """Compatibilidade com código legado"""
    return Serializer.model(model_obj, exclude)


def serialize_models(models: List[Any], exclude: Optional[List[str]] = None) -> List[Dict]:
    """Compatibilidade com código legado"""
    return Serializer.models(models, exclude)