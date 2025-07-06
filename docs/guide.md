# 가이드

## 설치

### 쉽고 빠른 설치 (easy_install)

Windows 사용자는 **easy_install 전용 패키지**(`auto-translate-easy-install.zip`)만 받아서 압축을 풀고 `run.bat` 을 실행하면 모든 과정이 자동으로 진행됩니다.

```text
1. (선택) uv 패키지 매니저 설치
   powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"

2. 패키지 다운로드
   https://github.com/kunho-park/auto-translate/releases/download/easy-install/auto-translate-easy-install.zip

3. 압축 해제 후 폴더 진입
   auto-translate-easy-install\easy_install

4. 실행
   run.bat
```

`run.bat` 스크립트는 다음 작업을 순서대로 수행합니다.

1. 최신 코드를 GitHub에서 가져와 업데이트(`update.bat` 호출)  
2. 필요 시 종속성 설치(`uv sync`) 및 가상 환경 생성  
3. `run_flet_gui.py` 실행으로 프로그램 시작  
4. 프로그램 종료 후 가상 환경 비활성화

> **TIP** `run.bat` 만 실행하면 `installer.bat` 가 자동으로 호출되므로 별도 실행이 필요하지 않습니다.

### 실행

설치 과정에서 이미 `run.bat` 이 실행되어 프로그램이 시작됩니다. 다음에 다시 실행하고 싶다면 동일하게 `easy_install` 폴더에서 `run.bat` 을 더블클릭하세요.

## 번역 방법

Auto-Translate Modpack Browser 는 두 가지 방식으로 번역을 수행할 수 있습니다.

### 1. GUI (권장)

1. 프로그램을 실행하면 모드팩 브라우저가 나타납니다.
2. 번역하려는 모드팩을 선택 후 "Translate" 버튼을 클릭합니다.
3. 번역 진행 상황은 진행 바(progress bar)로 확인할 수 있으며, 완료되면 결과를 저장하거나 바로 적용할 수 있습니다.

### 2. CLI (자동화)

`src/translators/modpack_translator.py` 의 `ModpackTranslator` 클래스를 직접 사용하는 파이썬 스크립트를 작성할 수 있습니다.

```python
from src.translators.modpack_translator import ModpackTranslator
import asyncio

async def main():
    translator = ModpackTranslator(
        modpack_path="./my_modpack",
        target_language="한국어",
        max_concurrent_requests=3,
        delay_between_requests_ms=500,
    )

    # 전체 워크플로우 실행 (수집 → 번역 → 저장)
    await translator.run_full_translation(
        output_path="translated.json",
        apply_to_files=True,
        output_dir="./translated_modpack"
    )

asyncio.run(main())
```

## 모델 선택

| LLM 제공자 | 모델 이름            | 특징                   | 권장 용도                          |
| ---------- | -------------------- | ---------------------- | ---------------------------------- |
| Google     | `gemini-2.0-flash` | 빠른 속도, 저렴한 비용 | 대량 번역, 빠른 피드백이 필요할 때 |
| Google     | `gemini-2.5-pro`   | 더 높은 품질, 비용 ↑  | 품질이 중요한 최종 릴리즈 번역     |
| OpenAI     | `gpt-4o-mini`      | 속도와 품질 균형       | 일반적인 번역 작업                 |
| OpenAI     | `gpt-4o`           | 최고 품질, 비용 ↑↑   | 번역 품질 검수, 소량 고품질 번역   |

> `src/translators/modpack_translator.py` 의 `run_full_translation` 메서드에서 `llm_provider`, `llm_model`, `temperature` 등을 지정하여 모델과 파라미터를 조정할 수 있습니다.

## 적용 방법

번역이 완료되면 두 가지 방식으로 결과를 적용할 수 있습니다.

1. **자동 적용**`run_full_translation(..., apply_to_files=True, output_dir="./translated_modpack")` 옵션을 사용하면 원본을 백업하고 번역 결과가 바로 파일에 반영됩니다.
2. **리소스팩 패키징**
   `enable_packaging=True` (기본값) 일 때, 번역된 리소스가 하나의 리소스팩(zip)으로 패키징됩니다.
   게임의 `resourcepacks` 폴더에 넣고 리소스팩을 활성화하면 적용 완료!

---

궁금한 점이나 기여하고 싶은 내용이 있다면 GitHub PR/Issue 로 알려 주세요. 😄
