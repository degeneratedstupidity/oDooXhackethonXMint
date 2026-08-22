"""Field-level encryption for sensitive identity and bank details.

Values are encrypted with Fernet (AES-128-CBC + HMAC) before they reach the database and
decrypted on the way out, so the plaintext never sits in Postgres, in a backup, or in a
query log.

Only use these for values that never need to be filtered, sorted, or aggregated in SQL —
the database only ever sees ciphertext, so `WHERE pan_number = ...` cannot work. Bank
account numbers, IFSC, PAN and UAN all qualify: they are displayed and edited, never
searched on.
"""

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from django.db import models


def _fernet():
    return Fernet(settings.FIELD_ENCRYPTION_KEY.encode())


class EncryptedCharField(models.TextField):
    """A CharField whose value is stored encrypted at rest.

    Stored as text because ciphertext is longer than the plaintext and not a fixed size.
    `max_length` is still honoured for validation of the plaintext.
    """

    def __init__(self, *args, **kwargs):
        self.plain_max_length = kwargs.pop("max_length", None)
        super().__init__(*args, **kwargs)

    def deconstruct(self):
        name, path, args, kwargs = super().deconstruct()
        if self.plain_max_length is not None:
            kwargs["max_length"] = self.plain_max_length
        return name, path, args, kwargs

    def get_prep_value(self, value):
        if value is None or value == "":
            return value
        return _fernet().encrypt(str(value).encode()).decode()

    def from_db_value(self, value, expression, connection):
        if value is None or value == "":
            return value
        try:
            return _fernet().decrypt(value.encode()).decode()
        except InvalidToken:
            # Pre-existing plaintext, or a value written with a different key. Return it
            # as-is rather than crashing the whole response.
            return value
