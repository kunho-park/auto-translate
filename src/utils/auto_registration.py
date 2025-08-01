"""
번역 완료 후 자동 등록 기능
"""

import json
import os
from pathlib import Path
from typing import Dict, Optional, Tuple

import requests

from .translator_hash import get_translator_hash, update_registration_history


class AutoRegistrationManager:
    """자동 등록 관리 클래스"""

    def __init__(self, api_base_url: str = "https://mcat.2odk.com"):
        """
        AutoRegistrationManager 초기화

        Args:
            api_base_url: API 서버 베이스 URL
        """
        self.api_base_url = api_base_url.rstrip("/")
        self.register_endpoint = f"{self.api_base_url}/api/modpacks/register"

    def auto_register_modpack(
        self,
        output_dir: str,
        modpack_info: Dict,
        loader_settings: Dict,
        translated_count: int,
        version: str = "1.0.0",
        description: str = "",
        resource_pack_path: Optional[str] = None,
        override_files_path: Optional[str] = None,
    ) -> bool:
        """
        번역 완료 후 자동으로 모드팩을 등록합니다.

        Args:
            output_dir: 번역된 파일들이 저장된 출력 디렉토리
            modpack_info: 모드팩 정보 (path, name 등)
            loader_settings: ModpackLoader 설정 정보
            translated_count: 번역된 항목 수
            version: 번역 버전
            description: 번역 설명
            resource_pack_path: 리소스팩 파일 경로 (직접 지정)
            override_files_path: 덮어쓰기 파일 경로 (직접 지정)

        Returns:
            bool: 등록 성공 여부
        """
        # 파일 경로 변수 (직접 제공되거나 검색을 통해 찾음)
        final_resource_pack_path = resource_pack_path
        final_override_files_path = override_files_path

        try:
            print("\n" + "=" * 60)
            print("🚀 자동 등록 시작")
            print("=" * 60)

            # CurseForge ID와 버전 추출
            curseforge_id, modpack_version = self._extract_modpack_metadata(
                modpack_info
            )
            if not curseforge_id:
                print("❌ CurseForge ID를 찾을 수 없어 자동 등록을 건너뛰니다.")
                return False

            # 버전이 추출되지 않았다면 등록 중단
            if not modpack_version:
                print("❌ 모드팩 버전을 찾을 수 없어 자동 등록을 건너뛰니다.")
                print("   manifest.json에 version 필드가 있는지 확인해 주세요.")
                return False
            else:
                print(f"✓ 자동 추출된 모드팩 버전 사용: {modpack_version}")

            # 출력 디렉토리 존재 및 파일 확인
            if not self._validate_output_directory(output_dir):
                print("❌ 번역된 파일을 찾을 수 없어 자동 등록을 건너뛰니다.")
                return False

            # 번역 범위 분석
            translation_scope = self._analyze_translation_scope(
                output_dir, loader_settings
            )

            # 번역 범위 검증
            if not any(translation_scope.values()):
                print("❌ 번역된 콘텐츠를 찾을 수 없어 자동 등록을 건너뛰니다.")
                return False

            # 번역자 해시 가져오기
            translator_hash = get_translator_hash()
            if not translator_hash:
                print("❌ 번역자 해시 생성에 실패하여 자동 등록을 건너뛰니다.")
                return False

            # 번역 항목 수 검증
            if translated_count <= 0:
                print("❌ 번역된 항목이 없어 자동 등록을 건너뛰니다.")
                return False

            # 설명 생성
            if not description:
                description = self._generate_description(
                    modpack_info, translation_scope, translated_count
                )

            # 설명 검증
            if not description or len(description.strip()) < 10:
                print("❌ 번역 설명 생성에 실패하여 자동 등록을 건너뛰니다.")
                return False

            # 파일 경로가 직접 제공되지 않은 경우에만 찾기
            if not final_resource_pack_path and not final_override_files_path:
                print("🔍 생성된 파일들을 검색 중...")
                final_resource_pack_path, final_override_files_path = (
                    self._find_generated_files(output_dir, modpack_info)
                )
            else:
                print("📁 직접 제공된 파일 경로 사용:")
                if final_resource_pack_path:
                    print(f"   리소스팩: {final_resource_pack_path}")
                if final_override_files_path:
                    print(f"   덮어쓰기: {final_override_files_path}")

            # 업로드할 파일이 하나도 없으면 등록 중단
            if not final_resource_pack_path and not final_override_files_path:
                print("❌ 업로드할 파일이 생성되지 않아 자동 등록을 건너뛰니다.")
                return False

            # 등록 요청
            success = self._register_to_server(
                curseforge_id=curseforge_id,
                version=modpack_version,
                description=description,
                translator=translator_hash,
                resource_pack_path=final_resource_pack_path,
                override_files_path=final_override_files_path,
                translation_scope=translation_scope,
            )

            if success:
                # 등록 기록 저장
                modpack_name = Path(modpack_info.get("path", "")).name
                update_registration_history(f"{modpack_name}_{curseforge_id}")

                print("✅ 자동 등록 완료!")
                print("=" * 60)
                return True
            else:
                print("❌ 자동 등록 실패")
                print("=" * 60)
                return False

        except Exception as e:
            print(f"❌ 자동 등록 중 오류 발생: {e}")
            print("=" * 60)
            return False
        finally:
            # 생성된 파일들은 정리하지 않음 (packaging_output의 원본 파일들)
            pass

    def _extract_modpack_metadata(
        self, modpack_info: Dict
    ) -> Tuple[Optional[str], Optional[str]]:
        """
        모드팩 정보에서 CurseForge ID와 버전을 추출합니다.

        Args:
            modpack_info: 모드팩 정보

        Returns:
            Tuple[Optional[str], Optional[str]]: (CurseForge ID, 버전)
        """
        # manifest.json에서 CurseForge ID와 버전 찾기
        modpack_path = Path(modpack_info.get("path", ""))

        # 1. minecraftinstance.json 확인 (CurseForge Launcher)
        minecraft_instance_path = modpack_path / "minecraftinstance.json"
        if minecraft_instance_path.exists():
            try:
                with open(minecraft_instance_path, "r", encoding="utf-8") as f:
                    instance_data = json.load(f)

                # installedModpack.installedFile.projectId 경로로 CurseForge ID 추출
                if (
                    "installedModpack" in instance_data
                    and "installedFile" in instance_data["installedModpack"]
                    and "projectId"
                    in instance_data["installedModpack"]["installedFile"]
                ):
                    curseforge_id = str(
                        instance_data["installedModpack"]["installedFile"]["projectId"]
                    )
                    print(
                        f"✓ CurseForge ID 발견 (minecraftinstance.json): {curseforge_id}"
                    )

                    # 버전도 찾아보기
                    version = instance_data["manifest"]["version"]

                    return curseforge_id, version

            except Exception as e:
                print(f"⚠️ minecraftinstance.json 파일 읽기 실패: {e}")

        return None, None

    def _validate_output_directory(self, output_dir: str) -> bool:
        """
        출력 디렉토리와 번역된 파일들이 존재하는지 검증합니다.

        Args:
            output_dir: 출력 디렉토리 경로

        Returns:
            bool: 검증 성공 여부
        """
        output_path = Path(output_dir)

        # 출력 디렉토리 존재 확인
        if not output_path.exists():
            print(f"   출력 디렉토리가 존재하지 않음: {output_dir}")
            return False

        # 번역된 파일이 있는지 확인
        translated_files = []
        for file_path in output_path.rglob("*"):
            if file_path.is_file() and file_path.suffix in [
                ".json",
                ".lang",
                ".snbt",
                ".js",
                ".toml",
                ".jar",
            ]:
                translated_files.append(file_path)

        if not translated_files:
            print(f"   번역된 파일을 찾을 수 없음: {output_dir}")
            return False

        print(f"✓ 번역된 파일 {len(translated_files)}개 발견")
        return True

    def _analyze_translation_scope(
        self, output_dir: str, loader_settings: Dict
    ) -> Dict[str, bool]:
        """
        번역 범위를 분석합니다.

        Args:
            output_dir: 출력 디렉토리
            translation_scope: 번역 범위 정보

        Returns:
            Dict[str, bool]: 번역 범위 정보
        """
        output_path = Path(output_dir)

        # 실제 생성된 파일들을 기반으로 번역 범위 확인
        scope = {
            "config": False,
            "kubejs": False,
            "mods": False,
            "resourcepacks": False,
            "patchouli_books": False,
            "ftbquests": False,
        }

        if output_path.exists():
            # config 폴더 확인
            if (output_path / "config").exists():
                scope["config"] = True

            # kubejs 폴더 확인
            if (output_path / "kubejs").exists():
                scope["kubejs"] = True

            # resourcepacks 폴더 확인
            if (output_path / "resourcepacks").exists():
                scope["resourcepacks"] = True

            # mods 관련 파일 확인 (jar 파일들)
            jar_files = list(output_path.rglob("*.jar"))
            if jar_files:
                scope["mods"] = True

            # patchouli_books 확인
            if (output_path / "config" / "patchouli_books").exists():
                scope["patchouli_books"] = True

            # ftbquests 확인
            if (output_path / "config" / "ftbquests").exists():
                scope["ftbquests"] = True

        return scope

    def _generate_description(
        self,
        modpack_info: Dict,
        translation_scope: Dict[str, bool],
        translated_count: int,
    ) -> str:
        """
        자동으로 번역 설명을 생성합니다.

        Args:
            modpack_info: 모드팩 정보
            translation_scope: 번역 범위
            translated_count: 번역된 항목 수

        Returns:
            str: 생성된 설명
        """
        modpack_name = Path(modpack_info.get("path", "")).name

        # 번역된 범위 목록 생성
        translated_areas = []
        scope_names = {
            "config": "설정 파일",
            "kubejs": "KubeJS 스크립트",
            "mods": "모드",
            "resourcepacks": "리소스팩",
            "patchouli_books": "Patchouli 가이드북",
            "ftbquests": "FTB 퀘스트",
        }

        for key, enabled in translation_scope.items():
            if enabled:
                translated_areas.append(scope_names[key])

        # 설명 생성
        areas_text = ", ".join(translated_areas) if translated_areas else "기본 번역"

        description = f"""Auto Translate 도구를 사용한 {modpack_name} 한국어 번역

📊 번역 통계:
• 번역된 항목: {translated_count:,}개
• 번역 범위: {areas_text}

⚠️ 주의사항:
• AI 자동 번역이므로 일부 오역이 있을 수 있습니다"""

        return description

    def _find_generated_files(
        self, output_dir: str, modpack_info: Dict
    ) -> Tuple[Optional[str], Optional[str]]:
        """
        packaging_output에서 생성된 파일들을 찾습니다.

        Args:
            output_dir: 출력 디렉토리
            modpack_info: 모드팩 정보

        Returns:
            Tuple[Optional[str], Optional[str]]: (리소스팩 경로, 덮어쓰기 파일 경로)
        """
        # packaging_output 디렉토리 경로
        packaging_output_dir = Path(output_dir) / "packaging_output"

        resource_pack_path = None
        override_files_path = None

        try:
            if not packaging_output_dir.exists():
                print(
                    f"⚠️ packaging_output 디렉토리가 존재하지 않음: {packaging_output_dir}"
                )
                return None, None

            # 리소스팩 파일 찾기 (*_리소스팩.zip)
            resourcepack_files = list(packaging_output_dir.glob("*_리소스팩.zip"))
            if resourcepack_files:
                resource_pack_path = str(resourcepack_files[0])
                print(f"✓ 리소스팩 파일 발견: {resourcepack_files[0].name}")

            # 덮어쓰기 파일 찾기 (*_덮어쓰기.zip)
            override_files = list(packaging_output_dir.glob("*_덮어쓰기.zip"))
            if override_files:
                override_files_path = str(override_files[0])
                print(f"✓ 덮어쓰기 파일 발견: {override_files[0].name}")

            # 추가로 korean 키워드가 포함된 zip 파일들도 찾아보기
            if not resource_pack_path:
                korean_resourcepack_files = list(
                    packaging_output_dir.glob("*korean*리소스팩*.zip")
                )
                if korean_resourcepack_files:
                    resource_pack_path = str(korean_resourcepack_files[0])
                    print(
                        f"✓ 한국어 리소스팩 파일 발견: {korean_resourcepack_files[0].name}"
                    )

            if not override_files_path:
                korean_override_files = list(
                    packaging_output_dir.glob("*korean*덮어쓰기*.zip")
                )
                if korean_override_files:
                    override_files_path = str(korean_override_files[0])
                    print(
                        f"✓ 한국어 덮어쓰기 파일 발견: {korean_override_files[0].name}"
                    )

        except Exception as e:
            print(f"⚠️ 생성된 파일 검색 중 오류: {e}")

        return resource_pack_path, override_files_path

    def _register_to_server(
        self,
        curseforge_id: str,
        version: str,
        description: str,
        translator: str,
        resource_pack_path: Optional[str],
        override_files_path: Optional[str],
        translation_scope: Dict[str, bool],
    ) -> bool:
        """
        서버에 모드팩을 등록합니다.

        Args:
            curseforge_id: CurseForge ID
            version: 버전
            description: 설명
            translator: 번역자 해시
            resource_pack_path: 리소스팩 파일 경로
            override_files_path: 덮어쓰기 파일 경로
            translation_scope: 번역 범위 정보

        Returns:
            bool: 등록 성공 여부
        """
        try:
            # 폼 데이터 준비 (기본 정보)
            data = {
                "curseforgeId": curseforge_id,
                "version": version,
                "description": description,
                "translator": translator,
            }

            # 번역 범위 플래그 설정 (translation_scope 기반)
            data.update(
                {
                    "translateConfig": str(
                        translation_scope.get("config", False)
                    ).lower(),
                    "translateKubejs": str(
                        translation_scope.get("kubejs", False)
                    ).lower(),
                    "translateMods": str(translation_scope.get("mods", False)).lower(),
                    "translateResourcepacks": str(
                        translation_scope.get("resourcepacks", False)
                    ).lower(),
                    "translatePatchouliBooks": str(
                        translation_scope.get("patchouli_books", False)
                    ).lower(),
                    "translateFtbquests": str(
                        translation_scope.get("ftbquests", False)
                    ).lower(),
                }
            )

            files = {}

            # 리소스팩 파일 첨부
            if resource_pack_path and os.path.exists(resource_pack_path):
                files["resourcePack"] = open(resource_pack_path, "rb")
                print(f"✓ 리소스팩 파일 첨부: {resource_pack_path}")

            # 덮어쓰기 파일 첨부
            if override_files_path and os.path.exists(override_files_path):
                files["overrideFiles"] = open(override_files_path, "rb")
                print(f"✓ 덮어쓰기 파일 첨부: {override_files_path}")

            print("🚀 서버에 등록 요청 시작...")
            print(f"   CurseForge ID: {curseforge_id}")
            print(f"   버전: {version}")
            print(f"   번역자: {translator}")
            print(f"   서버 URL: {self.register_endpoint}")

            # 번역 범위 출력
            scope_info = []
            for key, value in data.items():
                if key.startswith("translate") and value == "true":
                    scope_info.append(key.replace("translate", ""))
            print(f"   번역 범위: {', '.join(scope_info) if scope_info else '없음'}")

            # API 호출
            response = requests.post(
                self.register_endpoint,
                data=data,
                files=files,
                timeout=300,  # 5분 타임아웃
            )

            print(f"📡 응답 상태: {response.status_code}")

            if response.status_code == 200:
                try:
                    result = response.json()
                    print("✅ 등록 성공!")
                    print(f"   등록된 모드팩 ID: {result.get('modpackId', 'N/A')}")
                    print(f"   메시지: {result.get('message', 'N/A')}")
                    return True
                except json.JSONDecodeError:
                    print("✅ 등록 성공! (응답 JSON 파싱 실패)")
                    return True
            else:
                print("❌ 등록 실패!")
                try:
                    error_data = response.json()
                    print(f"   오류: {error_data.get('error', '알 수 없는 오류')}")
                except:
                    print(f"   응답: {response.text}")
                return False

        except requests.exceptions.Timeout:
            print("❌ 요청 시간 초과! 서버 응답을 기다리는 중...")
            return False
        except requests.exceptions.ConnectionError:
            print(f"❌ 서버 연결 실패! {self.api_base_url}에 연결할 수 없습니다.")
            return False
        except Exception as e:
            print(f"❌ 예상치 못한 오류: {e}")
            return False
        finally:
            # 파일 핸들 정리
            for file_handle in files.values():
                if hasattr(file_handle, "close"):
                    file_handle.close()

    def _cleanup_temp_files(self, *file_paths):
        """
        임시 파일들을 정리합니다.

        Args:
            *file_paths: 정리할 파일 경로들
        """
        for file_path in file_paths:
            if file_path and os.path.exists(file_path):
                try:
                    os.remove(file_path)
                    print(f"🗑️ 임시 파일 정리: {file_path}")
                except Exception as e:
                    print(f"⚠️ 임시 파일 정리 실패 ({file_path}): {e}")


