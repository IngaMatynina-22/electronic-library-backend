"""Domain exceptions returned to the GUI layer."""

from __future__ import annotations


class LibraryError(Exception):
    """Base error for the library backend."""

    def __init__(self, message: str, *, code: str = "library_error") -> None:
        super().__init__(message)
        self.message = message
        self.code = code


class NotFoundError(LibraryError):
    def __init__(self, message: str = "Record not found") -> None:
        super().__init__(message, code="not_found")


class ValidationError(LibraryError):
    def __init__(self, message: str) -> None:
        super().__init__(message, code="validation_error")


class FileAccessError(LibraryError):
    def __init__(self, message: str = "File is not accessible") -> None:
        super().__init__(message, code="file_access_error")


class UnsupportedFormatError(LibraryError):
    def __init__(self, message: str = "Unsupported file format") -> None:
        super().__init__(message, code="unsupported_format")


class CorruptedFileError(LibraryError):
    def __init__(self, message: str = "File is corrupted or unreadable") -> None:
        super().__init__(message, code="corrupted_file")


class EncryptedFileError(LibraryError):
    def __init__(self, message: str = "File is encrypted or password-protected") -> None:
        super().__init__(message, code="encrypted_file")


class DuplicateBookError(LibraryError):
    def __init__(self, message: str = "Book already exists in the library", *, book_id: int | None = None) -> None:
        super().__init__(message, code="duplicate_book")
        self.book_id = book_id


class DiskSpaceError(LibraryError):
    def __init__(self, message: str = "Not enough disk space") -> None:
        super().__init__(message, code="disk_space_error")


class TransactionError(LibraryError):
    def __init__(self, message: str = "Database transaction failed") -> None:
        super().__init__(message, code="transaction_error")


class BackupError(LibraryError):
    def __init__(self, message: str = "Backup operation failed") -> None:
        super().__init__(message, code="backup_error")


class ScannedPdfWarning(LibraryError):
    """Raised as a soft signal when PDF has no extractable text layer."""

    def __init__(self, message: str = "PDF appears to be scanned (no text layer)") -> None:
        super().__init__(message, code="scanned_pdf")


class AuthenticationError(LibraryError):
    def __init__(self, message: str = "Invalid username or password") -> None:
        super().__init__(message, code="authentication_error")


class UnauthorizedError(LibraryError):
    def __init__(self, message: str = "Authentication required") -> None:
        super().__init__(message, code="unauthorized")


class UserExistsError(LibraryError):
    def __init__(self, message: str = "Username already taken") -> None:
        super().__init__(message, code="user_exists")
