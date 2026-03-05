from .java.java_parser import JavaParser

# 언어명 → 파서 인스턴스 매핑 (새 언어 추가 시 여기만 수정)
PARSERS = {
    "java": JavaParser(),
}
