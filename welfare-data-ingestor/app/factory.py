# app/factory.py
# -*- coding: utf-8 -*-

from app import config
from app.fetchers.local_fetcher import LocalWelfareFetcher
from app.fetchers.central_fetcher import CentralWelfareFetcher
from app.repository.welfare_repository import WelfareRepository
# (미래 확장 예시)
# from app.fetchers.employment_fetcher import EmploymentFetcher
# from app.repository.employment_repository import EmploymentRepository

def get_dependencies(source: str, db_config: dict) -> dict:
    """
    'source' 문자열을 기반으로 올바른 Fetcher, Repository,
    그리고 페이지 설정(dict)을 반환합니다.
    """
    if source == "local":
        return {
            "fetcher": LocalWelfareFetcher(
                api_endpoint=config.LOCAL_API_ENDPOINT,
                service_key=config.LOCAL_API_KEY,
                rows_per_page=config.LOCAL_ROWS_PER_PAGE
            ),
            "repository": WelfareRepository(db_config),
            "page_config": {
                "start_page": config.LOCAL_START_PAGE,
                "page_limit": config.LOCAL_PAGE_LIMIT
            }
        }
    elif source == "central":
        return {
            "fetcher": CentralWelfareFetcher(
                api_endpoint=config.CENTRAL_API_ENDPOINT,
                service_key=config.CENTRAL_API_KEY,
                rows_per_page=config.CENTRAL_ROWS_PER_PAGE
            ),
            "repository": WelfareRepository(db_config),
            "page_config": {
                "start_page": config.CENTRAL_START_PAGE,
                "page_limit": config.CENTRAL_PAGE_LIMIT
            }
        }

    # (미래 확장 예시)
    # elif source == "employment":
    #     return {
    #         "fetcher": EmploymentFetcher(...),
    #         "repository": EmploymentRepository(db_config),
    #         "page_config": { ... }
    #     }

    else:
        raise ValueError(f"알 수 없는 'source' 값입니다: {source}")

def get_sources_to_run(event) -> list:
    """이벤트에 따라 실행할 source 리스트를 반환합니다."""
    source_to_run = event.get("source")

    if source_to_run:
        # "local" 또는 "central" (또는 미래의 "employment")
        return [source_to_run]
    else:
        # 파라미터가 없으면 기본값 (모든 복지 데이터)
        return ["local", "central"]
