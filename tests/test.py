#!/usr/bin/env python3
"""
기존 번역 데이터 활용 기능 테스트 실행 스크립트

사용법:
    python tests/test.py

또는:
    cd tests
    python test.py
"""

import asyncio
import sys
from pathlib import Path

# 프로젝트 루트를 sys.path에 추가
current_dir = Path(__file__).parent
project_root = current_dir.parent
sys.path.insert(0, str(project_root))

from test_existing_translations import TestExistingTranslations


def print_banner():
    """테스트 시작 배너 출력"""
    print("=" * 80)
    print("🧪 Auto-Translate 기존 번역 데이터 활용 기능 테스트")
    print("=" * 80)
    print()
    print("📋 테스트 내용:")
    print("  1. ModpackLoader의 소스/타겟 파일 수집 기능")
    print("  2. 기존 번역 데이터 추출 및 분석 기능")
    print("  3. 1차 사전 구축 기능")
    print("  4. JSONTranslator의 기존 번역 데이터 활용")
    print("  5. ModpackTranslator 통합 동작")
    print()
    print("🎯 목표: 기존 번역 파일을 활용하여 더 일관성 있는 번역 생성")
    print()


def print_requirements():
    """요구사항 출력"""
    print("📋 테스트 요구사항:")
    print("  ✅ Python 3.8 이상")
    print("  ✅ 프로젝트 의존성 설치 (requirements.txt)")
    print("  ✅ 테스트 데이터 (tests/test_data/)")
    print()

    # 테스트 데이터 확인
    test_data_path = current_dir / "test_data" / "modpack"
    if test_data_path.exists():
        print("  ✅ 테스트 데이터 확인됨")
    else:
        print("  ❌ 테스트 데이터 없음")
        print(f"      예상 경로: {test_data_path}")
        return False

    print()
    return True


async def main():
    """메인 함수"""
    # 배너 출력
    print_banner()

    # 요구사항 확인
    if not print_requirements():
        print("❌ 테스트 데이터가 없습니다. 테스트를 종료합니다.")
        return

    try:
        # 테스트 실행
        print("🚀 테스트 시작...")
        print()

        test_runner = TestExistingTranslations()
        await test_runner.run_all_tests()

    except KeyboardInterrupt:
        print("\n⏸️  사용자가 테스트를 중단했습니다.")
    except Exception as e:
        print(f"\n❌ 예상치 못한 오류가 발생했습니다: {e}")
        import traceback

        traceback.print_exc()

    print("\n🏁 테스트 실행 완료")


if __name__ == "__main__":
    # 비동기 테스트 실행
    asyncio.run(main())
