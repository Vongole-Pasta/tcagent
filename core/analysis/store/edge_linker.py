"""
엣지 관계를 인메모리로 해석하는 모듈.

파서가 추출한 원시 엣지(호출명, 객체명 등)를 인메모리 인덱스를 활용해
실제 qualname 쌍으로 변환합니다. DB 의존성 없음 — 순수 인메모리 로직입니다.
"""
import logging

from .models import (
    ParsedField, ParsedMethod,
    ParsedCallEdge, ParsedParameterEdge, ParsedReturnEdge,
    ParsedRegistry, ResolvedEdges,
)

logger = logging.getLogger(__name__)


class EdgeLinker:
    """
    [엣지 해석기 — 순수 인메모리]

    ParsedRegistry에 축적된 타입/필드/메서드 정보를 바탕으로
    파서가 생성한 원시 엣지를 DB에 기록할 수 있는 형태로 변환합니다.

    사용 흐름:
      1. 생성자에서 ParsedRegistry를 받으면서 인덱스 구축
      2. resolve()로 모든 관계를 한 번에 해석 → ResolvedEdges에 모아서 반환
    """
    def __init__(self, registry: ParsedRegistry):
        self._registry = registry

        # 해석용 인덱스 (인스턴스별 독립)
        self._types_by_name: dict[str, list[str]] = {}
        self._parent_types: dict[str, list[str]] = {}
        self._methods_by_class: dict[str, dict[str, list[ParsedMethod]]] = {}
        self._fields_by_class: dict[str, dict[str, ParsedField]] = {}

        self._build_indexes()

    def _build_indexes(self):
        """엣지 해석에 필요한 인메모리 인덱스를 구축합니다."""
        # 1) name → [qualname] (동명 타입을 리스트로 관리)
        #    예: "User" → ["com.example.model.User", "com.other.model.User"]
        for t in self._registry.types.values():
            self._types_by_name.setdefault(t.name, []).append(t.qualname)

        # 2) qualname → [부모 qualname] (상속 계층)
        #    supertypes의 단순 이름을 qualname으로 해석하여 저장
        #    AS-IS 타입(DB 복원)은 supertypes가 이미 qualname이므로 직접 사용
        for t in self._registry.types.values():
            parents = []
            for parent_name in t.supertypes:
                if parent_name in self._registry.types:
                    parents.append(parent_name)                         # 이미 qualname (DB 복원)
                else:
                    parent_q = self._resolve_type_name_global(parent_name)
                    if parent_q:
                        parents.append(parent_q)                        # 단순 이름 → qualname
            if parents:
                self._parent_types[t.qualname] = parents

        # 3) class_qualname → {method_name → [ParsedMethod]}
        for m in self._registry.methods.values():
            cls = self._methods_by_class.setdefault(m.class_qualname, {})
            cls.setdefault(m.name, []).append(m)

        # 4) class_qualname → {field_name → ParsedField}
        for f in self._registry.fields.values():
            cls = self._fields_by_class.setdefault(f.type_qualname, {})
            cls[f.name] = f

    # -----------------------------------------------------------------------
    # 통합 해석 (DB 접근 없음)
    # -----------------------------------------------------------------------

    def resolve(self) -> ResolvedEdges:
        """
        모든 관계를 인메모리에서 해석합니다.

        1. supertypes 단순 이름 → qualname 변환 (registry.types 직접 변경)
        2. 엣지 배치 생성 (DB 기록용 dict 리스트)
        """
        self.resolve_supertype_qualnames()
        self._resolve_unresolved_vars()

        resolved_calls, external_calls = self.resolve_calls(self._registry.calls)

        return ResolvedEdges(
            contains_edges          = self.resolve_field_type_edges(),
            internal_calls_edges    = resolved_calls,
            external_calls_edges    = external_calls,
            has_parameter_edges     = self.resolve_parameter_edges(self._registry.param_edges),
            returns_edges           = self.resolve_return_edges(self._registry.return_edges),
        )

    # -----------------------------------------------------------------------
    # 노드 데이터 보강 (DB 접근 없음)
    # -----------------------------------------------------------------------

    def resolve_supertype_qualnames(self):
        """
        ParsedType.supertypes를 단순 이름에서 qualname으로 변환합니다.

        _build_indexes()의 _parent_types는 글로벌 해석(후보 1개만 확정)으로 구축되지만,
        이 메서드는 파일별 import 컨텍스트를 활용하여 동명 타입도 정확히 해석합니다.
        """
        for t in self._registry.types.values():
            resolved = []
            for parent_name in t.supertypes:
                if parent_name in self._registry.types:
                    resolved.append(parent_name)               # 이미 qualname (DB 복원) — skip
                else:
                    parent_q = self._resolve_type_in_file(parent_name, t.file_path)
                    resolved.append(parent_q or parent_name)   # 해석 실패 시 원본 유지
            t.supertypes = resolved

    def _resolve_unresolved_vars(self):
        """
        var 선언 중 메서드 리턴타입 추론이 필요한 변수를 해석합니다.
        unresolved_vars의 (메서드명, 객체명)으로 가상 호출을 해석하고,
        해당 메서드의 리턴타입을 local_vars에 추가합니다.
        CALLS 해석 전에 실행되어야 합니다.
        """
        for method in self._registry.methods.values():
            if not method.unresolved_vars:
                continue

            for var_name, (target_method, obj_name) in method.unresolved_vars.items():
                # 가상 ParsedCallEdge를 만들어 기존 해석 로직 재활용
                virtual_call = ParsedCallEdge(
                    caller_qualname=method.qualname,
                    target_method_name=target_method,
                    object_name=obj_name,
                )
                resolved_qualname = self._resolve_call_target(virtual_call)
                if not resolved_qualname:
                    continue

                # 해석된 메서드의 리턴타입에서 첫 번째 타입명 추출
                resolved_method = self._registry.methods.get(resolved_qualname)
                if not resolved_method or not resolved_method.return_type:
                    continue
                layout = resolved_method.return_type.get("layout", [])
                if layout:
                    method.local_vars[var_name] = layout[0]

    # -----------------------------------------------------------------------
    # CALLS 해석
    # -----------------------------------------------------------------------

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

    def _resolve_call_target(self, call: ParsedCallEdge) -> str | None:
        """
        호출 대상을 인메모리 인덱스로 해석합니다.

        해석 전략 (우선순위 순):
          1. obj_name 있음 → 타입명/필드명으로 해석 + 상속 계층 탐색
          2. obj_name 없음 + receiver_chain 있음 (체이닝) → 체인을 순회하며 리턴 타입 추적
          3. obj_name 없음 → 같은 클래스 + 상속 계층에서 형제 메서드 탐색
          4. 오버로딩: 후보가 여러 개면 arg_count로 필터링
        """
        caller_method = self._registry.methods.get(call.caller_qualname)
        caller_type = self._registry.types.get(caller_method.class_qualname) if caller_method else None
        caller_file = caller_type.file_path if caller_type else None

        if call.object_name:
            return self._resolve_with_object(call, caller_method, caller_file)
        elif call.receiver_chain:
            return self._resolve_chained_call(call, caller_method, caller_file)
        else:
            return self._resolve_sibling_call(call, caller_method)

    def _resolve_with_object(self, call: ParsedCallEdge, caller_method, caller_file) -> str | None:
        """
        obj_name이 있는 호출을 해석합니다.

        예: userService.getUser(id)
          → obj_name="userService" (필드명), target_method_name="getUser"
          → userService 필드의 타입(UserService)에서 getUser 메서드 탐색
        """
        obj = call.object_name

        # Case 0: this/super 키워드 처리
        #   예: this.validate(id) → 자신의 클래스(UserService) + 상속 계층에서 validate 탐색
        if obj == "this" and caller_method:
            methods = self._find_method_in_hierarchy(caller_method.class_qualname, call.target_method_name)
            return self._pick_by_arg_count(methods, call.arg_count)
        if obj == "super" and caller_method:
            # 예: super.onCreate() → 부모 타입(AppCompatActivity)에서부터 탐색 (자기 자신 스킵)
            parents = self._parent_types.get(caller_method.class_qualname, [])
            for parent_q in parents:
                methods = self._find_method_in_hierarchy(parent_q, call.target_method_name)
                if methods:
                    return self._pick_by_arg_count(methods, call.arg_count)
            return None

        # Case 1a: obj_name이 타입명 (정적 호출 또는 타입 참조)
        #   예: UserService.getInstance() → obj="UserService"를 qualname으로 해석 → 정적 메서드 탐색
        type_q = (self._resolve_type_in_file(obj, caller_file)
                  if caller_file else self._resolve_type_name_global(obj))
        if type_q:
            methods = self._find_method_in_hierarchy(type_q, call.target_method_name)
            return self._pick_by_arg_count(methods, call.arg_count)

        # Case 1b: obj_name이 필드명 → 필드의 타입에서 탐색
        #   예: userRepo.findById(id) → obj="userRepo" 필드의 타입(UserRepository)에서 findById 탐색
        if caller_method:
            field = self._fields_by_class.get(caller_method.class_qualname, {}).get(obj)
            if field and field.field_type.get("layout"):
                field_type_name = field.field_type["layout"][0]
                type_q = (self._resolve_type_in_file(field_type_name, caller_file)
                          if caller_file else self._resolve_type_name_global(field_type_name))
                if type_q:
                    methods = self._find_method_in_hierarchy(type_q, call.target_method_name)
                    return self._pick_by_arg_count(methods, call.arg_count)

        # Case 1c: obj_name이 로컬 변수명 → 로컬 변수의 타입에서 탐색
        #   예: Member member = repo.find(...);
        #      member.recordLogin()
        #   → obj="member", local_vars={"member": "Member"} → Member 타입에서 recordLogin 탐색
        if caller_method and caller_method.local_vars:
            local_type_name = caller_method.local_vars.get(obj)
            if local_type_name:
                type_q = (self._resolve_type_in_file(local_type_name, caller_file)
                          if caller_file else self._resolve_type_name_global(local_type_name))
                if type_q:
                    methods = self._find_method_in_hierarchy(type_q, call.target_method_name)
                    return self._pick_by_arg_count(methods, call.arg_count)

        # Case 1d: obj_name에 '.'이 포함된 복합 객체명 해석
        #   예1: ApiResponseCode.SUCCESS.getMessage() → obj="ApiResponseCode.SUCCESS"
        #        → "ApiResponseCode" ENUM 타입의 상수 "SUCCESS" → 해당 enum에서 getMessage 탐색
        #   예2: Outer.Inner.foo() → obj="Outer.Inner"
        #        → "Outer" 타입의 내부 클래스 "Outer$Inner" → 해당 내부 클래스에서 foo 탐색
        if "." in obj:
            result = self._resolve_dotted_object(obj, call.target_method_name, call.arg_count, caller_file)
            if result:
                return result

        return None

    def _resolve_dotted_object(
        self, obj: str, target_method: str, arg_count: int, caller_file: str | None,
    ) -> str | None:
        """
        '.'이 포함된 복합 객체명을 반복적으로 해석합니다. 뎁스 제한 없음.

        해석 전략 (파트를 하나씩 소비하며 반복):
          1. obj를 '.' 기준으로 분리 → [part0, part1, part2, ...]
          2. part0을 타입으로 해석 → current_q
          3. 나머지 파트를 순회하며:
             a. current_q가 ENUM이고 해당 파트가 상수명 → 현재 타입에서 메서드 탐색 (탐색 종료)
             b. current_q$파트 가 내부 클래스로 존재 → current_q를 내부 클래스로 갱신 (다음 파트 계속)
             c. 둘 다 아니면 → 해석 실패
          4. 모든 파트를 소비하면 최종 current_q에서 메서드 탐색

        예: Outer.Inner.Inner2.foo()
          → parts = ["Outer", "Inner", "Inner2"]
          → Outer → Outer$Inner → Outer$Inner$Inner2 → foo() 탐색
        """
        parts = obj.split(".")
        if len(parts) < 2:
            return None

        # 첫 번째 파트를 타입으로 해석
        current_q = (self._resolve_type_in_file(parts[0], caller_file)
                     if caller_file else self._resolve_type_name_global(parts[0]))
        if not current_q:
            return None

        # 나머지 파트를 순회하며 해석
        for part in parts[1:]:
            parsed_type = self._registry.types.get(current_q)
            if not parsed_type:
                return None

            # ENUM 상수 접근 → 현재 타입에서 메서드 탐색 (더 이상 깊이 들어갈 수 없으므로 종료)
            if parsed_type.kind == "ENUM":
                constant_names = {c["name"] for c in parsed_type.constants} if parsed_type.constants else set()
                if part in constant_names:
                    methods = self._find_method_in_hierarchy(current_q, target_method)
                    return self._pick_by_arg_count(methods, arg_count)

            # 내부 클래스 접근 → qualname 갱신 후 다음 파트로 계속
            inner_qualname = f"{current_q}${part}"
            if inner_qualname in self._registry.types:
                current_q = inner_qualname
                continue

            return None  # 어느 패턴에도 매칭되지 않음

        # 모든 파트를 소비 → 최종 타입에서 메서드 탐색
        methods = self._find_method_in_hierarchy(current_q, target_method)
        return self._pick_by_arg_count(methods, arg_count)

    def _resolve_chained_call(self, call: ParsedCallEdge, caller_method, caller_file) -> str | None:
        """
        체이닝 호출을 반복적으로 해석합니다. 뎁스 제한 없음.

        예: a.getUser().getAddress().getCity()
          → receiver_chain=["getUser", "getAddress"], receiver_object="a", target="getCity"
          → 1) a.getUser() 해석 → User 타입
          → 2) User.getAddress() 해석 → Address 타입
          → 3) Address.getCity() 탐색

        전략:
          1. 체인의 첫 번째 메서드를 receiver_object 기반으로 해석
          2. 리턴 타입을 구한 뒤, 그 타입에서 다음 체인 메서드를 해석 (반복)
          3. 체인을 모두 소비하면 최종 타입에서 target_method 탐색
        """
        chain = call.receiver_chain
        if not chain:
            return None

        # 1단계: 체인의 첫 번째 메서드를 해석
        first_call = ParsedCallEdge(
            caller_qualname=call.caller_qualname,
            target_method_name=chain[0],
            object_name=call.receiver_object,
        )
        current_qualname = (self._resolve_with_object(first_call, caller_method, caller_file)
                            if call.receiver_object
                            else self._resolve_sibling_call(first_call, caller_method))
        if not current_qualname:
            return None

        # 2단계: 나머지 체인 메서드를 순회하며 리턴 타입 추적
        for chain_method in chain[1:]:
            current_qualname = self._follow_return_type(current_qualname, chain_method, caller_file)
            if not current_qualname:
                return None

        # 3단계: 최종 리턴 타입에서 target_method 탐색
        return self._follow_return_type(current_qualname, call.target_method_name, caller_file, call.arg_count)

    def _follow_return_type(
        self, method_qualname: str, next_method: str, caller_file: str | None, arg_count: int = -1,
    ) -> str | None:
        """
        메서드의 리턴 타입을 구하고, 그 타입에서 다음 메서드를 탐색합니다.

        예: getUser()의 리턴 타입이 User → User에서 next_method 탐색
        """
        method = self._registry.methods.get(method_qualname)
        if not method or not method.return_type or not method.return_type.get("layout"):
            return None

        return_type_name = method.return_type["layout"][0]
        type_q = (self._resolve_type_in_file(return_type_name, caller_file)
                  if caller_file else self._resolve_type_name_global(return_type_name))
        if not type_q:
            return None

        methods = self._find_method_in_hierarchy(type_q, next_method)
        return self._pick_by_arg_count(methods, arg_count)

    def _resolve_sibling_call(self, call: ParsedCallEdge, caller_method) -> str | None:
        """
        같은 클래스 + 상속 계층에서 형제 메서드를 탐색합니다.

        예: UserService 내부에서 validateUser(id) 호출
          → obj_name 없음, target_method_name="validateUser"
          → UserService → 부모 클래스 순으로 validateUser 탐색
        """
        if not caller_method:
            return None
        methods = self._find_method_in_hierarchy(caller_method.class_qualname, call.target_method_name)
        return self._pick_by_arg_count(methods, call.arg_count)

    # -----------------------------------------------------------------------
    # 파라미터/리턴 엣지 해석
    # -----------------------------------------------------------------------

    def resolve_parameter_edges(self, param_edges: list[ParsedParameterEdge]) -> list[dict]:
        """HAS_PARAMETER 엣지를 해석하여 DB 기록용 배치를 반환합니다."""
        batch = []
        for edge in param_edges:
            caller_method = self._registry.methods.get(edge.method_qualname)
            caller_type = self._registry.types.get(caller_method.class_qualname) if caller_method else None
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
            caller_method = self._registry.methods.get(edge.method_qualname)
            caller_type = self._registry.types.get(caller_method.class_qualname) if caller_method else None
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

    def resolve_field_type_edges(self) -> list[dict]:
        """FIELD→CONTAINS→TYPE 엣지를 해석하여 DB 기록용 배치를 반환합니다."""
        batch = []
        for f in self._registry.fields.values():
            # 변경분만 처리 (증분 분석)
            if f.qualname not in self._registry.dirty_fields:
                continue

            if not f.field_type or not f.field_type.get("layout"):
                continue

            # 필드가 속한 TYPE의 file_path → import 컨텍스트 활용
            parent_type = self._registry.types.get(f.type_qualname)
            file_path = parent_type.file_path if parent_type else None

            for type_name in f.field_type["layout"]:
                type_qualname = (self._resolve_type_in_file(type_name, file_path)
                                 if file_path else self._resolve_type_name_global(type_name))
                if type_qualname:
                    batch.append({
                        "field_qualname": f.qualname,
                        "type_qualname": type_qualname,
                    })
        return batch

    # -----------------------------------------------------------------------
    # 공통 유틸리티
    # -----------------------------------------------------------------------

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

        ctx = self._registry.file_contexts.get(file_path)
        if not ctx:
            return None

        # 1. 정규 import 매칭
        #    예: import com.example.model.User → "User" → "com.example.model.User" 확정
        for imp in ctx["imports"]:
            if imp.endswith(f".{type_name}") and imp in self._registry.types:
                return imp

        # 2. 같은 패키지/네임스페이스
        #    예: package com.example.service 내에서 "UserHelper" → "com.example.service.UserHelper"
        if ctx["package"]:
            for cand in candidates:
                cand_pkg = cand.rsplit(".", 1)[0] if "." in cand else ""
                if cand_pkg == ctx["package"]:
                    return cand

        # 3. 와일드카드 import
        #    예: import com.example.dto.* → "UserDto" → "com.example.dto.UserDto"
        for wp in ctx["wildcard_imports"]:
            for cand in candidates:
                cand_pkg = cand.rsplit(".", 1)[0] if "." in cand else ""
                if cand_pkg == wp:
                    return cand

        return None

    def _resolve_type_name_global(self, type_name: str) -> str | None:
        """
        타입 단순 이름을 qualname으로 해석합니다 (글로벌 — import 컨텍스트 없이).
        인덱스 구축 시 사용. 후보가 1개면 확정, 여러 개면 None.
        """
        candidates = self._types_by_name.get(type_name, [])
        if len(candidates) == 1:
            return candidates[0]
        return None

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
