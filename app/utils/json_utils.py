"""
JSON Sanitizer
Converte objetos incompatíveis com JSON
para tipos serializáveis.
"""

import math
from datetime import datetime, date

try:
    import numpy as np
except ImportError:
    np = None

try:
    import pandas as pd
except ImportError:
    pd = None


def sanitize_json(obj):

    if obj is None:
        return None

    # dict
    if isinstance(obj, dict):
        return {
            str(k): sanitize_json(v)
            for k, v in obj.items()
        }

    # list / tuple
    if isinstance(obj, (list, tuple)):
        return [
            sanitize_json(v)
            for v in obj
        ]

    # datetime
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()

    # pandas
    if pd is not None:

        try:
            if pd.isna(obj):
                return None
        except Exception:
            pass

        if isinstance(obj, pd.Timestamp):
            return obj.isoformat()

    # numpy integer
    if np is not None:

        if isinstance(
            obj,
            (
                np.int64,
                np.int32,
                np.int16,
                np.int8
            )
        ):
            return int(obj)

        if isinstance(
            obj,
            (
                np.float64,
                np.float32,
                np.float16
            )
        ):
            if math.isnan(obj):
                return None

            return float(obj)

        if isinstance(obj, np.bool_):
            return bool(obj)

    # float python
    if isinstance(obj, float):

        if math.isnan(obj):
            return None

        if math.isinf(obj):
            return None

        return float(obj)

    return obj