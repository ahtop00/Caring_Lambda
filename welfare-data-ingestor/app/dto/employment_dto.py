# -*- coding: utf-8 -*-
from dataclasses import dataclass, field
from typing import Optional, List

@dataclass
class JobOpeningDTO:
    """
    '구인 정보' 데이터 소스용 표준 DTO (DB 자동 ID, termDate 반영)
    """
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

    term_date_str: Optional[str] = None

    def get_text_for_embedding(self) -> str:
        """EmbeddingService로 전달할 표준화된 텍스트를 생성합니다."""
        skills = f"요구 기술은 {', '.join(self.required_skills)}입니다." if self.required_skills else ""
        salary_info = f"{self.salary_type or ''} {self.salary or ''}".strip()

        return (
            f"회사명은 '{self.company_name}'이며, {self.location or '지역 미정'}에서 근무합니다. "
            f"채용 직무는 '{self.job_title}'({self.job_type or '유형 미정'})입니다. "
            f"급여는 {salary_info or '정보 없음'}입니다. "
            f"요구 경력은 {self.required_career or '무관'}이며, 요구 학력은 {self.required_education or '무관'}입니다. "
            f"{skills}"
        )

    # --- SQS 중복 알림 방지용 복합 키 생성 ---
    def get_composite_key(self) -> str:
        """
        중복 검사를 위한 고유 키(문자열)를 생성합니다.
        (detail_link가 없으므로 주요 필드를 조합)
        """
        # term_date_str, salary 등 바뀔 수 있는 정보는 키에서 제외하거나
        # 혹은 포함하여 완전히 동일한 공고만 걸러낼 수 있습니다.
        # 여기서는 좀 더 엄격하게 (회사명 + 직무명 + 마감일 + 급여)가 모두 같아야 중복으로 봅니다.
        return (
            f"{self.company_name or ''}|{self.job_title or ''}|"
            f"{self.term_date_str or ''}|{self.salary or ''}"
        )
