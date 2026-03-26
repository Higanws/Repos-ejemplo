"""Lectura de secretos (Bearer token) desde AWS Secrets Manager."""

from __future__ import annotations

import json

import boto3

_client = None


def _sm():
    global _client
    if _client is None:
        _client = boto3.client("secretsmanager")
    return _client


def get_bearer_token(secret_id: str) -> str:
    """
    Obtiene el token API. SecretString puede ser:
    - JSON con una de las claves: token, api_token, bearer, access_token, password
    - Texto plano (el token en sí)
    """
    resp = _sm().get_secret_value(SecretId=secret_id)
    raw = resp.get("SecretString") or ""
    raw = raw.strip()
    if not raw:
        raise ValueError(f"Secret vacío: {secret_id}")

    if raw.startswith("{"):
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return raw
        for key in ("token", "api_token", "bearer", "access_token", "password", "api_key"):
            v = data.get(key)
            if isinstance(v, str) and v.strip():
                return v.strip()
        raise ValueError(f"JSON en secreto sin clave de token conocida: {secret_id}")

    return raw
