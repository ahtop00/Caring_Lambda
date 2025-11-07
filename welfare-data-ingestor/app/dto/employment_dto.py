# -*- coding: utf-8 -*-
from dataclasses import dataclass, field
from typing import Optional, List

@dataclass
class JobOpeningDTO:
    """
    '구인 정보' 데이터 소스용 표준 DTO (DB 자동 ID, termDate 반영)
    """
    # [수정] job_id 제거 (DB가 BIGSERIAL로 자동 생성)
    company_name: str
    job_title: str
    job_description: str
    detail_link: Optional[str] = None

    job_type: Optional[str] = None
    salary: Optional[str] = None
    salary_type: Optional[str] = None
    location: Optional[str] = None
    required_skills: List[str] = field(default_factory=list)
    required_career: Optional[str] = None
    required_education: Optional[str] = None

    last_modified_date: Optional[str] = None

    # [신규] XML의 <termDate> 원본 문자열 (예: "2025-11-04~2025-11-13")
    term_date_str: Optional[str] = None

    def get_text_for_embedding(self) -> str:
        """EmbeddingService로 전달할 표준화된 텍스트를 생성합니다."""
        # (기존과 동일하게 유지)
        skills = f"요구 기술은 {', '.join(self.required_skills)}입니다." if self.required_skills else ""
        salary_info = f"{self.salary_type or ''} {self.salary or ''}".strip()

        return (
            f"회사명은 '{self.company_name}'이며, {self.location or '지역 미정'}에서 근무합니다. "
            f"채용 직무는 '{self.job_title}'({self.job_type or '유형 미정'})입니다. "
            f"급여는 {salary_info or '정보 없음'}입니다. "
            f"요구 경력은 {self.required_career or '무관'}이며, 요구 학력은 {self.required_education or '무관'}입니다. "
            f"{skills}"
        )
