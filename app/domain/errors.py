class AppError(Exception):
    def __init__(self, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class UnauthorizedError(AppError):
    def __init__(self, message: str = "No autenticado") -> None:
        super().__init__(message, 401)


class ForbiddenError(AppError):
    def __init__(self, message: str = "No autorizado") -> None:
        super().__init__(message, 403)


class NotFoundError(AppError):
    def __init__(self, message: str = "No encontrado") -> None:
        super().__init__(message, 404)
