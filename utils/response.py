from typing import Any, Optional, Dict


class ApiResponse:
    """统一的API响应结构"""

    @staticmethod
    def success(data: Any = None, message: Optional[str] = None) -> Dict:
        response = {
            "code": 0,
            "message": message,
            "data": data if data is not None else {}
        }
        return response

    @staticmethod
    def error(message: str, data: Any = None) -> Dict:
        response = {
            "code": -1,
            "message": message,
            "data": data
        }
        return response

    @staticmethod
    def custom(code: int, message: Optional[str] = None, data: Any = None) -> Dict:
        response = {
            "code": code,
            "message": message,
            "data": data if data is not None else {}
        }
        return response
