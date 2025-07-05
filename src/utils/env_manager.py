"""
환경 변수 관리 유틸리티 모듈

.env 파일 읽기/쓰기 및 API 키 관리 기능 제공
"""

import logging
import os
from pathlib import Path
from typing import Dict, Optional

logger = logging.getLogger(__name__)


class EnvManager:
    """환경 변수 관리자 클래스"""

    def __init__(self, env_file_path: str = ".env"):
        self.env_file_path = Path(env_file_path)
        self.env_data = {}
        self.load_env_file()

    def load_env_file(self):
        """환경 변수 파일 로드"""
        if not self.env_file_path.exists():
            logger.info(f"환경 변수 파일이 없습니다: {self.env_file_path}")
            return

        try:
            with open(self.env_file_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        key, value = line.split("=", 1)
                        key = key.strip()
                        value = value.strip()

                        # 따옴표 제거
                        if value.startswith('"') and value.endswith('"'):
                            value = value[1:-1]
                        elif value.startswith("'") and value.endswith("'"):
                            value = value[1:-1]

                        self.env_data[key] = value
                        # 환경 변수에도 설정
                        os.environ[key] = value

            logger.info(f"환경 변수 파일 로드 완료: {len(self.env_data)}개 변수")

        except Exception as e:
            logger.error(f"환경 변수 파일 로드 실패: {e}")

    def save_env_file(self):
        """환경 변수 파일 저장"""
        try:
            # 디렉토리가 없으면 생성
            self.env_file_path.parent.mkdir(parents=True, exist_ok=True)

            with open(self.env_file_path, "w", encoding="utf-8") as f:
                f.write("# Auto-generated environment variables\n")
                f.write("# API Keys and Configuration\n\n")

                for key, value in self.env_data.items():
                    # 값에 공백이나 특수문자가 있으면 따옴표로 감싸기
                    if " " in value or any(
                        char in value for char in ["#", "=", "\n", "\r"]
                    ):
                        f.write(f'{key}="{value}"\n')
                    else:
                        f.write(f"{key}={value}\n")

            logger.info(f"환경 변수 파일 저장 완료: {self.env_file_path}")

        except Exception as e:
            logger.error(f"환경 변수 파일 저장 실패: {e}")
            raise

    def get_env_var(self, key: str, default: Optional[str] = None) -> Optional[str]:
        """환경 변수 값 조회"""
        # 먼저 현재 환경 변수에서 조회
        value = os.environ.get(key)
        if value is not None:
            return value

        # 로드된 데이터에서 조회
        return self.env_data.get(key, default)

    def set_env_var(self, key: str, value: str):
        """환경 변수 설정"""
        self.env_data[key] = value
        os.environ[key] = value
        logger.debug(f"환경 변수 설정: {key}")

    def delete_env_var(self, key: str):
        """환경 변수 삭제"""
        if key in self.env_data:
            del self.env_data[key]

        if key in os.environ:
            del os.environ[key]

        logger.debug(f"환경 변수 삭제: {key}")

    def get_all_api_keys(self) -> Dict[str, str]:
        """모든 API 키 조회"""
        api_keys = {}

        api_key_patterns = [
            "OPENAI_API_KEY",
            "GOOGLE_API_KEY",
            "ANTHROPIC_API_KEY",
            "DEEPSEEK_API_KEY",
        ]

        for pattern in api_key_patterns:
            value = self.get_env_var(pattern)
            if value:
                api_keys[pattern] = value

        return api_keys

    def set_api_key(self, provider_id: str, api_key: str):
        """API 키 설정"""
        key_mapping = {
            "openai": "OPENAI_API_KEY",
            "gemini": "GOOGLE_API_KEY",
            "claude": "ANTHROPIC_API_KEY",
            "deepseek": "DEEPSEEK_API_KEY",
        }

        env_key = key_mapping.get(provider_id)
        if env_key:
            self.set_env_var(env_key, api_key)
            logger.info(f"{provider_id} API 키 설정 완료")
            return True

        return False

    def get_api_key(self, provider_id: str) -> Optional[str]:
        """API 키 조회"""
        key_mapping = {
            "openai": "OPENAI_API_KEY",
            "gemini": "GOOGLE_API_KEY",
            "claude": "ANTHROPIC_API_KEY",
            "deepseek": "DEEPSEEK_API_KEY",
        }

        env_key = key_mapping.get(provider_id)
        if env_key:
            return self.get_env_var(env_key)

        return None

    def remove_api_key(self, provider_id: str):
        """API 키 제거"""
        key_mapping = {
            "openai": "OPENAI_API_KEY",
            "gemini": "GOOGLE_API_KEY",
            "claude": "ANTHROPIC_API_KEY",
            "deepseek": "DEEPSEEK_API_KEY",
        }

        env_key = key_mapping.get(provider_id)
        if env_key:
            self.delete_env_var(env_key)
            logger.info(f"{provider_id} API 키 제거 완료")
            return True

        return False

    def save_api_keys(self, api_keys: Dict[str, str]):
        """여러 API 키 저장"""
        for provider_id, api_key in api_keys.items():
            if api_key.strip():  # 빈 문자열이 아닌 경우만 저장
                self.set_api_key(provider_id, api_key.strip())

        self.save_env_file()

    def validate_api_key(self, api_key: str) -> bool:
        """API 키 형식 검증"""
        if not api_key or not api_key.strip():
            return False

        # 기본적인 검증: 길이와 문자 구성
        api_key = api_key.strip()

        # 최소 길이 검증
        if len(api_key) < 10:
            return False

        # 공백 문자 검증
        if " " in api_key:
            return False

        return True

    def get_config_summary(self) -> Dict:
        """설정 요약 정보"""

        summary = {
            "env_file_exists": self.env_file_path.exists(),
            "env_file_path": str(self.env_file_path),
            "total_vars": len(self.env_data),
            "api_keys_configured": [],
        }

        # API 키 설정 상태 확인
        providers = ["openai", "gemini", "claude", "deepseek"]
        for provider in providers:
            api_key = self.get_api_key(provider)
            if api_key:
                summary["api_keys_configured"].append(provider)

        return summary
