import base64
import hashlib
import hmac
import json
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional, Tuple
from urllib.parse import parse_qsl, unquote_plus

from ..core.config import settings


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("utf-8")


def _b64url_decode(data: str) -> bytes:
    padding = '=' * (-len(data) % 4)
    return base64.urlsafe_b64decode((data + padding).encode("utf-8"))


def create_session_token(telegram_id: str, expires_in_seconds: int = 60 * 60 * 24 * 7) -> str:
    """Создает JWT (HS256) на стандартной библиотеке для хранения в cookie."""
    header = {"alg": "HS256", "typ": "JWT"}
    now = datetime.now(timezone.utc)
    payload = {
        "sub": telegram_id,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=expires_in_seconds)).timestamp()),
    }

    header_b64 = _b64url_encode(json.dumps(header, separators=(",", ":")).encode("utf-8"))
    payload_b64 = _b64url_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signing_input = f"{header_b64}.{payload_b64}".encode("utf-8")
    signature = hmac.new(settings.secret_key.encode("utf-8"), signing_input, hashlib.sha256).digest()
    signature_b64 = _b64url_encode(signature)
    return f"{header_b64}.{payload_b64}.{signature_b64}"


def verify_session_token(token: str) -> Optional[Dict[str, Any]]:
    """Проверяет JWT и возвращает payload или None, если токен недействителен."""
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return None
        header_b64, payload_b64, signature_b64 = parts
        signing_input = f"{header_b64}.{payload_b64}".encode("utf-8")
        expected_sig = hmac.new(settings.secret_key.encode("utf-8"), signing_input, hashlib.sha256).digest()
        actual_sig = _b64url_decode(signature_b64)

        if not hmac.compare_digest(expected_sig, actual_sig):
            return None

        payload = json.loads(_b64url_decode(payload_b64))
        # Проверка exp
        exp = int(payload.get("exp", 0))
        if datetime.now(timezone.utc).timestamp() > exp:
            return None
        return payload
    except Exception:
        return None


def _parse_init_data(init_data: str) -> Tuple[Dict[str, str], Optional[Dict[str, Any]]]:
    """Парсит строку initData в словарь и вытаскивает user как dict."""
    fields: Dict[str, str] = {}
    user_obj: Optional[Dict[str, Any]] = None
    # init_data — URL query string вида: key=value&user=%7B...%7D
    for key, value in parse_qsl(init_data, keep_blank_values=True):
        fields[key] = value
    if 'user' in fields:
        try:
            user_obj = json.loads(fields['user'])
        except Exception:
            user_obj = None
    return fields, user_obj


def verify_telegram_init_data(init_data: str, max_age_seconds: int = 24 * 60 * 60) -> Tuple[bool, Optional[Dict[str, Any]], Optional[str]]:
    """
    Проверяет подпись initData согласно документации Telegram WebApp.
    Возвращает кортеж: (ok, user_obj, error_message)
    """
    try:
        fields, user_obj = _parse_init_data(init_data)
        if 'hash' not in fields:
            return False, None, 'Отсутствует hash в initData'

        received_hash = fields['hash']
        # Готовим data_check_string: сортированные key=value (кроме hash), через '\n'
        data_pairs = []
        for k, v in fields.items():
            if k == 'hash':
                continue
            data_pairs.append(f"{k}={v}")
        data_pairs.sort()
        data_check_string = "\n".join(data_pairs)

        # secret_key = HMAC_SHA256("WebAppData", bot_token)
        secret_key = hmac.new(b"WebAppData", settings.telegram_bot_token.encode("utf-8"), hashlib.sha256).digest()
        computed_hash = hmac.new(secret_key, data_check_string.encode("utf-8"), hashlib.sha256).hexdigest()

        if not hmac.compare_digest(computed_hash, received_hash):
            return False, None, 'Неверная подпись initData'

        # Проверяем возраст auth_date (если присутствует)
        if 'auth_date' in fields:
            try:
                auth_ts = int(fields['auth_date'])
                now_ts = int(datetime.now(timezone.utc).timestamp())
                if now_ts - auth_ts > max_age_seconds:
                    return False, None, 'Срок действия initData истек'
            except Exception:
                # Если не удалось распарсить — не валидируем по времени
                pass

        return True, user_obj, None
    except Exception as e:
        return False, None, f'Ошибка проверки initData: {str(e)}'


