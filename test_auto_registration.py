#!/usr/bin/env python3
"""
자동 등록 기능 테스트 스크립트
"""

import json
import tempfile
from pathlib import Path

from src.utils.auto_registration import auto_register_after_translation
from src.utils.translator_hash import get_translator_hash


def create_test_output_structure(test_dir: Path):
    """테스트용 출력 폴더 구조 생성"""

    # config 폴더와 파일들 생성
    config_dir = test_dir / "config"
    config_dir.mkdir(parents=True, exist_ok=True)

    # 가짜 config 파일 생성
    (config_dir / "test_config.toml").write_text(
        "# 테스트 설정 파일\ntest_value = 'translated'"
    )

    # ftbquests 폴더 생성
    ftbquests_dir = config_dir / "ftbquests" / "quests" / "chapters"
    ftbquests_dir.mkdir(parents=True, exist_ok=True)
    (ftbquests_dir / "chapter1.snbt").write_text("{title: '번역된 퀘스트'}")

    # kubejs 폴더 생성
    kubejs_dir = test_dir / "kubejs" / "server_scripts"
    kubejs_dir.mkdir(parents=True, exist_ok=True)
    (kubejs_dir / "test_script.js").write_text(
        "// 번역된 스크립트\nconsole.log('테스트');"
    )

    # mods 폴더에 jar 파일 생성 (빈 파일)
    mods_dir = test_dir / "mods"
    mods_dir.mkdir(parents=True, exist_ok=True)
    (mods_dir / "test_mod_korean.jar").write_bytes(b"fake jar content")

    print(f"✓ 테스트 출력 구조 생성 완료: {test_dir}")


def create_test_modpack_with_minecraft_instance(
    test_modpack_dir: Path, curseforge_id: str
):
    """테스트용 모드팩 폴더와 minecraftinstance.json 생성"""
    test_modpack_dir.mkdir(parents=True, exist_ok=True)

    # minecraftinstance.json 생성 (CurseForge Launcher 형식)
    minecraft_instance = {
        "name": "Craft to Exile 2 (VR Support)",
        "gameVersion": "1.21.1",
        "installedModpack": {
            "installedFile": {
                "projectId": int(curseforge_id),
                "displayName": "Craft to Exile 2 (VR Support) v2.1.0",
                "fileName": "craft-to-exile-2-vr-support-2.1.0.zip",
            }
        },
    }

    instance_path = test_modpack_dir / "minecraftinstance.json"
    with open(instance_path, "w", encoding="utf-8") as f:
        json.dump(minecraft_instance, f, indent=2, ensure_ascii=False)

    print(f"✓ 테스트 모드팩 구조 생성 완료: {test_modpack_dir}")
    print(f"✓ CurseForge ID {curseforge_id}로 minecraftinstance.json 생성")


def create_test_modpack_with_manifest(test_modpack_dir: Path, curseforge_id: str):
    """테스트용 모드팩 폴더와 manifest.json 생성"""
    test_modpack_dir.mkdir(parents=True, exist_ok=True)

    # manifest.json 생성
    manifest = {
        "minecraft": {
            "version": "1.21.1",
            "modLoaders": [{"id": "neoforge", "primary": True}],
        },
        "manifestType": "minecraftModpack",
        "manifestVersion": 1,
        "name": "테스트 모드팩",
        "version": "2.1.0",
        "author": "테스트 작성자",
        "projectID": int(curseforge_id),  # CurseForge ID
        "files": [],
        "overrides": "overrides",
    }

    manifest_path = test_modpack_dir / "manifest.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)

    print(f"✓ 테스트 모드팩 구조 생성 완료 (manifest.json): {test_modpack_dir}")
    print(f"✓ CurseForge ID {curseforge_id}로 manifest.json 생성")


def test_auto_registration_with_minecraft_instance():
    """minecraftinstance.json으로 자동 등록 테스트"""
    print("=" * 60)
    print("🧪 자동 등록 기능 테스트 (minecraftinstance.json)")
    print("=" * 60)

    # 임시 디렉토리 생성
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        # 테스트 모드팩 디렉토리 생성
        test_modpack_dir = temp_path / "Craft to Exile 2 (VR Support) (2)"
        output_dir = temp_path / "output" / "Craft_to_Exile_2_VR_Support_2_korean"

        # 테스트 구조 생성
        create_test_modpack_with_minecraft_instance(
            test_modpack_dir, "874578"
        )  # 실제 CurseForge ID
        create_test_output_structure(output_dir)

        # 모드팩 정보
        modpack_info = {
            "path": str(test_modpack_dir),
            "name": "Craft to Exile 2 (VR Support) (2)",
        }

        # 로더 설정
        loader_settings = {
            "translate_config": True,
            "translate_kubejs": True,
            "translate_mods": True,
            "translate_resourcepacks": False,
            "translate_patchouli_books": False,
            "translate_ftbquests": True,
        }

        # 번역자 해시 확인
        translator_hash = get_translator_hash()
        print(f"📝 사용할 번역자 해시: {translator_hash}")

        # 자동 등록 테스트
        print(f"\n📁 테스트 출력 디렉토리: {output_dir}")
        print(f"📁 테스트 모드팩 디렉토리: {test_modpack_dir}")

        # 실제 자동 등록 수행
        success = auto_register_after_translation(
            output_dir=str(output_dir),
            modpack_info=modpack_info,
            loader_settings=loader_settings,
            translated_count=1234,
            version="기본버전",  # 기본값 (minecraftinstance.json에서 자동 추출됨)
            description="테스트용 자동 등록",
            api_base_url="http://localhost:5173",  # 실제 서버 URL로 변경 가능
        )

        print("\n" + "=" * 60)
        if success:
            print("✅ 자동 등록 테스트 성공!")
        else:
            print("❌ 자동 등록 테스트 실패")
            print("   - 서버가 실행 중인지 확인하세요")
            print("   - API 엔드포인트가 올바른지 확인하세요")
        print("=" * 60)


