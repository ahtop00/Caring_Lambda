# common_dto.py
from dataclasses import dataclass, field
from typing import Optional, List

@dataclass
class CommonServiceDTO:
    """
    API 소스에 관계없이 표준화된 복지 서비스 데이터 객체 (DTO)
    """

    service_id: str
    service_name: str
    service_summary: str
    detail_link: str

    # 공통 필드 (소스에 따라 채워짐)
    department_name: Optional[str] = None # 지자체: bizChrDeptNm, 중앙: jurMnofNm
    province: Optional[str] = None        # 지자체: ctpvNm, 중앙: None
    city_district: Optional[str] = None   # 지자체: sggNm, 중앙: None

    # 배열/날짜 필드
    target_audience: List[str] = field(default_factory=list) # trgterIndvdlArray
    life_cycle: List[str] = field(default_factory=list)      # lifeArray
    interest_theme: List[str] = field(default_factory=list)  # intrsThemaNmArray
    support_cycle: Optional[str] = None                      # sprtCycNm
    support_type: Optional[str] = None                       # srvPvsnNm
    application_method: Optional[str] = None                 # aplyMtdNm
    last_modified_date: Optional[str] = None # 지자체: lastModYmd, 중앙: svcfrstRegTs

    # DTO가 스스로 임베딩 텍스트를 생성하도록 만들면 더 깔끔합니다.
    def get_text_for_embedding(self) -> str:
        """EmbeddingService로 전달할 표준화된 텍스트를 생성합니다."""
        region = f"{self.province or ''} {self.city_district or ''}".strip()
        if not region:
            region = self.department_name or '중앙부처' # 지역 정보가 없으면 부처명

        return (
            f"이 복지 서비스는 {region}의 {', '.join(self.target_audience) or '정보 없음'}를 대상으로 합니다. "
            f"지원 주기는 {self.support_cycle or '정보 없음'}이며, {self.support_type or '정보 없음'} 형태로 제공됩니다. "
            f"신청은 {self.application_method or '정보 없음'} 방식으로 할 수 있습니다. "
            f"서비스명은 '{self.service_name}'이고, 주요 내용은 다음과 같습니다: {self.service_summary}"
        )
