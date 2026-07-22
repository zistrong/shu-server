"""密码哈希（标准库 PBKDF2）。"""
import hashlib
import secrets


def hash_pw(password, salt=None):
    salt = salt or secrets.token_hex(16)
    h = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"),
                            bytes.fromhex(salt), 120_000).hex()
    return salt, h


def verify_pw(password, salt, expected):
    _, h = hash_pw(password, salt)
    return secrets.compare_digest(h, expected)
