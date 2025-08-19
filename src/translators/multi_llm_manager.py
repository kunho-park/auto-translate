"""
다중 API 키 지원 LLM 관리자 모듈

여러 API 키를 로테이션으로 사용하여 할당량 제한을 우회하고 처리 속도를 향상시킵니다.
"""

import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from .llm_manager import LLMManager

logger = logging.getLogger(__name__)


@dataclass
class APIKeyInfo:
    """API 키 정보를 저장하는 클래스"""

    key: str
    provider: str
    model: str
    usage_count: int = 0
    last_used: float = 0.0
    failed_count: int = 0
    is_active: bool = True
    error_message: str = ""

    def __post_init__(self):
        if self.last_used == 0.0:
            self.last_used = time.time()


@dataclass
class LLMClientInfo:
    """LLM 클라이언트 정보를 저장하는 클래스"""

    client: Any
    key_info: APIKeyInfo
    created_at: float = field(default_factory=time.time)


class MultiLLMManager:
    """다중 API 키를 관리하는 클래스"""

    def __init__(self):
        self.llm_manager = LLMManager()
        self.api_keys: Dict[str, APIKeyInfo] = {}  # key_id -> APIKeyInfo
        self.clients: Dict[str, LLMClientInfo] = {}  # key_id -> LLMClientInfo
        self.current_key_index = 0
        self.min_request_interval = 1.0  # 같은 키 재사용 최소 간격 (초)
        self.max_failed_attempts = 5  # 최대 실패 횟수
        self.client_cache_duration = 3600  # 클라이언트 캐시 유지 시간 (초)
        # Persisted storage
        self.storage_path = Path("multi_api_keys.json")
        # Load persisted API keys
        self.load_api_keys()

    def add_api_key(self, key_id: str, provider: str, model: str, api_key: str):
        """API 키를 추가합니다."""
        if not api_key or not api_key.strip():
            raise ValueError("API 키가 비어있습니다.")

        key_info = APIKeyInfo(key=api_key.strip(), provider=provider, model=model)

        self.api_keys[key_id] = key_info
        logger.info(f"API 키 추가됨: {key_id} ({provider}/{model})")
        # Persist keys
        self.save_api_keys()

    def remove_api_key(self, key_id: str):
        """API 키를 제거합니다."""
        if key_id in self.api_keys:
            del self.api_keys[key_id]

        if key_id in self.clients:
            del self.clients[key_id]

        logger.info(f"API 키 제거됨: {key_id}")
        # Persist keys
        self.save_api_keys()

    def get_api_keys(self) -> Dict[str, APIKeyInfo]:
        """모든 API 키 정보를 반환합니다."""
        return self.api_keys.copy()

    def get_active_keys(self) -> List[str]:
        """활성화된 API 키 ID 목록을 반환합니다."""
        return [
            key_id
            for key_id, key_info in self.api_keys.items()
            if key_info.is_active and key_info.failed_count < self.max_failed_attempts
        ]

    def get_next_key(self) -> Optional[str]:
        """다음에 사용할 API 키를 선택합니다.

        로직 우선순위
        1. `min_request_interval` 이상 쉬었던 키가 있으면 그중 가장 오래 쉬었던 키
        2. 그렇지 않으면 **라운드로빈** 방식으로 순차 선택해 키가 고르게 분배되도록 함
        """
        active_keys = self.get_active_keys()
        if not active_keys:
            return None

        current_time = time.time()

        # 1) 최소 휴식 간격을 만족하는 후보 키 목록 추출
        candidates: List[tuple[str, float]] = []
        for key_id in active_keys:
            elapsed = current_time - self.api_keys[key_id].last_used
            if elapsed >= self.min_request_interval:
                candidates.append((key_id, elapsed))

        if candidates:
            # 가장 오래 쉬었던 키 우선 선택
            candidates.sort(key=lambda x: x[1], reverse=True)
            return candidates[0][0]

        # 2) 모든 키가 아직 min_request_interval 내에 있으면 라운드로빈으로 분배
        selected_key = active_keys[self.current_key_index % len(active_keys)]
        self.current_key_index += 1
        return selected_key

    async def get_client(self, key_id: Optional[str] = None) -> Optional[Any]:
        """LLM 클라이언트를 가져옵니다."""
        client_info = await self.get_client_with_id(key_id)
        return client_info["client"] if client_info else None

    async def get_client_with_id(
        self, key_id: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """LLM 클라이언트와 해당 키 ID를 함께 반환합니다."""
        if key_id is None:
            key_id = self.get_next_key()

        if key_id is None:
            logger.error("사용 가능한 API 키가 없습니다.")
            return None

        key_info = self.api_keys.get(key_id)
        if not key_info:
            logger.error(f"API 키 정보를 찾을 수 없습니다: {key_id}")
            return None

        # 기존 클라이언트가 있고 유효한 경우 재사용
        if key_id in self.clients:
            client_info = self.clients[key_id]
            current_time = time.time()

            # 클라이언트가 너무 오래된 경우 새로 생성
            if current_time - client_info.created_at < self.client_cache_duration:
                key_info.last_used = current_time
                key_info.usage_count += 1
                logger.debug(f"기존 클라이언트 재사용: {key_id}")
                return {"client": client_info.client, "key_id": key_id}

        # 새 클라이언트 생성
        try:
            # 임시로 API 키 설정
            self.llm_manager.set_api_key(key_info.provider, key_info.key)

            client = await self.llm_manager.create_llm_client(
                key_info.provider, key_info.model
            )

            # 클라이언트 정보 저장
            self.clients[key_id] = LLMClientInfo(client=client, key_info=key_info)

            # 사용 정보 업데이트
            key_info.last_used = time.time()
            key_info.usage_count += 1
            key_info.failed_count = 0  # 성공 시 실패 카운트 리셋

            logger.debug(f"새 클라이언트 생성: {key_id}")
            return {"client": client, "key_id": key_id}

        except Exception as e:
            logger.error(f"클라이언트 생성 실패: {key_id}, 오류: {e}")
            self.mark_key_failed(key_id, str(e))
            return None

    async def create_multiple_clients(self, count: int) -> List[Any]:
        """여러 클라이언트를 생성합니다."""
        clients = []
        active_keys = self.get_active_keys()

        if not active_keys:
            logger.error("사용 가능한 API 키가 없습니다.")
            return clients

        # 키를 순환하면서 클라이언트 생성
        for i in range(count):
            key_id = active_keys[i % len(active_keys)]
            client = await self.get_client(key_id)
            if client:
                clients.append(client)

        return clients

    def mark_key_failed(self, key_id: str, error_message: str = ""):
        """API 키 실패를 기록합니다."""
        if key_id in self.api_keys:
            key_info = self.api_keys[key_id]
            key_info.failed_count += 1
            key_info.error_message = error_message

            if key_info.failed_count >= self.max_failed_attempts:
                key_info.is_active = False
                logger.warning(f"API 키 비활성화 (실패 횟수 초과): {key_id}")

    def reset_key_failures(self, key_id: str):
        """API 키 실패 카운트를 리셋합니다."""
        if key_id in self.api_keys:
            key_info = self.api_keys[key_id]
            key_info.failed_count = 0
            key_info.is_active = True
            key_info.error_message = ""
            logger.info(f"API 키 실패 카운트 리셋: {key_id}")
            # Persist keys
            self.save_api_keys()

    def get_statistics(self) -> Dict[str, Any]:
        """사용 통계를 반환합니다."""
        stats = {
            "total_keys": len(self.api_keys),
            "active_keys": len(self.get_active_keys()),
            "total_requests": sum(
                key_info.usage_count for key_info in self.api_keys.values()
            ),
            "keys_detail": {},
        }

        for key_id, key_info in self.api_keys.items():
            stats["keys_detail"][key_id] = {
                "provider": key_info.provider,
                "model": key_info.model,
                "usage_count": key_info.usage_count,
                "failed_count": key_info.failed_count,
                "is_active": key_info.is_active,
                "error_message": key_info.error_message,
            }

        return stats

    def cleanup_old_clients(self):
        """오래된 클라이언트를 정리합니다."""
        current_time = time.time()
        to_remove = []

        for key_id, client_info in self.clients.items():
            if current_time - client_info.created_at > self.client_cache_duration:
                to_remove.append(key_id)

        for key_id in to_remove:
            del self.clients[key_id]
            logger.debug(f"오래된 클라이언트 정리: {key_id}")

    def set_config(
        self, min_request_interval: float = None, max_failed_attempts: int = None
    ):
        """설정을 변경합니다."""
        if min_request_interval is not None:
            self.min_request_interval = min_request_interval

        if max_failed_attempts is not None:
            self.max_failed_attempts = max_failed_attempts

        logger.info(
            f"설정 변경: 최소 요청 간격={self.min_request_interval}초, 최대 실패 횟수={self.max_failed_attempts}"
        )

    def save_api_keys(self, file_path: Optional[str] = None) -> None:
        """Persist API keys to JSON file."""
        path = Path(file_path) if file_path else self.storage_path
        data: Dict[str, Dict[str, Any]] = {}
        for key_id, info in self.api_keys.items():
            data[key_id] = {
                "key": info.key,
                "provider": info.provider,
                "model": info.model,
                "usage_count": info.usage_count,
                "last_used": info.last_used,
                "failed_count": info.failed_count,
                "is_active": info.is_active,
                "error_message": info.error_message,
            }
        path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def load_api_keys(self, file_path: Optional[str] = None) -> None:
        """Load API keys from JSON file if exists."""
        path = Path(file_path) if file_path else self.storage_path
        if not path.exists():
            return
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            for key_id, info in raw.items():
                key_info = APIKeyInfo(
                    key=info.get("key", ""),
                    provider=info.get("provider", ""),
                    model=info.get("model", ""),
                    usage_count=info.get("usage_count", 0),
                    last_used=info.get("last_used", time.time()),
                    failed_count=info.get("failed_count", 0),
                    is_active=info.get("is_active", True),
                    error_message=info.get("error_message", ""),
                )
                self.api_keys[key_id] = key_info
        except Exception as e:
            logger.error(f"API 키 로드 실패: {e}")
