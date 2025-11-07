# base_fetcher.py
from abc import ABC, abstractmethod
from typing import List, Optional
from common_dto import CommonServiceDTO

class BaseWelfareFetcher(ABC):
    """
    모든 Fetcher가 따라야 하는 추상 기본 클래스(인터페이스)
    """
    @abstractmethod
    def fetch_services_by_page(self, page_num: int, event_params: Optional[dict] = None) -> List[CommonServiceDTO]:
        """
        API에서 데이터를 가져와 파싱한 후,
        공통 DTO(CommonServiceDTO)의 리스트로 반환해야 합니다.
        """
        pass
