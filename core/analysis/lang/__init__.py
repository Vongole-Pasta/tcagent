from .java.java_parser import JavaParser

# 언어명 → 파서 인스턴스 매핑 (새 언어 추가 시 여기만 수정)
PARSERS = {
    "java": JavaParser(),
}


def collect_root_patterns() -> list[str]:
    """
    등록된 모든 파서 언어별 코드베이스의 ROOT_PATTERNS를 우선순위 순으로 수집합니다.
    각 파서가 정의한 순서를 유지하며, 중복은 제거됩니다.

    Returns:
        소스 루트 패턴 목록 (예: ["src/main/java/", "src/"])
    """
    seen = set()
    patterns = []
    for parser in PARSERS.values():
        for pattern in getattr(parser, "ROOT_PATTERNS", []):
            if pattern not in seen:
                seen.add(pattern)
                patterns.append(pattern)
    return patterns
