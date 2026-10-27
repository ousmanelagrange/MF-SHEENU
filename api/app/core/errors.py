"""Erreurs métier renvoyées au client sous la forme {code, message} (docs/03 §3.1)."""

from fastapi import HTTPException


class AppError(HTTPException):
    def __init__(self, status_code: int, code: str, message: str) -> None:
        super().__init__(status_code=status_code, detail={"code": code, "message": message})


def not_found(what: str = "Ressource") -> AppError:
    return AppError(404, "not_found", f"{what} introuvable.")


def forbidden(message: str = "Action non autorisée.") -> AppError:
    return AppError(403, "forbidden", message)


def out_of_scope() -> AppError:
    return AppError(403, "out_of_scope", "Cette personne est hors de votre périmètre.")


def conflict(code: str, message: str) -> AppError:
    return AppError(409, code, message)


def bad_request(code: str, message: str) -> AppError:
    return AppError(400, code, message)
