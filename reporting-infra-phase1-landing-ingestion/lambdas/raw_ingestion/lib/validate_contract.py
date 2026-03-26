"""
Validación estricta contra contratos JSON en contracts/*.contract.json.
Sin dependencias externas (compatible con ZIP Lambda actual).
"""

from __future__ import annotations

import csv
import io
import json
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parent.parent


def _load_contract(name: str) -> dict[str, Any]:
    path = _ROOT / "contracts" / f"{name}.contract.json"
    if not path.is_file():
        raise FileNotFoundError(f"Contrato no encontrado: {path}")
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def _check_type(value: Any, expected: str, path: str) -> str | None:
    if value is None:
        return f"{path}: valor nulo no permitido"
    if expected == "string":
        if isinstance(value, str):
            return None
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return f"{path}: se esperaba string (texto), llegó número"
        return f"{path}: se esperaba string, llegó {type(value).__name__}"
    if expected == "number":
        if isinstance(value, bool):
            return f"{path}: se esperaba number, llegó bool"
        if isinstance(value, (int, float)):
            return None
        return f"{path}: se esperaba number, llegó {type(value).__name__}"
    if expected == "integer":
        if isinstance(value, bool):
            return f"{path}: se esperaba integer, llegó bool"
        if isinstance(value, int) and not isinstance(value, bool):
            return None
        return f"{path}: se esperaba integer, llegó {type(value).__name__}"
    if expected == "boolean":
        if not isinstance(value, bool):
            return f"{path}: se esperaba boolean, llegó {type(value).__name__}"
        return None
    return f"{path}: tipo desconocido en contrato: {expected}"


def validate_trade_event_payload(payload: Any) -> tuple[bool, str]:
    """
    Valida un objeto o lista de objetos trade_event.
    Retorna (ok, mensaje_error).
    """
    contract = _load_contract("trade_event")
    if contract.get("format") != "json":
        return False, "contrato trade_event debe ser format=json"

    if isinstance(payload, list):
        for i, item in enumerate(payload):
            ok, msg = _validate_json_object(item, contract, f"[{i}]")
            if not ok:
                return False, msg
        return True, ""

    if isinstance(payload, dict):
        return _validate_json_object(payload, contract, "")

    return False, f"payload debe ser objeto o lista de objetos, llegó {type(payload).__name__}"


def _validate_json_object(obj: Any, contract: dict[str, Any], prefix: str) -> tuple[bool, str]:
    if not isinstance(obj, dict):
        return False, f"{prefix} se esperaba objeto JSON, llegó {type(obj).__name__}"

    req = list(contract.get("required") or [])
    props = contract.get("properties") or {}
    additional = contract.get("additionalProperties", True)

    for k in req:
        if k not in obj:
            return False, f"{prefix} falta campo obligatorio: {k}"

    if not additional:
        allowed = set(props.keys())
        for k in obj:
            if k not in allowed:
                return False, f"{prefix} campo no permitido (additionalProperties=false): {k}"

    for key, spec in props.items():
        if key not in obj:
            continue
        expected = spec.get("type", "string")
        err = _check_type(obj[key], expected, f"{prefix}.{key}" if prefix else key)
        if err:
            return False, err

    return True, ""


def _parse_bool_cell(s: str) -> bool | None:
    t = s.strip().lower()
    if t in ("true", "1", "yes"):
        return True
    if t in ("false", "0", "no"):
        return False
    return None


def _parse_number_cell(s: str) -> float | None:
    s = s.strip()
    if not s:
        return None
    try:
        return float(s)
    except ValueError:
        return None


def validate_price_history_csv(text: str) -> tuple[bool, str]:
    """
    Valida CSV completo (header + filas). Tipos: strings no vacíos donde aplica;
    number/boolean parseables desde texto.
    """
    contract = _load_contract("price_history")
    if contract.get("format") != "csv":
        return False, "contrato price_history debe ser format=csv"

    delim = contract.get("delimiter", ",")
    req_cols = list(contract.get("required_columns") or [])
    col_types = dict(contract.get("column_types") or {})

    f = io.StringIO(text)
    reader = csv.DictReader(f, delimiter=delim)
    if reader.fieldnames is None:
        return False, "CSV sin cabecera"

    header = [h.strip() for h in reader.fieldnames]
    for c in req_cols:
        if c not in header:
            return False, f"falta columna obligatoria en header: {c}"

    for ri, row in enumerate(reader):
        for c in req_cols:
            if c not in row or row[c] is None:
                return False, f"fila {ri + 2}: falta valor para columna {c}"
            raw = str(row[c]).strip()
            typ = col_types.get(c, "string")
            if typ == "string":
                if raw == "":
                    return False, f"fila {ri + 2}: {c} debe ser texto no vacío"
            elif typ == "number":
                if _parse_number_cell(raw) is None:
                    return False, f"fila {ri + 2}: {c} debe ser numérico, valor={raw!r}"
            elif typ == "boolean":
                if _parse_bool_cell(raw) is None:
                    return False, f"fila {ri + 2}: {c} debe ser boolean (true/false), valor={raw!r}"

    return True, ""
