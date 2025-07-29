"""
번역자 해시 생성 및 관리 유틸리티
"""

import hashlib
import json
import os
import time
from pathlib import Path


class TranslatorHashManager:
    """번역자 해시 생성 및 관리 클래스"""

    def __init__(self, config_dir: str = "."):
        """
        TranslatorHashManager 초기화

        Args:
            config_dir: 설정 파일이 저장될 디렉토리
        """
        self.config_dir = Path(config_dir)
        self.config_file = self.config_dir / "translator_config.json"

        # 설정 디렉토리가 없으면 생성
        self.config_dir.mkdir(exist_ok=True)

    def get_or_create_translator_hash(self) -> str:
        """
        기존 번역자 해시를 불러오거나 새로 생성합니다.

        Returns:
            str: 번역자 해시 (8자리)
        """
        # 기존 설정 파일 확인
        if self.config_file.exists():
            try:
                with open(self.config_file, "r", encoding="utf-8") as f:
                    config = json.load(f)
                    if "translator_hash" in config:
                        print(f"✓ 기존 번역자 해시 사용: {config['translator_hash']}")
                        return config["translator_hash"]
            except Exception as e:
                print(f"⚠️ 설정 파일 읽기 실패: {e}")

        # 새로운 해시 생성
        translator_hash = self._generate_new_hash()

        # 설정 파일에 저장
        self._save_config(translator_hash)

        print(f"🆕 새로운 번역자 해시 생성: {translator_hash}")
        return translator_hash

    def _generate_new_hash(self) -> str:
        """
        새로운 번역자 해시를 생성합니다.

        Returns:
            str: 8자리 해시 문자열
        """
        import platform
        import random
        import time

        # 고유한 데이터 조합으로 해시 생성
        unique_data = f"{time.time()}{random.random()}{platform.node()}{os.getpid()}"
        hash_object = hashlib.sha256(unique_data.encode())

        # 처음 8자리만 사용
        return hash_object.hexdigest()[:8].upper()

    def _save_config(self, translator_hash: str):
        """
        번역자 해시를 설정 파일에 저장합니다.

        Args:
            translator_hash: 저장할 번역자 해시
        """
        try:
            config = {}

            # 기존 설정이 있다면 불러오기
            if self.config_file.exists():
                try:
                    with open(self.config_file, "r", encoding="utf-8") as f:
                        config = json.load(f)
                except:
                    pass  # 파일이 손상되었다면 빈 설정으로 시작

            # 번역자 해시 설정
            config["translator_hash"] = translator_hash
            config["created_at"] = str(time.time())

            # 파일에 저장
            with open(self.config_file, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=2, ensure_ascii=False)

        except Exception as e:
            print(f"❌ 설정 파일 저장 실패: {e}")

    def update_last_registration(self, modpack_id: str):
        """
        마지막 등록 정보를 업데이트합니다.

        Args:
            modpack_id: 등록한 모드팩 ID
        """
        try:
            config = {}

            # 기존 설정 불러오기
            if self.config_file.exists():
                with open(self.config_file, "r", encoding="utf-8") as f:
                    config = json.load(f)

            # 등록 기록 추가
            if "registration_history" not in config:
                config["registration_history"] = []

            config["registration_history"].append(
                {"modpack_id": modpack_id, "registered_at": str(time.time())}
            )

            # 최근 10개만 유지
            config["registration_history"] = config["registration_history"][-10:]

            # 파일에 저장
            with open(self.config_file, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=2, ensure_ascii=False)

        except Exception as e:
            print(f"⚠️ 등록 기록 저장 실패: {e}")


# 전역 인스턴스
_hash_manager = None


def get_translator_hash() -> str:
    """
    전역 번역자 해시를 가져옵니다.

    Returns:
        str: 번역자 해시
    """
    global _hash_manager
    if _hash_manager is None:
        _hash_manager = TranslatorHashManager()

    return _hash_manager.get_or_create_translator_hash()


def update_registration_history(modpack_id: str):
    """
    등록 기록을 업데이트합니다.

    Args:
        modpack_id: 등록한 모드팩 ID
    """
    global _hash_manager
    if _hash_manager is None:
        _hash_manager = TranslatorHashManager()

    _hash_manager.update_last_registration(modpack_id)