def test_auto_registration_with_manifest():
    """manifest.json으로 자동 등록 테스트"""
    print("=" * 60)
    print("🧪 자동 등록 기능 테스트 (manifest.json)")
    print("=" * 60)

    # 임시 디렉토리 생성
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        # 테스트 모드팩 디렉토리 생성
        test_modpack_dir = temp_path / "test_modpack_123456"
        output_dir = temp_path / "output" / "test_modpack_123456_korean"

        # 테스트 구조 생성
        create_test_modpack_with_manifest(test_modpack_dir, "123456")
        create_test_output_structure(output_dir)

        # 모드팩 정보
        modpack_info = {"path": str(test_modpack_dir), "name": "test_modpack_123456"}

        # 로더 설정
        loader_settings = {
            "translate_config": True,
            "translate_kubejs": True,
            "translate_mods": True,
            "translate_resourcepacks": False,
            "translate_patchouli_books": False,
            "translate_ftbquests": True,
        }

        # 번역자 해시 확인
        translator_hash = get_translator_hash()
        print(f"📝 사용할 번역자 해시: {translator_hash}")

        # 자동 등록 테스트
        print(f"\n📁 테스트 출력 디렉토리: {output_dir}")
        print(f"📁 테스트 모드팩 디렉토리: {test_modpack_dir}")

        # 실제 자동 등록 수행
        success = auto_register_after_translation(
            output_dir=str(output_dir),
            modpack_info=modpack_info,
            loader_settings=loader_settings,
            translated_count=1234,
            version="기본버전",  # 기본값 (manifest.json에서 자동 추출됨)
            description="테스트용 자동 등록",
            api_base_url="http://localhost:5173",  # 실제 서버 URL로 변경 가능
        )

        print("\n" + "=" * 60)
        if success:
            print("✅ 자동 등록 테스트 성공!")
        else:
            print("❌ 자동 등록 테스트 실패")
            print("   - 서버가 실행 중인지 확인하세요")
            print("   - API 엔드포인트가 올바른지 확인하세요")
        print("=" * 60)


def test_translator_hash():
    """번역자 해시 기능 테스트"""
    print("\n" + "=" * 60)
    print("🔑 번역자 해시 기능 테스트")
    print("=" * 60)

    # 여러 번 호출해도 같은 해시가 나오는지 테스트
    hash1 = get_translator_hash()
    hash2 = get_translator_hash()

    print(f"첫 번째 호출: {hash1}")
    print(f"두 번째 호출: {hash2}")

    if hash1 == hash2:
        print("✅ 번역자 해시 일관성 테스트 통과")
    else:
        print("❌ 번역자 해시 일관성 테스트 실패")

    # 설정 파일 확인
    config_file = Path("translator_config.json")
    if config_file.exists():
        try:
            with open(config_file, "r", encoding="utf-8") as f:
                config = json.load(f)
            print("📄 설정 파일 내용:")
            print(f"   번역자 해시: {config.get('translator_hash', 'N/A')}")
            print(f"   생성 시간: {config.get('created_at', 'N/A')}")
            if "registration_history" in config:
                print(f"   등록 기록: {len(config['registration_history'])}개")
        except Exception as e:
            print(f"⚠️ 설정 파일 읽기 실패: {e}")

    print("=" * 60)


if __name__ == "__main__":
    print("🚀 Auto Translate - 자동 등록 기능 테스트")

    # 번역자 해시 테스트
    test_translator_hash()

    # minecraftinstance.json 테스트
    test_auto_registration_with_minecraft_instance()

    # manifest.json 테스트
    test_auto_registration_with_manifest()

    print("\n✨ 모든 테스트 완료!")
    print("\n💡 실제 사용 시:")
    print("   1. 번역 완료 후 자동으로 등록이 시도됩니다")
    print(
        "   2. CurseForge ID는 minecraftinstance.json 또는 manifest.json에서 자동 추출됩니다"
    )
    print("   3. 번역자 해시는 자동으로 생성되고 재사용됩니다")
    print("   4. 서버가 실행 중이어야 등록이 성공합니다")
    print("   5. minecraftinstance.json (CurseForge Launcher)을 우선적으로 확인합니다")
