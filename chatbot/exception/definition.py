# chatbot/exception/definition.py

class AppError(Exception):
    """비즈니스 로직에서 발생하는 기본 커스텀 예외"""
    def __init__(self, status_code: int, message: str, detail: str = None):
        self.status_code = status_code
        self.message = message
        self.detail = detail
