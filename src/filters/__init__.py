"""
번역 대상 필터링 모듈

이 모듈은 모드팩에서 추출된 파일들 중에서
실제로 번역이 필요한 키들을 골라내는 역할을 합니다.
"""

from .base import (
    BaseFilter,
    ExtendedFilterManager,
    FilterManager,
    GenericJSONFilter,
    TranslationEntry,
)

# 모드별 필터들 import
from .ftbquests import (
    FTBQuestsChapterFilter,
    FTBQuestsEnUsFilter,
    FTBQuestsFilter,
    FTBQuestsRewardTableFilter,
)
from .kubejs import (
    KubeJSClientFilter,
    KubeJSFilter,
    KubeJSServerFilter,
    KubeJSStartupFilter,
)
from .origins import GlobalPacksOriginFilter, OriginsFilter
from .patchouli import PatchouliCategoryFilter, PatchouliEntryFilter, PatchouliFilter
from .paxi import PaxiDatapackFilter, PaxiFilter, PaxiResourcepackFilter
from .puffish_skills import (
    PuffishSkillsCategoryFilter,
    PuffishSkillsDefinitionsFilter,
    PuffishSkillsFilter,
)
from .tconstruct import TConstructFilter

__all__ = [
    # 기본 클래스들
    "BaseFilter",
    "FilterManager",
    "ExtendedFilterManager",
    "GenericJSONFilter",
    "TranslationEntry",
    # FTBQuests 필터들
    "FTBQuestsFilter",
    "FTBQuestsChapterFilter",
    "FTBQuestsRewardTableFilter",
    "FTBQuestsEnUsFilter",
    # KubeJS 필터들
    "KubeJSFilter",
    "KubeJSClientFilter",
    "KubeJSStartupFilter",
    "KubeJSServerFilter",
    # Origins 필터들
    "OriginsFilter",
    "GlobalPacksOriginFilter",
    # Patchouli 필터들
    "PatchouliFilter",
    "PatchouliCategoryFilter",
    "PatchouliEntryFilter",
    # TConstruct 필터들
    "TConstructFilter",
    # PuffishSkills 필터들
    "PuffishSkillsFilter",
    "PuffishSkillsCategoryFilter",
    "PuffishSkillsDefinitionsFilter",
    # Paxi 필터들
    "PaxiFilter",
    "PaxiDatapackFilter",
    "PaxiResourcepackFilter",
]
