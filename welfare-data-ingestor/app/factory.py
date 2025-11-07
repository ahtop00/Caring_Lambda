# -*- coding: utf-8 -*-

from app import config
from app.fetchers.local_fetcher import LocalWelfareFetcher
from app.fetchers.central_fetcher import CentralWelfareFetcher
from app.repository.welfare_repository import WelfareRepository
from app.service.notification_service import NotificationService
from app.fetchers.employment_fetcher import EmploymentFetcher
from app.repository.employment_repository import EmploymentRepository


def get_dependencies(source: str, db_config: dict, sqs_client) -> dict:
    """
    'source' 문자열을 기반으로 올바른 Fetcher, Repository, Publisher,
    그리고 페이지 설정(dict)을 반환합니다.

    sqs_client를 인자로 받아 올바른 Publisher를 주입합니다.
    """
    if source == "local" or source == "central":
        # '복지(policy)' 정보 소스
        publisher_instance = NotificationService(
            sqs_client=sqs_client,
            queue_url=config.WELFARE_SQS_QUEUE_URL # 'policy-sqs' 사용
        )

        if source == "local":
            fetcher_instance = LocalWelfareFetcher(
                api_endpoint=config.LOCAL_API_ENDPOINT,
                service_key=config.LOCAL_API_KEY,
                rows_per_page=config.LOCAL_ROWS_PER_PAGE
            )
            page_cfg = {
                "start_page": config.LOCAL_START_PAGE,
                "page_limit": config.LOCAL_PAGE_LIMIT
            }
        else: # "central"
            fetcher_instance = CentralWelfareFetcher(
                api_endpoint=config.CENTRAL_API_ENDPOINT,
                service_key=config.CENTRAL_API_KEY,
                rows_per_page=config.CENTRAL_ROWS_PER_PAGE
            )
            page_cfg = {
                "start_page": config.CENTRAL_START_PAGE,
                "page_limit": config.CENTRAL_PAGE_LIMIT
            }

        return {
            "fetcher": fetcher_instance,
            "repository": WelfareRepository(db_config),
            "publisher": publisher_instance,
            "page_config": page_cfg
        }

    elif source == "employment":
        publisher_instance = NotificationService(
            sqs_client=sqs_client,
            queue_url=config.EMPLOYMENT_SQS_QUEUE_URL # 'jobOpening-sqs' 사용
        )

        fetcher_instance = EmploymentFetcher(
            api_endpoint=config.EMPLOYMENT_API_ENDPOINT,
            service_key=config.EMPLOYMENT_API_KEY,
            rows_per_page=config.EMPLOYMENT_ROWS_PER_PAGE
        )

        page_cfg = {
            "start_page": config.EMPLOYMENT_START_PAGE,
            "page_limit": config.EMPLOYMENT_PAGE_LIMIT
        }

        return {
            "fetcher": fetcher_instance,
            "repository": EmploymentRepository(db_config), # [신규] 구인 정보 Repository
            "publisher": publisher_instance,               # [신규] 구인 정보 SQS Publisher
            "page_config": page_cfg
        }

    else:
        raise ValueError(f"알 수 없는 'source' 값입니다: {source}")

def get_sources_to_run(event) -> list:
    """이벤트에 따라 실행할 source 리스트를 반환합니다."""
    source_to_run = event.get("source")

    if source_to_run:
        # "local", "central", "employment" 등
        return [source_to_run]
    else:
        # 파라미터가 없으면 기본값 (모든 복지 데이터)
        return ["local", "central"]
