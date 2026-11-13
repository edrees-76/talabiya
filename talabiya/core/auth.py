"""Password and secret-answer hashing (scrypt), kept in the settings table."""
from __future__ import annotations

import hashlib
import hmac
import secrets

from talabiya.core.repo import Repo, RepoError

_N, _R, _P = 2**14, 8, 1
MIN_PASSWORD = 4


def hash_secret(text: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(text.encode("utf-8"), salt=salt, n=_N, r=_R, p=_P, dklen=32)
    return f"scrypt${salt.hex()}${digest.hex()}"


def verify_secret(text: str, stored: str | None) -> bool:
    if not stored:
        return False
    try:
        algo, salt_hex, digest_hex = stored.split("$")
    except ValueError:
        return False
    if algo != "scrypt":
        return False
    digest = hashlib.scrypt(text.encode("utf-8"), salt=bytes.fromhex(salt_hex), n=_N, r=_R, p=_P, dklen=32)
    return hmac.compare_digest(digest.hex(), digest_hex)


def normalize_answer(answer: str) -> str:
    """Case, spacing and common Arabic letter variants do not matter in the secret answer."""
    a = " ".join(answer.split()).casefold()
    for src, dst in (("أ", "ا"), ("إ", "ا"), ("آ", "ا"), ("ة", "ه"), ("ى", "ي")):
        a = a.replace(src, dst)
    return a


def is_configured(repo: Repo) -> bool:
    return repo.get_setting("password_hash") is not None


def _check_password(password: str) -> None:
    if len(password) < MIN_PASSWORD:
        raise RepoError(f"أدخل كلمة سر من {MIN_PASSWORD} خانات على الأقل")


def setup(repo: Repo, password: str, question: str, answer: str) -> None:
    _check_password(password)
    if not question.strip():
        raise RepoError("اكتب السؤال السري")
    if not normalize_answer(answer):
        raise RepoError("اكتب إجابة السؤال السري")
    repo.set_setting("password_hash", hash_secret(password))
    repo.set_setting("secret_question", question.strip())
    repo.set_setting("secret_answer_hash", hash_secret(normalize_answer(answer)))


def check_password(repo: Repo, password: str) -> bool:
    return verify_secret(password, repo.get_setting("password_hash"))


def secret_question(repo: Repo) -> str:
    return repo.get_setting("secret_question", "") or ""


def reset_with_answer(repo: Repo, answer: str, new_password: str) -> None:
    if not verify_secret(normalize_answer(answer), repo.get_setting("secret_answer_hash")):
        raise RepoError("الإجابة غير مطابقة. حاول مرة أخرى")
    _check_password(new_password)
    repo.set_setting("password_hash", hash_secret(new_password))


def change_password(repo: Repo, current: str, new_password: str) -> None:
    if not check_password(repo, current):
        raise RepoError("كلمة السر الحالية غير صحيحة")
    _check_password(new_password)
    repo.set_setting("password_hash", hash_secret(new_password))


def change_secret(repo: Repo, current_password: str, question: str, answer: str) -> None:
    if not check_password(repo, current_password):
        raise RepoError("كلمة السر الحالية غير صحيحة")
    if not question.strip() or not normalize_answer(answer):
        raise RepoError("اكتب السؤال السري وإجابته")
    repo.set_setting("secret_question", question.strip())
    repo.set_setting("secret_answer_hash", hash_secret(normalize_answer(answer)))
