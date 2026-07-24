from cryptography.fernet import Fernet, InvalidToken

from app.core.config import get_settings


class SecretService:
    @staticmethod
    def _fernet() -> Fernet:
        key = get_settings().integration_encryption_key.strip()
        if not key:
            raise RuntimeError(
                "INTEGRATION_ENCRYPTION_KEY is not configured. Generate one with: "
                'python -c "from cryptography.fernet import Fernet; '
                'print(Fernet.generate_key().decode())"'
            )
        try:
            return Fernet(key.encode("utf-8"))
        except (ValueError, TypeError) as exc:
            raise RuntimeError(
                "INTEGRATION_ENCRYPTION_KEY is invalid. It must be a Fernet key."
            ) from exc

    def encrypt(self, value: str) -> str:
        return self._fernet().encrypt(value.encode("utf-8")).decode("utf-8")

    def decrypt(self, value: str) -> str:
        try:
            return self._fernet().decrypt(value.encode("utf-8")).decode("utf-8")
        except InvalidToken as exc:
            raise RuntimeError(
                "The stored integration credential could not be decrypted."
            ) from exc


secret_service = SecretService()