# 전역 등록 매니저 인스턴스
_registration_manager = None


def auto_register_after_translation(
    output_dir: str,
    modpack_info: Dict,
    loader_settings: Dict,
    translated_count: int,
    version: str = "1.0.0",
    description: str = "",
    api_base_url: str = "https://mcat.2odk.com",
    resource_pack_path: Optional[str] = None,
    override_files_path: Optional[str] = None,
) -> bool:
    """
    번역 완료 후 자동 등록을 수행합니다.

    Args:
        output_dir: 번역된 파일들이 저장된 출력 디렉토리
        modpack_info: 모드팩 정보
        loader_settings: ModpackLoader 설정
        translated_count: 번역된 항목 수
        version: 번역 버전
        description: 번역 설명
        api_base_url: API 서버 URL
        resource_pack_path: 리소스팩 파일 경로 (직접 지정)
        override_files_path: 덮어쓰기 파일 경로 (직접 지정)

    Returns:
        bool: 등록 성공 여부
    """
    global _registration_manager

    if _registration_manager is None:
        _registration_manager = AutoRegistrationManager(api_base_url)

    return _registration_manager.auto_register_modpack(
        output_dir=output_dir,
        modpack_info=modpack_info,
        loader_settings=loader_settings,
        translated_count=translated_count,
        version=version,
        description=description,
        resource_pack_path=resource_pack_path,
        override_files_path=override_files_path,
    )
