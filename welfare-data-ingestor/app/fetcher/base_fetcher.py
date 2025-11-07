# base_fetcher.py
from abc import ABC, abstractmethod
from typing import List, Optional, Any

try:
    from app.dto.common_dto import CommonServiceDTO
except ImportError:
    pass

class BaseWelfareFetcher(ABC):
    """
    모든 Fetcher가 따라야 하는 추상 기본 클래스(인터페이스)
    """
    @abstractmethod
    def fetch_services_by_page(self, page_num: int, event_params: Optional[dict] = None) -> List[Any]:
        """
        API에서 데이터를 가져와 파싱한 후,
        DTO(CommonServiceDTO 또는 JobOpeningDTO)의 리스트로 반환해야 합니다.
        """
        pass
