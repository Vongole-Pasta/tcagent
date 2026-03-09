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
        file_contexts: dict[str, dict] | None = None,
    ):
        self._types = types
        self._fields = fields
        self._methods = methods
        self._file_contexts = file_contexts or {}

        # 인덱스 구축
        self._build_indexes()

    # -----------------------------------------------------------------------
    # 인메모리 인덱스 구축
    # -----------------------------------------------------------------------

    def _build_indexes(self):
        """엣지 해석에 필요한 인메모리 인덱스를 구축합니다."""
        # 1) name → [qualname] (동명 타입을 리스트로 관리)
        #    예: "User" → ["com.example.model.User", "com.other.model.User"]
        self._types_by_name: dict[str, list[str]] = {}
        for t in self._types.values():
            self._types_by_name.setdefault(t.name, []).append(t.qualname)

        # 2) qualname → [부모 qualname] (상속 계층)
        #    supertypes의 단순 이름을 qualname으로 해석하여 저장
        self._parent_types: dict[str, list[str]] = {}
        for t in self._types.values():
            parents = []
            for parent_name in t.supertypes:
                parent_q = self._resolve_type_name_global(parent_name)
                if parent_q:
                    parents.append(parent_q)
            if parents:
                self._parent_types[t.qualname] = parents

        # 3) class_qualname → {method_name → [ParsedMethod]}
        self._methods_by_class: dict[str, dict[str, list[ParsedMethod]]] = {}
        for m in self._methods.values():
            cls = self._methods_by_class.setdefault(m.class_qualname, {})
            cls.setdefault(m.name, []).append(m)

        # 4) class_qualname → {field_name → ParsedField}
        self._fields_by_class: dict[str, dict[str, ParsedField]] = {}
        for f in self._fields.values():
            cls = self._fields_by_class.setdefault(f.type_qualname, {})
            cls[f.name] = f

    # -----------------------------------------------------------------------
    # 타입 이름 해석
    # -----------------------------------------------------------------------

    def _resolve_type_name_global(self, type_name: str) -> str | None:
        """
        타입 단순 이름을 qualname으로 해석합니다 (글로벌 — import 컨텍스트 없이).
        인덱스 구축 시 사용. 후보가 1개면 확정, 여러 개면 None.
        """
        candidates = self._types_by_name.get(type_name, [])
        if len(candidates) == 1:
            return candidates[0]
        return None

    def _resolve_type_in_file(self, type_name: str, file_path: str) -> str | None:
        """
        파일의 import 컨텍스트를 활용하여 타입 이름을 qualname으로 해석합니다.

        해석 우선순위:
          1. 후보가 1개뿐이면 바로 확정
          2. 정규 import에서 매칭 (예: import com.ex.User → "User" → "com.ex.User")
          3. 같은 패키지/네임스페이스의 타입
          4. 와일드카드 import 패키지의 타입
        """
        candidates = self._types_by_name.get(type_name, [])
        if not candidates:
            return None
        if len(candidates) == 1:
            return candidates[0]

        ctx = self._file_contexts.get(file_path)
        if not ctx:
            return None

        # 1. 정규 import 매칭
        for imp in ctx["imports"]:
            if imp.endswith(f".{type_name}") and imp in self._types:
                return imp

        # 2. 같은 패키지/네임스페이스
        package = ctx["package"]
        if package:
            for cand in candidates:
                cand_pkg = cand.rsplit(".", 1)[0] if "." in cand else ""
                if cand_pkg == package:
                    return cand

        # 3. 와일드카드 import
        for wp in ctx["wildcard_imports"]:
            for cand in candidates:
                cand_pkg = cand.rsplit(".", 1)[0] if "." in cand else ""
                if cand_pkg == wp:
                    return cand

        return None

    # -----------------------------------------------------------------------
    # 상속 계층 탐색
    # -----------------------------------------------------------------------

    def _find_method_in_hierarchy(self, type_qualname: str, method_name: str) -> list[ParsedMethod]:
        """
        타입의 상속 계층을 따라 메서드를 탐색합니다.
        자기 자신 → 부모 → 부모의 부모 ... 순서로 BFS 탐색합니다.
        순환 참조 방지를 위해 visited set을 사용합니다.
        """
        visited = set()
        queue = [type_qualname]

        while queue:
            current = queue.pop(0)
            if current in visited:
                continue
            visited.add(current)

            methods = self._methods_by_class.get(current, {}).get(method_name, [])
            if methods:
                return methods

            # 부모 타입으로 확장
            parents = self._parent_types.get(current, [])
            queue.extend(parents)

        return []

    # -----------------------------------------------------------------------
    # 오버로딩 구분
    # -----------------------------------------------------------------------

    def _pick_by_arg_count(self, methods: list[ParsedMethod], arg_count: int) -> str | None:
        """
        오버로딩된 메서드 목록에서 인자 개수로 필터링합니다.
        - 후보 0개: None
        - 후보 1개: 그대로 반환
        - 후보 여러 개 + arg_count >= 0: 인자 수 일치하는 것 선택
        - 그래도 여러 개 or arg_count < 0: 첫 번째 반환 (best effort)
        """
        if not methods:
            return None
        if len(methods) == 1:
            return methods[0].qualname

        if arg_count >= 0:
            matched = [m for m in methods if len(m.params) == arg_count]
            if len(matched) == 1:
                return matched[0].qualname

        return methods[0].qualname  # fallback

    # -----------------------------------------------------------------------
    # 노드 데이터 보강 (DB 접근 없음)
    # -----------------------------------------------------------------------

    def resolve_supertype_qualnames(self):
        """
        ParsedType.supertypes를 단순 이름에서 qualname으로 변환합니다.

        _build_indexes()의 _parent_types는 글로벌 해석(후보 1개만 확정)으로 구축되지만,
        이 메서드는 파일별 import 컨텍스트를 활용하여 동명 타입도 정확히 해석합니다.
        """
        for t in self._types.values():
            resolved = []
            for parent_name in t.supertypes:
                parent_q = self._resolve_type_in_file(parent_name, t.file_path)
                if parent_q:
                    resolved.append(parent_q)
                else:
                    resolved.append(parent_name)  # 해석 실패 시 원본 유지
            t.supertypes = resolved

    # -----------------------------------------------------------------------
    # 엣지 해석 (DB 접근 없음, 배치 반환)
    # -----------------------------------------------------------------------

    def resolve_parameter_edges(self, param_edges: list[ParsedParameterEdge]) -> list[dict]:
        """HAS_PARAMETER 엣지를 해석하여 DB 기록용 배치를 반환합니다."""
        batch = []
        for edge in param_edges:
            caller_method = self._methods.get(edge.method_qualname)
            caller_type = self._types.get(caller_method.class_qualname) if caller_method else None
            caller_file = caller_type.file_path if caller_type else None

            for type_name in edge.param_info["type"]["layout"]:
                type_qualname = (self._resolve_type_in_file(type_name, caller_file)
                                 if caller_file else self._resolve_type_name_global(type_name))
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
            caller_method = self._methods.get(edge.method_qualname)
            caller_type = self._types.get(caller_method.class_qualname) if caller_method else None
            caller_file = caller_type.file_path if caller_type else None

            for type_name in edge.return_info["layout"]:
                type_qualname = (self._resolve_type_in_file(type_name, caller_file)
                                 if caller_file else self._resolve_type_name_global(type_name))
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
            target_qualname = self._resolve_call_target(call)
            if target_qualname:
                call.callee_qualname = target_qualname
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
                call.callee_qualname = ext_qualname
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
    # CALLS 해석 — 메인 로직
    # -----------------------------------------------------------------------

    def _resolve_call_target(self, call: ParsedCallEdge) -> str | None:
        """
        호출 대상을 인메모리 인덱스로 해석합니다.

        해석 전략 (우선순위 순):
          1. obj_name 있음 → 타입명/필드명으로 해석 + 상속 계층 탐색
          2. obj_name 없음 + receiver_method 있음 (체이닝) → 수신 메서드 리턴 타입에서 탐색
          3. obj_name 없음 → 같은 클래스 + 상속 계층에서 형제 메서드 탐색
          4. 오버로딩: 후보가 여러 개면 arg_count로 필터링
        """
        caller_method = self._methods.get(call.caller_qualname)
        caller_type = self._types.get(caller_method.class_qualname) if caller_method else None
        caller_file = caller_type.file_path if caller_type else None

        if call.object_name:
            return self._resolve_with_object(call, caller_method, caller_file)
        elif call.receiver_method:
            return self._resolve_chained_call(call, caller_method, caller_file)
        else:
            return self._resolve_sibling_call(call, caller_method)

    def _resolve_with_object(self, call: ParsedCallEdge, caller_method, caller_file) -> str | None:
        """obj_name이 있는 호출을 해석합니다."""
        obj = call.object_name

        # Case 0: this/super 키워드 처리
        if obj == "this" and caller_method:
            methods = self._find_method_in_hierarchy(caller_method.class_qualname, call.target_method_name)
            return self._pick_by_arg_count(methods, call.arg_count)
        if obj == "super" and caller_method:
            # super.method() → 부모 타입에서부터 탐색 (자기 자신 스킵)
            parents = self._parent_types.get(caller_method.class_qualname, [])
            for parent_q in parents:
                methods = self._find_method_in_hierarchy(parent_q, call.target_method_name)
                if methods:
                    return self._pick_by_arg_count(methods, call.arg_count)
            return None

        # Case 1a: obj_name이 타입명 (정적 호출 또는 타입 참조)
        type_q = (self._resolve_type_in_file(obj, caller_file)
                  if caller_file else self._resolve_type_name_global(obj))
        if type_q:
            methods = self._find_method_in_hierarchy(type_q, call.target_method_name)
            return self._pick_by_arg_count(methods, call.arg_count)

        # Case 1b: obj_name이 필드명 → 필드의 타입에서 탐색
        if caller_method:
            field = self._fields_by_class.get(caller_method.class_qualname, {}).get(obj)
            if field and field.field_type.get("layout"):
                field_type_name = field.field_type["layout"][0]
                type_q = (self._resolve_type_in_file(field_type_name, caller_file)
                          if caller_file else self._resolve_type_name_global(field_type_name))
                if type_q:
                    methods = self._find_method_in_hierarchy(type_q, call.target_method_name)
                    return self._pick_by_arg_count(methods, call.arg_count)

        return None

    def _resolve_chained_call(self, call: ParsedCallEdge, caller_method, caller_file) -> str | None:
        """
        체이닝 호출을 해석합니다.
        예: userService.getUser(id).getName()
        → receiver_object=userService, receiver_method=getUser
        → getUser의 리턴 타입에서 getName 탐색
        """
        # 수신 메서드 찾기 (receiver_object.receiver_method())
        recv_call = ParsedCallEdge(
            caller_qualname=call.caller_qualname,
            target_method_name=call.receiver_method,
            object_name=call.receiver_object,
        )
        recv_qualname = (self._resolve_with_object(recv_call, caller_method, caller_file)
                         if call.receiver_object
                         else self._resolve_sibling_call(recv_call, caller_method))

        if not recv_qualname:
            return None

        # 수신 메서드의 리턴 타입 → 그 타입에서 target 메서드 탐색
        recv_method = self._methods.get(recv_qualname)
        if not recv_method or not recv_method.return_type or not recv_method.return_type.get("layout"):
            return None

        return_type_name = recv_method.return_type["layout"][0]
        type_q = (self._resolve_type_in_file(return_type_name, caller_file)
                  if caller_file else self._resolve_type_name_global(return_type_name))
        if type_q:
            methods = self._find_method_in_hierarchy(type_q, call.target_method_name)
            return self._pick_by_arg_count(methods, call.arg_count)

        return None

    def _resolve_sibling_call(self, call: ParsedCallEdge, caller_method) -> str | None:
        """같은 클래스 + 상속 계층에서 형제 메서드를 탐색합니다."""
        if not caller_method:
            return None
        methods = self._find_method_in_hierarchy(caller_method.class_qualname, call.target_method_name)
        return self._pick_by_arg_count(methods, call.arg_count)
