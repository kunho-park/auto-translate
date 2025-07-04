# Auto-Translate 테스트 스위트

이 폴더는 Auto-Translate 프로젝트의 테스트 코드와 테스트 데이터를 포함합니다.

## 🧪 테스트 목록

### 📁 `test_existing_translations.py`
**기존 번역 데이터 활용 기능 테스트**

새로 구현된 기능들을 종합적으로 테스트합니다:
- ModpackLoader의 소스/타겟 파일 수집
- 기존 번역 데이터 추출 및 분석
- 1차 사전 구축
- JSONTranslator의 기존 번역 데이터 활용
- ModpackTranslator 통합 동작

## 🚀 테스트 실행 방법

### 빠른 시작
```bash
# 프로젝트 루트에서 실행
python tests/test.py
```

### 상세 실행
```bash
# 특정 테스트 파일 실행
python tests/test_existing_translations.py

# 또는 tests 폴더로 이동 후 실행
cd tests
python test.py
```

## 📋 사전 준비사항

1. **의존성 설치**
   ```bash
   pip install -r requirements.txt
   ```

2. **환경 변수 설정** (실제 LLM 테스트 시)
   ```bash
   # .env 파일에 추가
   GOOGLE_API_KEY=your_gemini_api_key_here
   ```

3. **테스트 데이터 확인**
   - `tests/test_data/modpack/` 폴더에 테스트 데이터가 있는지 확인
   - 자동으로 생성된 모의 모드팩 데이터 사용

## 📊 테스트 데이터

### 구조
```
tests/
├── test_data/modpack/           # 모의 모드팩 데이터
│   ├── mods/extracted/          # 모드 JAR 파일들
│   ├── resourcepacks/           # 리소스팩 파일들
│   ├── config/                  # 설정 파일들
│   └── kubejs/                  # KubeJS 스크립트들
├── test_existing_translations.py # 메인 테스트 코드
├── test.py                      # 테스트 실행 스크립트
└── README.md                    # 이 파일
```

### 테스트 데이터 내용
- **3개 모드**: example_mod, tech_mod + 리소스팩
- **언어 쌍**: 영어(en_us) ↔ 한국어(ko_kr)
- **번역 쌍**: 총 41개 이상의 기존 번역 데이터
- **파일 형식**: JSON, JavaScript, 설정 파일

## 🔍 테스트 결과 해석

### 성공 시 출력 예시
```
✅ 파일 수집 테스트 통과
  소스 파일(en_us): 3개
  타겟 파일(ko_kr): 3개

✅ 기존 번역 분석 테스트 통과
  추출된 번역 쌍: 41개
  유효한 번역 쌍: 41/41개

✅ 1차 사전 구축 테스트 통과
  생성된 1차 사전 용어 수: 15개

🎉 모든 테스트가 성공적으로 완료되었습니다!
```

### 실패 시 대처 방법

1. **테스트 데이터 없음**
   - `tests/test_data/modpack/` 폴더와 파일들이 제대로 생성되었는지 확인

2. **의존성 오류**
   ```bash
   pip install -r requirements.txt
   ```

3. **LLM API 오류**
   - API 키가 설정되어 있지 않아도 기본 테스트는 실행됨
   - 실제 번역 테스트는 모의(mock) 결과로 대체됨

## 🎯 테스트 목적

이 테스트는 다음을 검증합니다:

1. **기능 정확성**: 새로 구현된 기능들이 올바르게 동작하는지
2. **데이터 무결성**: 기존 번역 데이터가 정확히 추출되는지
3. **통합 동작**: 전체 번역 파이프라인이 원활히 작동하는지
4. **성능**: 대용량 데이터 처리 시 성능 이슈가 없는지

## 💡 추가 테스트 개발

새로운 테스트를 추가하려면:

1. `tests/` 폴더에 `test_새기능.py` 파일 생성
2. `TestExistingTranslations` 클래스를 참고하여 테스트 클래스 작성
3. `test.py`에 새 테스트 추가

## 🔧 문제 해결

문제 발생 시:
1. Python 버전 확인 (3.8 이상 필요)
2. 의존성 재설치
3. 테스트 데이터 재생성
4. 로그 확인 및 오류 메시지 분석

도움이 필요하면 프로젝트 이슈 트래커에 문의하세요! 