"""
엣지 관계를 인메모리로 해석하는 모듈.

파서가 추출한 원시 엣지(호출명, 객체명 등)를 인메모리 인덱스를 활용해
실제 qualname 쌍으로 변환합니다. DB 의존성 없음 — 순수 인메모리 로직입니다.
"""
import logging

from .models import (
    ParsedType, ParsedField, ParsedMethod,
    ParsedCallEdge, ParsedParameterEdge, ParsedReturnEdge,
)

logger = logging.getLogger(__name__)


class EdgeLinker:
    """
    [엣지 해석기 — 순수 인메모리]

    인메모리에 축적된 타입/필드/메서드 정보를 바탕으로
    파서가 생성한 원시 엣지를 DB에 기록할 수 있는 형태로 변환합니다.

    사용 흐름:
      1. 생성자에서 인덱스 자동 구축
      2. resolve_*() 메서드로 각 엣지 유형 해석 → DB 기록용 배치 반환
    """

    def __init__(
        self,
        types: dict[str, ParsedType],
        fields: dict[str, ParsedField],
        methods: dict[str, ParsedMethod],
    ):
        self._types = types
        self._fields = fields
        self._methods = methods

        # 인덱스 구축
        self._build_indexes()

    # -----------------------------------------------------------------------
    # 인메모리 인덱스 구축
    # -----------------------------------------------------------------------

    def _build_indexes(self):
        """엣지 해석에 필요한 인메모리 인덱스를 구축합니다."""
        # name → qualname (동명 타입 시 마지막 등록이 우선 — 향후 개선 대상)
        self._type_by_name: dict[str, str] = {
            t.name: t.qualname for t in self._types.values()
        }
        # class_qualname → {method_name → [ParsedMethod]}
        self._methods_by_class: dict[str, dict[str, list[ParsedMethod]]] = {}
        for m in self._methods.values():
            cls = self._methods_by_class.setdefault(m.class_qualname, {})
            cls.setdefault(m.name, []).append(m)

        # class_qualname → {field_name → ParsedField}
        self._fields_by_class: dict[str, dict[str, ParsedField]] = {}
        for f in self._fields.values():
            cls = self._fields_by_class.setdefault(f.type_qualname, {})
            cls[f.name] = f

    # -----------------------------------------------------------------------
    # 엣지 해석 (DB 접근 없음, 배치 반환)
    # -----------------------------------------------------------------------

    def resolve_parameter_edges(self, param_edges: list[ParsedParameterEdge]) -> list[dict]:
        """HAS_PARAMETER 엣지를 해석하여 DB 기록용 배치를 반환합니다."""
        batch = []
        for edge in param_edges:
            for type_name in edge.param_info["type"]["layout"]:
                type_qualname = self._type_by_name.get(type_name)
                if type_qualname:
                    batch.append({
                        "method_qualname": edge.method_qualname,
                        "type_qualname": type_qualname,
                    })
        return batch

    def resolve_return_edges(self, return_edges: list[ParsedReturnEdge]) -> list[dict]:
        """RETURNS 엣지를 해석하여 DB 기록용 배치를 반환합니다."""
        batch = []
        for edge in return_edges:
            for type_name in edge.return_info["layout"]:
                type_qualname = self._type_by_name.get(type_name)
                if type_qualname:
                    batch.append({
                        "method_qualname": edge.method_qualname,
                        "type_qualname": type_qualname,
                    })
        return batch

    def resolve_calls(self, calls: list[ParsedCallEdge]) -> tuple[list[dict], list[dict]]:
        """
        CALLS 엣지를 해석하여 두 종류의 배치를 반환합니다.

        Returns:
            (resolved_batch, external_batch) 튜플
            - resolved_batch: 프로젝트 내 METHOD → CALLS → METHOD
            - external_batch: 외부 호출 METHOD → CALLS → EXTERNAL_CALL
        """
        resolved_batch = []
        external_batch = []

        for call in calls:
            target_qualname = self._resolve_call_target(
                call.caller_qualname, call.target_method_name, call.object_name,
            )
            if target_qualname:
                resolved_batch.append({
                    "caller_qualname": call.caller_qualname,
                    "callee_qualname": target_qualname,
                })
            else:
                ext_qualname = (
                    f"{call.object_name}.{call.target_method_name}"
                    if call.object_name
                    else call.target_method_name
                )
                external_batch.append({
                    "caller_qualname": call.caller_qualname,
                    "ext_qualname": ext_qualname,
                    "name": call.target_method_name,
                    "signature": f"{ext_qualname}()",
                })

        logger.info(
            f"CALLS edges: {len(resolved_batch)} resolved, "
            f"{len(external_batch)} external"
        )
        return resolved_batch, external_batch

    # -----------------------------------------------------------------------
    # CALLS 관계 찾기
    # -----------------------------------------------------------------------

    def _resolve_call_target(
        self, caller_qualname: str, target_name: str, obj_name: str,
    ) -> str | None:
        """호출 대상을 인메모리 인덱스로 해석하여 METHOD qualname을 반환합니다."""
        if obj_name:
            # Case 1a: obj_name이 타입명 → 해당 타입의 메서드 탐색
            type_q = self._type_by_name.get(obj_name)
            if type_q:
                methods = self._methods_by_class.get(type_q, {}).get(target_name, [])
                if methods:
                    return methods[0].qualname

            # Case 1b: obj_name이 필드명 → 필드 타입의 메서드 탐색
            caller_method = self._methods.get(caller_qualname)
            if caller_method:
                field = self._fields_by_class.get(
                    caller_method.class_qualname, {},
                ).get(obj_name)
                if field and field.field_type.get("layout"):
                    field_type_name = field.field_type["layout"][0]
                    type_q = self._type_by_name.get(field_type_name)
                    if type_q:
                        methods = self._methods_by_class.get(type_q, {}).get(target_name, [])
                        if methods:
                            return methods[0].qualname
        else:
            # Case 2: obj_name 없음 → 같은 클래스의 형제 메서드 탐색
            caller_method = self._methods.get(caller_qualname)
            if caller_method:
                methods = self._methods_by_class.get(
                    caller_method.class_qualname, {},
                ).get(target_name, [])
                if methods:
                    return methods[0].qualname

        return None
