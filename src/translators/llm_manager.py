"""
LLM 모델 관리자 모듈

다양한 LLM 제공업체(OpenAI, Gemini, Claude, DeepSeek, Ollama)를 지원하는 통합 관리자
"""

import logging
import os
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class LLMManager:
    """다양한 LLM 모델을 관리하는 클래스"""

    def __init__(self):
        self.supported_providers = {
            "openai": {
                "name": "OpenAI",
                "api_key_env": "OPENAI_API_KEY",
                "client_class": None,
                "models": [],
            },
            "gemini": {
                "name": "Google Gemini",
                "api_key_env": "GOOGLE_API_KEY",
                "client_class": None,
                "models": [],
            },
            "claude": {
                "name": "Anthropic Claude",
                "api_key_env": "ANTHROPIC_API_KEY",
                "client_class": None,
                "models": [],
            },
            "deepseek": {
                "name": "DeepSeek",
                "api_key_env": "DEEPSEEK_API_KEY",
                "client_class": None,
                "models": [],
            },
            "ollama": {
                "name": "Ollama",
                "api_key_env": None,  # Ollama는 API 키 불필요
                "client_class": None,
                "models": [],
            },
        }

        # 현재 선택된 모델 정보
        self.current_provider = None
        self.current_model = None
        self.current_client = None

    def get_available_providers(self) -> List[str]:
        """사용 가능한 제공업체 목록 반환"""
        return list(self.supported_providers.keys())

    def get_provider_info(self, provider_id: str) -> Dict:
        """특정 제공업체 정보 반환"""
        return self.supported_providers.get(provider_id, {})

    def set_api_key(self, provider_id: str, api_key: str) -> bool:
        """API 키 설정"""
        if provider_id not in self.supported_providers:
            return False

        env_var = self.supported_providers[provider_id]["api_key_env"]
        if env_var:
            os.environ[env_var] = api_key
            logger.info(f"{provider_id} API 키 설정 완료")

        return True

    def get_api_key(self, provider_id: str) -> Optional[str]:
        """API 키 조회"""
        if provider_id not in self.supported_providers:
            return None

        env_var = self.supported_providers[provider_id]["api_key_env"]
        if env_var:
            return os.environ.get(env_var)

        return None

    async def get_available_models(self, provider_id: str) -> List[Dict]:
        """특정 제공업체의 사용 가능한 모델 목록 조회"""
        if provider_id not in self.supported_providers:
            return []

        try:
            if provider_id == "openai":
                return await self._get_openai_models()
            elif provider_id == "gemini":
                return await self._get_gemini_models()
            elif provider_id == "claude":
                return await self._get_claude_models()
            elif provider_id == "deepseek":
                return await self._get_deepseek_models()
            elif provider_id == "ollama":
                return await self._get_ollama_models()
            else:
                return []
        except Exception as e:
            logger.error(f"{provider_id} 모델 목록 조회 실패: {e}")
            return []

    async def _get_openai_models(self) -> List[Dict]:
        """OpenAI 모델 목록 조회"""
        try:
            from openai import AsyncOpenAI

            api_key = self.get_api_key("openai")
            if not api_key:
                logger.warning("OpenAI API 키가 설정되지 않았습니다")
                return []

            client = AsyncOpenAI(api_key=api_key)
            models = await client.models.list()

            # 텍스트 생성 모델만 필터링
            text_models = []
            for model in models.data:
                if any(keyword in model.id.lower() for keyword in ["gpt", "text"]):
                    text_models.append(
                        {
                            "id": model.id,
                            "name": model.id,
                            "description": f"OpenAI {model.id}",
                        }
                    )

            # 일반적인 모델들 우선 정렬
            priority_models = ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "gpt-3.5-turbo"]
            text_models.sort(
                key=lambda x: priority_models.index(x["id"])
                if x["id"] in priority_models
                else len(priority_models)
            )

            return text_models

        except Exception as e:
            logger.error(f"OpenAI 모델 조회 실패: {e}")
            return []

    async def _get_gemini_models(self) -> List[Dict]:
        """Gemini 모델 목록 조회"""
        try:
            import google.generativeai as genai

            api_key = self.get_api_key("gemini")
            if not api_key:
                logger.warning("Google API 키가 설정되지 않았습니다")
                return []

            genai.configure(api_key=api_key)

            models = []
            for model in genai.list_models():
                if "generateContent" in model.supported_generation_methods:
                    models.append(
                        {
                            "id": model.name.replace("models/", ""),
                            "name": model.display_name,
                            "description": f"Google {model.display_name}",
                        }
                    )

            return models

        except Exception as e:
            logger.error(f"Gemini 모델 조회 실패: {e}")
            return []

    async def _get_claude_models(self) -> List[Dict]:
        """Claude 모델 목록 조회 (하드코딩 - API에서 모델 목록 제공 안함)"""
        try:
            api_key = self.get_api_key("claude")
            if not api_key:
                logger.warning("Anthropic API 키가 설정되지 않았습니다")
                return []

            # Claude 모델들 (하드코딩 - API에서 모델 목록을 제공하지 않음)
            models = [
                {
                    "id": "claude-opus-4-20250514",
                    "name": "Claude Opus 4",
                    "description": "Anthropic Claude Opus 4 (최신 최고성능)",
                },
                {
                    "id": "claude-sonnet-4-20250514",
                    "name": "Claude Sonnet 4",
                    "description": "Anthropic Claude Sonnet 4 (최신 고성능)",
                },
                {
                    "id": "claude-3-7-sonnet-20250219",
                    "name": "Claude Sonnet 3.7",
                    "description": "Anthropic Claude 3.7 Sonnet (향상된 성능)",
                },
                {
                    "id": "claude-3-5-sonnet-20241022",
                    "name": "Claude 3.5 Sonnet v2",
                    "description": "Anthropic Claude 3.5 Sonnet v2 (최신)",
                },
                {
                    "id": "claude-3-5-sonnet-20240620",
                    "name": "Claude 3.5 Sonnet",
                    "description": "Anthropic Claude 3.5 Sonnet",
                },
                {
                    "id": "claude-3-5-haiku-20241022",
                    "name": "Claude 3.5 Haiku",
                    "description": "Anthropic Claude 3.5 Haiku (빠르고 효율적)",
                },
                {
                    "id": "claude-3-haiku-20240307",
                    "name": "Claude 3 Haiku",
                    "description": "Anthropic Claude 3 Haiku",
                },
            ]

            return models

        except Exception as e:
            logger.error(f"Claude 모델 조회 실패: {e}")
            return []

    async def _get_deepseek_models(self) -> List[Dict]:
        """DeepSeek 모델 목록 조회"""
        try:
            # DeepSeek API 클라이언트 (OpenAI 호환)
            from openai import AsyncOpenAI

            api_key = self.get_api_key("deepseek")
            if not api_key:
                logger.warning("DeepSeek API 키가 설정되지 않았습니다")
                return []

            client = AsyncOpenAI(api_key=api_key, base_url="https://api.deepseek.com")

            models = await client.models.list()

            deepseek_models = []
            for model in models.data:
                deepseek_models.append(
                    {
                        "id": model.id,
                        "name": model.id,
                        "description": f"DeepSeek {model.id}",
                    }
                )

            return deepseek_models

        except Exception as e:
            logger.error(f"DeepSeek 모델 조회 실패: {e}")
            return []

    async def _get_ollama_models(self) -> List[Dict]:
        """Ollama 모델 목록 조회"""
        try:
            import httpx

            # Ollama API 호출
            async with httpx.AsyncClient() as client:
                response = await client.get("http://localhost:11434/api/tags")
                response.raise_for_status()

                data = response.json()
                models = []

                for model in data.get("models", []):
                    models.append(
                        {
                            "id": model["name"],
                            "name": model["name"],
                            "description": f"Ollama {model['name']}",
                        }
                    )

                return models

        except Exception as e:
            logger.error(f"Ollama 모델 조회 실패: {e}")
            return []

    async def create_llm_client(self, provider_id: str, model_id: str, **kwargs):
        """LLM 클라이언트 생성"""
        if provider_id not in self.supported_providers:
            raise ValueError(f"지원하지 않는 제공업체: {provider_id}")

        try:
            if provider_id == "openai":
                return await self._create_openai_client(model_id, **kwargs)
            elif provider_id == "gemini":
                return await self._create_gemini_client(model_id, **kwargs)
            elif provider_id == "claude":
                return await self._create_claude_client(model_id, **kwargs)
            elif provider_id == "deepseek":
                return await self._create_deepseek_client(model_id, **kwargs)
            elif provider_id == "ollama":
                return await self._create_ollama_client(model_id, **kwargs)
            else:
                raise ValueError(f"지원하지 않는 제공업체: {provider_id}")
        except Exception as e:
            logger.error(f"{provider_id} 클라이언트 생성 실패: {e}")
            raise

    async def _create_openai_client(self, model_id: str, **kwargs):
        """OpenAI 클라이언트 생성 (LangChain 호환)"""
        from langchain_openai import ChatOpenAI

        api_key = self.get_api_key("openai")
        if not api_key:
            raise ValueError("OpenAI API 키가 설정되지 않았습니다")

        # 중복 매개변수 제거
        filtered_kwargs = {
            k: v for k, v in kwargs.items() if k not in ["temperature", "max_tokens"]
        }

        return ChatOpenAI(
            model=model_id,
            openai_api_key=api_key,
            temperature=kwargs.get("temperature", 0.1),
            **filtered_kwargs,
        )

    async def _create_gemini_client(self, model_id: str, **kwargs):
        """Gemini 클라이언트 생성 (LangChain 호환)"""
        from langchain_google_genai import ChatGoogleGenerativeAI

        api_key = self.get_api_key("gemini")
        if not api_key:
            raise ValueError("Google API 키가 설정되지 않았습니다")

        # 중복 매개변수 제거
        filtered_kwargs = {
            k: v for k, v in kwargs.items() if k not in ["temperature", "max_tokens"]
        }

        return ChatGoogleGenerativeAI(
            model=model_id,
            google_api_key=api_key,
            temperature=kwargs.get("temperature", 0.1),
            **filtered_kwargs,
        )

    async def _create_claude_client(self, model_id: str, **kwargs):
        """Claude 클라이언트 생성 (LangChain 호환)"""
        from langchain_anthropic import ChatAnthropic

        api_key = self.get_api_key("claude")
        if not api_key:
            raise ValueError("Anthropic API 키가 설정되지 않았습니다")

        # 중복 매개변수 제거
        filtered_kwargs = {
            k: v for k, v in kwargs.items() if k not in ["temperature", "max_tokens"]
        }

        return ChatAnthropic(
            model=model_id,
            anthropic_api_key=api_key,
            temperature=kwargs.get("temperature", 0.1),
            **filtered_kwargs,
        )

    async def _create_deepseek_client(self, model_id: str, **kwargs):
        """DeepSeek 클라이언트 생성 (LangChain 호환)"""
        from langchain_openai import ChatOpenAI

        api_key = self.get_api_key("deepseek")
        if not api_key:
            raise ValueError("DeepSeek API 키가 설정되지 않았습니다")

        # 중복 매개변수 제거
        filtered_kwargs = {
            k: v for k, v in kwargs.items() if k not in ["temperature", "max_tokens"]
        }

        return ChatOpenAI(
            model=model_id,
            openai_api_key=api_key,
            base_url="https://api.deepseek.com",
            temperature=kwargs.get("temperature", 0.1),
            **filtered_kwargs,
        )

    async def _create_ollama_client(self, model_id: str, **kwargs):
        """Ollama 클라이언트 생성 (LangChain 호환)"""
        from langchain_ollama import ChatOllama

        # 중복 매개변수 제거
        filtered_kwargs = {k: v for k, v in kwargs.items() if k not in ["temperature"]}

        return ChatOllama(
            model=model_id,
            base_url="http://localhost:11434",
            temperature=kwargs.get("temperature", 0.1),
            **filtered_kwargs,
        )

    def set_current_model(self, provider_id: str, model_id: str):
        """현재 모델 설정"""
        self.current_provider = provider_id
        self.current_model = model_id
        logger.info(f"현재 모델 설정: {provider_id}/{model_id}")

    def get_current_model(self) -> Tuple[Optional[str], Optional[str]]:
        """현재 모델 정보 반환"""
        return self.current_provider, self.current_model
