"""
V&V 검증 도구
— 소스코드 기대값(EXPECTED) 조회 및 Neo4j 그래프 대조 검증

검증 단계 (총 9단계):
  [사전확인]   FILE→TYPE, TYPE→METHOD 존재 여부 (실패 시 중단)
  [1~2단계]  구조 검증: TYPE→FIELD, FIELD→TYPE
  [3단계]    속성 검증: HTTP 메서드, URI, 파라미터, 어노테이션
  [4~7단계]  관계 검증: 파라미터 타입, 리턴 타입, 내부 호출, 외부 호출
  [8단계]    역방향 검증: 잉여/오분류 탐지
  [9단계]    DTO 필드 검증: 이름, 타입, 제약조건

사용법:
    cd <프로젝트 루트>

    # 기대값 조회
    .venv/bin/python scripts/verify.py -v AuthController.login
    .venv/bin/python scripts/verify.py -v AuthController.login -o ex_login

    # 검증 실행
    .venv/bin/python scripts/verify.py -x AuthController.login
    .venv/bin/python scripts/verify.py -x AuthController.login -o result_login

    # 도움말
    .venv/bin/python scripts/verify.py --help
"""

import argparse
import sys
import json
import os
import yaml
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


# ============================================================
#  ANSI 컬러 유틸리티
#    - 터미널(stdout/stderr) 출력 시 색상 적용
#    - 파일 출력(-o) 시 자동 비활성화
# ============================================================

class _Colors:
    """ANSI escape code 래퍼. enabled=False이면 모든 속성이 빈 문자열."""
    _CODES = {
        "RESET":   "\033[0m",
        "BOLD":    "\033[1m",
        "DIM":     "\033[2m",
        "RED":     "\033[31m",
        "GREEN":   "\033[32m",
        "YELLOW":  "\033[33m",
        "BLUE":    "\033[34m",
        "MAGENTA": "\033[35m",
        "CYAN":    "\033[36m",
        "WHITE":   "\033[37m",
        "BRIGHT_GREEN":  "\033[92m",
        "BRIGHT_RED":    "\033[91m",
        "BRIGHT_YELLOW": "\033[93m",
        "BRIGHT_BLUE":   "\033[94m",
        "BRIGHT_CYAN":   "\033[96m",
    }

    def __init__(self, enabled=True):
        self._enabled = enabled

    def __getattr__(self, name):
        if name in self._CODES:
            return self._CODES[name] if self._enabled else ""
        raise AttributeError(name)


def _make_colors(out) -> _Colors:
    """출력 대상이 터미널이면 컬러 활성화, 파일이면 비활성화."""
    is_tty = hasattr(out, "isatty") and out.isatty()
    return _Colors(enabled=is_tty)


# ============================================================
#  기대값 로드 (expected.yaml)
# ============================================================

def _load_expected() -> dict:
    """YAML 기대값 파일을 로드하여 EXPECTED(endpoints) 반환"""
    yaml_path = Path(__file__).parent / "expected.yaml"
    if not yaml_path.exists():
        print(f"오류: 기대값 파일이 없습니다: {yaml_path}")
        sys.exit(1)

    with open(yaml_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    endpoints = data.get("endpoints", {})

    # YAML에서 빈 매핑({})은 None으로 로드될 수 있으므로 보정
    for ctrl, ctrl_data in endpoints.items():
        # class_level.fields가 None이면 빈 dict로 보정
        cl = ctrl_data.get("class_level")
        if cl and cl.get("fields") is None:
            cl["fields"] = {}
        for method, method_data in ctrl_data.items():
            if method == "class_level":
                continue
            if not isinstance(method_data, dict):
                continue
            for key in ("params", "param_annotations", "related_types"):
                if method_data.get(key) is None:
                    method_data[key] = {}
            for key in ("return_types", "param_types", "internal_calls", "external_calls"):
                if method_data.get(key) is None:
                    method_data[key] = []

    return endpoints


EXPECTED = _load_expected()


def _load_call_comments() -> dict[str, dict[str, dict[str, dict[str, str]]]]:
    """YAML 파일에서 internal_calls/external_calls 항목의 인라인 주석을 추출.

    Returns:
        {controller: {method: {"internal_calls"|"external_calls": {value: comment}}}}
    """
    yaml_path = Path(__file__).parent / "expected.yaml"
    comments: dict = {}
    ctrl = method = section = None

    with open(yaml_path, "r", encoding="utf-8") as f:
        for line in f:
            stripped = line.rstrip()
            if not stripped:
                continue
            indent = len(line) - len(line.lstrip())
            content = stripped.lstrip()

            # 전체 주석 줄은 건너뜀 (단, 섹션 변경 시 section 리셋 안 함)
            if content.startswith("#"):
                continue

            # Controller (indent 2)
            if indent == 2 and ":" in content and not content.startswith("-"):
                ctrl = content.split(":")[0].strip()
                method = section = None
            # Method (indent 4)
            elif indent == 4 and ":" in content and not content.startswith("-"):
                method = content.split(":")[0].strip()
                section = None
            # Section (indent 6)
            elif indent == 6 and ":" in content and not content.startswith("-"):
                key = content.split(":")[0].strip()
                section = key if key in ("internal_calls", "external_calls") else None
            # List item (indent 8)
            elif indent == 8 and content.startswith("- ") and section and ctrl and method:
                item = content[2:]
                if "#" in item:
                    value, comment = item.split("#", 1)
                    value = value.strip()
                    comment = comment.strip()
                    if value and comment:
                        (comments.setdefault(ctrl, {})
                                 .setdefault(method, {})
                                 .setdefault(section, {}))[value] = comment
            # 다른 indent 레벨 → section 리셋
            elif indent >= 10 or (indent == 8 and not content.startswith("-")):
                pass  # sub-items, section 유지

    return comments


CALL_COMMENTS = _load_call_comments()


# ============================================================
#  유틸리티
# ============================================================

def _match_call(expected_name: str, actual_names: set[str], actual_qualnames: set[str]) -> tuple[bool, str | None]:
    """기대값 이름이 DB 실측값에 존재하는지 판별.

    - 단순 이름(`.` 미포함): name 필드 exact match → 매칭된 qualname 반환
    - qualified name(`.` 포함): qualname 필드 endswith match (괄호 제거 후)

    Returns:
        (매칭 여부, 매칭된 qualname 또는 None)
    """
    if "." not in expected_name:
        if expected_name in actual_names:
            # 매칭된 이름에 해당하는 qualname 탐색
            for qn in actual_qualnames:
                clean_qn = qn.split("(")[0] if "(" in qn else qn
                if clean_qn.endswith("." + expected_name) or clean_qn == expected_name:
                    return True, qn
            return True, None
        return False, None
    for qn in actual_qualnames:
        # METHOD qualname에는 파라미터 괄호가 있으므로 제거 후 비교
        clean_qn = qn.split("(")[0] if "(" in qn else qn
        if clean_qn.endswith(expected_name):
            return True, qn
    return False, None


def _reverse_match(db_name: str, db_qualname: str, expected_set: set[str]) -> bool:
    """DB 호출이 기대값 집합에 포함되는지 역방향 판별.

    - 기대값이 단순 이름이면: db_name exact match
    - 기대값이 qualified name이면: db_qualname endswith match (괄호 제거 후)
    """
    clean_qn = db_qualname.split("(")[0] if db_qualname and "(" in db_qualname else (db_qualname or "")
    for exp in expected_set:
        if "." not in exp:
            if db_name == exp:
                return True
        else:
            if clean_qn.endswith(exp):
                return True
    return False


def parse_endpoint(endpoint_str: str) -> tuple[str, str]:
    """'AuthController.login()' → ('AuthController', 'login')"""
    s = endpoint_str.strip().rstrip("()")
    parts = s.split(".")
    if len(parts) != 2:
        print(f"오류: '{endpoint_str}' 형식이 올바르지 않습니다.")
        print(f"  예시: AuthController.login")
        sys.exit(1)
    ctrl, method = parts
    if ctrl not in EXPECTED:
        print(f"오류: '{ctrl}' 컨트롤러가 EXPECTED에 없습니다.")
        print(f"  등록된 컨트롤러: {', '.join(EXPECTED.keys())}")
        sys.exit(1)
    if method not in EXPECTED[ctrl] or method == "class_level":
        methods = [k for k in EXPECTED[ctrl] if k != "class_level"]
        print(f"오류: '{ctrl}.{method}' 메서드가 EXPECTED에 없습니다.")
        print(f"  등록된 메서드: {', '.join(methods)}")
        sys.exit(1)
    return ctrl, method


def resolve_output_path(filename: str | None, extension: str) -> str | None:
    """출력 파일 경로 결정. 확장자 없으면 자동 추가."""
    if not filename:
        return None
    if not os.path.splitext(filename)[1]:
        filename += extension
    output_dir = Path(__file__).parent / "results"
    output_dir.mkdir(exist_ok=True)
    return str(output_dir / filename)




# ============================================================
#  -v: 기대값 조회
# ============================================================

def _format_expected_text(ctrl: str, method: str) -> str:
    """기대값을 사람이 읽기 편한 텍스트 형식으로 포맷."""
    class_level = EXPECTED[ctrl].get("class_level", {})
    exp = EXPECTED[ctrl][method]
    related_types = exp.get("related_types", {})

    lines = []
    lines.append("━" * 64)
    lines.append(f"  기대값: {ctrl}.{method}")
    lines.append("━" * 64)

    # ── 클래스 정보 ──
    lines.append(f"\n  컨트롤러: {ctrl}")
    if class_level.get("base_uri"):
        lines.append(f"  기본 URI: {class_level['base_uri']}")
    if class_level.get("fields"):
        fields = class_level["fields"]
        if isinstance(fields, dict):
            field_strs = [f"{k}: {v}" for k, v in fields.items()]
        else:
            field_strs = list(fields)
        lines.append(f"  DI 필드:  {', '.join(field_strs)}")

    # ── 메서드 기본 정보 ──
    lines.append(f"\n{'─' * 64}")
    lines.append(f"  메서드 정보")
    lines.append(f"{'─' * 64}")
    http = exp.get("http_method", "?")
    if isinstance(http, list):
        http = " | ".join(http)
    lines.append(f"  HTTP 메서드:    {http}")
    lines.append(f"  엔드포인트 URI: {exp.get('endpoint_uri', '?')}")

    # ── 파라미터 ──
    params = exp.get("params", {})
    if params:
        lines.append(f"\n  파라미터:")
        for pname, ptype in params.items():
            ann = exp.get("param_annotations", {}).get(pname, "")
            ann_str = f"  ({ann})" if ann else ""
            lines.append(f"    - {pname}: {ptype}{ann_str}")

    # ── 타입 연결 ──
    param_types = exp.get("param_types", [])
    return_types = exp.get("return_types", [])
    if param_types:
        lines.append(f"\n  파라미터 타입 (HAS_PARAMETER 연결):")
        for pt in param_types:
            lines.append(f"    - {pt}")
    if return_types:
        lines.append(f"\n  리턴 타입 (RETURNS 연결):")
        for rt in return_types:
            lines.append(f"    - {rt}")

    # ── 내부 호출 ──
    internal = exp.get("internal_calls", [])
    ctrl_comments = CALL_COMMENTS.get(ctrl, {}).get(method, {})
    if internal:
        lines.append(f"\n  내부 호출 ({len(internal)}건) — 사용자 작성 코드:")
        int_comments = ctrl_comments.get("internal_calls", {})
        for i, call in enumerate(internal, 1):
            comment = int_comments.get(call, "")
            c_str = f"  # {comment}" if comment else ""
            lines.append(f"    {i:>3}. {call}{c_str}")

    # ── 외부 호출 ──
    external = exp.get("external_calls", [])
    if external:
        lines.append(f"\n  외부 호출 ({len(external)}건) — 프레임워크/라이브러리:")
        ext_comments = ctrl_comments.get("external_calls", {})
        for i, call in enumerate(external, 1):
            comment = ext_comments.get(call, "")
            c_str = f"  # {comment}" if comment else ""
            lines.append(f"    {i:>3}. {call}{c_str}")

    # ── 관련 타입 필드 (endpoint별 직접 명시) ──
    if related_types:
        lines.append(f"\n{'─' * 64}")
        lines.append(f"  관련 타입 필드")
        lines.append(f"{'─' * 64}")
        for type_name, fields in related_types.items():
            lines.append(f"\n  {type_name}:")
            for fname, finfo in fields.items():
                constraint = finfo.get("constraint", "")
                c_str = f"  [{constraint}]" if constraint else ""
                lines.append(f"    - {fname}: {finfo['type']}{c_str}")

    lines.append("")
    return "\n".join(lines)


def view_expected(endpoint: str, output_filename: str | None):
    ctrl, method = parse_endpoint(endpoint)
    output_path = resolve_output_path(output_filename, ".txt")

    text = _format_expected_text(ctrl, method)

    if output_path:
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(text)
        print(f"기대값 저장 완료: {output_path}")
    else:
        print(text)


# ============================================================
#  -x: 검증 실행 — 판정 상수 및 리포트
# ============================================================

# 판정(verdict) 상수
OK            = "OK"             # 통과
MISSING       = "MISSING"        # 기대하는데 DB에 없음
MISMATCH      = "MISMATCH"       # 값 불일치
ANN_MISSING   = "ANN_MISSING"    # 어노테이션 누락
SURPLUS       = "SURPLUS"        # DB에만 있고 기대값에 없음 (잉여)
MISCLASSIFIED = "MISCLASSIFIED"  # internal/external 오분류 (파서 한계)
KNOWN_BUG     = "KNOWN_BUG"     # 알려진 파서 미구현 기능


class Report:
    """검증 결과 수집 및 리포트 출력."""

    # verdict → 사람이 읽을 수 있는 카테고리 설명
    VERDICT_LABELS = {
        MISSING:       "누락 — 기대하지만 DB에 없음",
        MISMATCH:      "불일치 — 기대값과 실제값 다름",
        ANN_MISSING:   "어노테이션 누락",
        MISCLASSIFIED: "오분류 — internal/external 잘못 분류됨",
        SURPLUS:       "잉여 — DB에는 있지만 소스코드 기대값(YAML)에 없음",
        KNOWN_BUG:     "알려진 버그 — 파서 미구현 기능",
    }

    # 파서 한계로 인한 verdict (버그지만 현재 해결 불가)
    PARSER_BUG_VERDICTS = {MISCLASSIFIED, SURPLUS, KNOWN_BUG}

    def __init__(self, out):
        self.out = out
        self.results = []
        self.c = _make_colors(out)

    def _print(self, *args, **kwargs):
        print(*args, file=self.out, **kwargs)

    def add(self, step: str, item: str, expected, actual, verdict: str):
        """검증 항목 하나를 추가하고, 실시간으로 결과를 출력."""
        c = self.c
        self.results.append((step, item, expected, actual, verdict))
        if verdict == OK:
            self._print(f"  {c.GREEN}✓{c.RESET} {item}: {c.GREEN}{verdict}{c.RESET}")
        elif verdict == KNOWN_BUG:
            self._print(f"  {c.YELLOW}✗{c.RESET} {item}: {c.YELLOW}{verdict}{c.RESET}")
            self._print(f"       {c.DIM}기대: {expected}{c.RESET}")
            self._print(f"       {c.DIM}실제: {actual}{c.RESET}")
        else:
            self._print(f"  {c.RED}✗{c.RESET} {item}: {c.RED}{verdict}{c.RESET}")
            self._print(f"       {c.DIM}기대: {expected}{c.RESET}")
            self._print(f"       {c.DIM}실제: {actual}{c.RESET}")

    def summary(self) -> int:
        """최종 검증 리포트를 출력하고, 실패+파서버그 건수를 반환."""
        total = len(self.results)
        passed = sum(1 for r in self.results if r[4] == OK)

        # 실패 항목을 verdict별로 그룹핑
        categories = {}
        for step, item, exp, act, verdict in self.results:
            if verdict == OK:
                continue
            categories.setdefault(verdict, []).append((step, item, exp, act))

        parser_bugs = sum(
            len(v) for k, v in categories.items()
            if k in self.PARSER_BUG_VERDICTS
        )
        failures = sum(
            len(v) for k, v in categories.items()
            if k not in self.PARSER_BUG_VERDICTS
        )

        c = self.c
        self._print(f"\n{c.BOLD}{'━' * 64}{c.RESET}")
        self._print(f"  {c.BOLD}최종 검증 리포트{c.RESET}")
        self._print(f"{c.BOLD}{'━' * 64}{c.RESET}")
        self._print(f"  전체: {c.BOLD}{total}건{c.RESET}")
        self._print(f"  {c.GREEN}✓ 통과: {passed}건{c.RESET}")
        self._print(f"  {c.RED}✗ 실패: {failures}건{c.RESET}  {c.DIM}(파서가 해결해야 할 항목){c.RESET}")
        self._print(f"  {c.YELLOW}⚠ 파서버그: {parser_bugs}건{c.RESET}  {c.DIM}(알려진 파서 한계){c.RESET}")

        if not categories:
            self._print(f"\n  {c.BRIGHT_GREEN}🎉 모든 항목 통과!{c.RESET}")
            return 0

        # verdict별 상세 출력
        for verdict, items in categories.items():
            label = self.VERDICT_LABELS.get(verdict, verdict)
            is_bug = verdict in self.PARSER_BUG_VERDICTS
            if is_bug:
                tag_str = f"{c.YELLOW}⚠ 파서한계{c.RESET}"
                verdict_str = f"{c.YELLOW}{verdict}{c.RESET}"
            else:
                tag_str = f"{c.RED}✗ 실패{c.RESET}"
                verdict_str = f"{c.RED}{verdict}{c.RESET}"
            self._print(f"\n  [{tag_str}] {verdict_str}: {label} ({len(items)}건)")
            for step, item, exp, act in items:
                self._print(f"    ({step}단계) {item}")
                self._print(f"           {c.DIM}기대: {exp}{c.RESET}")
                self._print(f"           {c.DIM}실제: {act}{c.RESET}")

        return failures + parser_bugs


# ============================================================
#  단계 헤더 출력 유틸리티
# ============================================================

def print_step_header(report, step_num: int, title: str, description: str,
                      verdict_guide: dict[str, str] | None = None):
    """각 단계 시작 시 제목, 설명, verdict 판정 기준을 출력합니다."""
    c = report.c
    report._print(f"\n{c.CYAN}{'─' * 64}{c.RESET}")
    report._print(f"  {c.BOLD}{c.BRIGHT_CYAN}{step_num}단계. {title}{c.RESET}")
    report._print(f"{c.CYAN}{'─' * 64}{c.RESET}")
    report._print(f"  {c.DIM}{description}{c.RESET}")
    if verdict_guide:
        report._print(f"")
        report._print(f"  {c.DIM}판정 기준:{c.RESET}")
        for verdict_name, meaning in verdict_guide.items():
            report._print(f"    {c.DIM}{verdict_name:<14s} → {meaning}{c.RESET}")
    report._print(f"")
    report._print(f"  {c.BOLD}검증 결과:{c.RESET}")


# ============================================================
#  사전 확인: FILE→TYPE, TYPE→METHOD 존재 여부
#    인자로 Controller.method를 받으므로 이 관계는 전제 조건.
#    실패 시 이후 검증이 무의미하므로 에러 메시지를 출력하고 중단.
# ============================================================

def precheck(db, out, ctrl, method) -> bool:
    """FILE→TYPE, TYPE→METHOD 존재 여부를 확인.
    정상이면 True, 실패 시 에러 메시지를 출력하고 False를 반환."""
    c = _make_colors(out)
    print_fn = lambda *a, **kw: print(*a, file=out, **kw)

    # FILE→TYPE
    file_records = db.execute_query("""
        MATCH (f:FILE)-[:CONTAINS]->(t:TYPE {name: $ctrl})
        RETURN f.name AS file_name, f.path AS file_path
    """, {"ctrl": ctrl})
    if not file_records:
        print_fn(f"\n  {c.RED}✗ 사전 확인 실패:{c.RESET} '{ctrl}' TYPE 노드가 DB에 없거나, FILE과 연결되지 않았습니다.")
        print_fn(f"    {c.DIM}→ 파서가 해당 클래스를 파싱하지 못한 것입니다. 이후 검증을 중단합니다.{c.RESET}")
        return False

    # TYPE→METHOD
    method_records = db.execute_query("""
        MATCH (t:TYPE {name: $ctrl})-[:CONTAINS]->(m:METHOD {name: $method})
        RETURN m.name AS name, m.qualname AS qualname
    """, {"ctrl": ctrl, "method": method})
    if not method_records:
        file_info = file_records[0].get("file_path") or file_records[0].get("file_name") or "(경로 미상)"
        print_fn(f"\n  {c.GREEN}✓{c.RESET} 사전 확인: FILE({file_info}) → TYPE({ctrl}) 연결 확인")
        print_fn(f"  {c.RED}✗ 사전 확인 실패:{c.RESET} '{ctrl}' 안에 '{method}' METHOD가 없습니다.")
        print_fn(f"    {c.DIM}→ 파서가 해당 메서드를 감지하지 못한 것입니다. 이후 검증을 중단합니다.{c.RESET}")
        return False

    file_info = file_records[0].get("file_path") or file_records[0].get("file_name") or "(경로 미상)"
    qn = method_records[0].get("qualname", "(qualname 없음)")
    print_fn(f"\n  {c.GREEN}✓{c.RESET} 사전 확인: FILE({file_info}) → TYPE({ctrl}) → METHOD({method})")
    print_fn(f"    {c.DIM}qualname: {qn}{c.RESET}")
    return True


# ============================================================
#  1~2단계: 구조 검증
#    파서가 타입-필드 간 CONTAINS 관계를 올바르게 생성했는지 확인
# ============================================================

def step1_type_contains_field(db, report, ctrl, expected_fields):
    """1단계. 클래스 → 필드(DI 주입) 소속 확인"""
    c = report.c
    if not expected_fields:
        report._print(f"\n{c.CYAN}{'─' * 64}{c.RESET}")
        report._print(f"  {c.BOLD}{c.BRIGHT_CYAN}1단계. 클래스 → 필드(DI 주입) 소속 확인{c.RESET}")
        report._print(f"{c.CYAN}{'─' * 64}{c.RESET}")
        report._print(f"  {c.DIM}(해당 없음 — 기대하는 DI 필드가 없습니다){c.RESET}")
        return
    print_step_header(report, 1,
        "클래스 → 필드(DI 주입) 소속 확인",
        "클래스에 선언된 필드(서비스 주입, 설정값 등)가 DB에 존재하는지 확인합니다.",
        {
            OK:      "기대하는 필드가 클래스 아래에 정상적으로 존재합니다.",
            MISSING: "기대하는 필드가 DB에 없습니다. 파서가 필드를 감지하지 못한 것입니다.",
        })
    records = db.execute_query("""
        MATCH (t:TYPE {name: $ctrl})-[:CONTAINS]->(f:FIELD)
        RETURN f.name AS name, f.type AS type ORDER BY f.name
    """, {"ctrl": ctrl})

    actual = {}
    for r in records:
        ftype = r["type"]
        if isinstance(ftype, str):
            try:
                ftype = json.loads(ftype)
            except (json.JSONDecodeError, TypeError):
                pass
        type_str = ftype.get("given", str(ftype)) if isinstance(ftype, dict) else str(ftype)
        actual[r["name"]] = type_str

    for f in expected_fields:
        if f in actual:
            report.add("1", f"FIELD[{f}]",
                       "연결됨", f"연결됨 (타입: {actual[f]})", OK)
        else:
            report.add("1", f"FIELD[{f}]", "연결됨", "없음", MISSING)


def step2_field_contains_type(db, report, ctrl, expected_fields, related_types):
    """2단계. 필드 → 타입 연결 확인

    YAML 기대값에서 각 필드의 타입을 가져와, 해당 타입이 DB에 TYPE 노드로
    존재하는 경우에만 FIELD→TYPE 연결을 기대합니다.
    primitive(long, int 등)나 JDK 타입(String 등)은 TYPE 노드가 없으므로 스킵.

    검증 대상:
      1) 컨트롤러 클래스 필드 — YAML class_level.fields (dict: name→type)
      2) 관련 타입 필드 — YAML endpoint별 related_types (dict: name→{type, constraint})
    """
    print_step_header(report, 2,
        "필드 → 타입 연결 확인",
        "각 필드(FIELD)가 자신의 타입에 해당하는 TYPE 노드와 연결되어 있는지 확인합니다.\n"
        "  예: orderService(FIELD) → OrderService(TYPE). 이 연결이 없으면\n"
        "  TC 생성 시 필드를 통한 호출 추적이 불가능합니다.\n"
        "  검증 범위: 컨트롤러 클래스 필드 + endpoint별 관련 타입 필드 (YAML 기대값 기준)\n"
        "  스킵 대상: 타입이 DB에 TYPE 노드로 존재하지 않는 필드 (primitive, JDK 타입 등)",
        {
            OK:        "필드와 타입이 정상적으로 연결되어 있습니다.",
            KNOWN_BUG: "파서가 이 연결을 아직 구현하지 못했습니다 (전체 DB에서 0건).",
        })

    c = report.c

    # ── 전체 DB에서 FIELD→TYPE 엣지 건수 (파서 전반 미구현 판별용) ──
    count_records = db.execute_query(
        "MATCH (:FIELD)-[:CONTAINS]->(:TYPE) RETURN count(*) AS cnt")
    cnt = count_records[0]["cnt"] if count_records else 0

    # ── 검증 대상 수집: (소속 TYPE, 필드명, 필드 타입) 튜플 목록 ──
    # 기대값 기반으로 수집하여, 타입이 DB에 TYPE 노드로 존재하는 것만 검증
    targets = []  # [(owner_type, field_name, field_type_str, label)]

    # 1) 컨트롤러 클래스 필드 (YAML class_level.fields dict)
    if expected_fields:
        for fname, ftype_str in expected_fields.items():
            targets.append((ctrl, fname, str(ftype_str), f"{ctrl} (컨트롤러)"))

    # 2) endpoint별 관련 타입 필드 (YAML related_types)
    for type_name, fields in related_types.items():
        for fname, finfo in fields.items():
            ftype_str = str(finfo.get("type", ""))
            targets.append((type_name, fname, ftype_str, type_name))

    if not targets:
        report._print(f"  {c.DIM}(해당 없음 — 검증 대상 필드가 없습니다){c.RESET}")
        return

    # ── 각 필드의 타입이 DB에 TYPE 노드로 존재하는지 캐싱 확인 ──
    type_exists_cache = {}

    def _type_exists_in_db(type_name: str) -> bool:
        """타입명이 DB에 TYPE 노드로 존재하는지 확인 (캐싱)."""
        if type_name in type_exists_cache:
            return type_exists_cache[type_name]
        result = db.execute_query(
            "MATCH (t:TYPE {name: $name}) RETURN t.name LIMIT 1",
            {"name": type_name})
        exists = bool(result)
        type_exists_cache[type_name] = exists
        return exists

    def _extract_base_type(type_str: str) -> str:
        """'List<Address>' → 'Address', 'Map<Long, SseEmitter>' → 'Map' 등
        제네릭 내부의 프로젝트 타입도 추출."""
        # 제네릭 래퍼 안의 타입 추출 시도
        import re
        # List<Address> → Address, List<OrderItemRequest> → OrderItemRequest
        inner = re.findall(r'<(.+?)>', type_str)
        if inner:
            # 제네릭 인자들 중 프로젝트 TYPE이 있으면 그것을 반환
            for arg in inner[0].split(","):
                arg = arg.strip().split("<")[0].strip()
                if arg and not arg[0].islower() and _type_exists_in_db(arg):
                    return arg
        # 기본: 제네릭 제거 후 base name
        return type_str.split("<")[0].split("[")[0].strip()

    # ── 소속 TYPE별로 그룹핑하여 출력 ──
    from collections import OrderedDict
    grouped = OrderedDict()  # label → [(owner, fname, ftype_str)]
    for owner, fname, ftype_str, label in targets:
        grouped.setdefault(label, []).append((owner, fname, ftype_str))

    found_any = False
    for label, items in grouped.items():
        # 이 그룹에서 연결 대상이 있는지 미리 확인
        connectable = []
        skipped = []
        for owner, fname, ftype_str in items:
            base_type = _extract_base_type(ftype_str)
            if _type_exists_in_db(base_type):
                connectable.append((owner, fname, ftype_str, base_type))
            else:
                skipped.append((fname, ftype_str))

        if not connectable and not skipped:
            continue

        found_any = True
        report._print(f"\n  {c.BOLD}── {label} ──{c.RESET}")

        # DB에서 실제 연결 조회
        if connectable:
            owner_name = connectable[0][0]
            connected_records = db.execute_query("""
                MATCH (t:TYPE {name: $type_name})-[:CONTAINS]->(f:FIELD)-[:CONTAINS]->(ft:TYPE)
                RETURN f.name AS field_name, ft.name AS type_name
            """, {"type_name": owner_name})
            connected = {r["field_name"]: r["type_name"] for r in connected_records} if connected_records else {}

            for owner, fname, ftype_str, base_type in connectable:
                if fname in connected:
                    report.add("2", f"FIELD[{fname}] ({ftype_str}) → TYPE[{connected[fname]}]",
                               "연결됨", "연결됨", OK)
                else:
                    report.add("2", f"FIELD[{fname}] ({ftype_str}) → TYPE[{base_type}] 연결",
                               f"{fname}의 타입({base_type})에 해당하는 TYPE과 연결 필요",
                               f"연결 없음 (전체 DB FIELD→TYPE: {cnt}건)",
                               KNOWN_BUG)

        # 스킵된 필드 (primitive/JDK 타입)
        if skipped:
            for fname, ftype_str in skipped:
                report._print(f"  {c.DIM}  (스킵) FIELD[{fname}] ({ftype_str}) — TYPE 노드 없음{c.RESET}")

    if not found_any:
        report._print(f"    {c.DIM}(필드 없음 — 이 단계 스킵){c.RESET}")


# ============================================================
#  3단계: 속성 검증
# ============================================================

def step3_method_attributes(db, report, ctrl, method, expected):
    """3단계. 메서드 속성 검증"""
    print_step_header(report, 3,
        "메서드 속성 검증",
        "METHOD 노드의 속성값이 소스코드와 일치하는지 확인합니다.\n"
        "  검증 항목: HTTP 메서드, 엔드포인트 URI, 파라미터(이름/타입), 파라미터 어노테이션",
        {
            OK:          "속성값이 소스코드와 일치합니다.",
            MISMATCH:    "속성값이 소스코드와 다릅니다. 파서가 잘못 추출한 것입니다.",
            MISSING:     "기대하는 파라미터가 DB에 없습니다.",
            ANN_MISSING: "파라미터에 붙어야 할 어노테이션(@RequestBody 등)이 DB에 없습니다.",
        })
    records = db.execute_query("""
        MATCH (c:TYPE {name: $ctrl})-[:CONTAINS]->(m:METHOD {name: $method})
        RETURN m.http_method AS http_method, m.endpoint_uri AS endpoint_uri,
               m.params AS params, m.return_type AS return_type
    """, {"ctrl": ctrl, "method": method})

    if not records:
        report.add("3", f"{ctrl}.{method} METHOD 노드", "존재해야 함", "없음", MISSING)
        return

    rec = records[0]

    # http_method
    actual_hm = rec["http_method"]
    exp_hm = expected["http_method"]
    if isinstance(exp_hm, list):
        report.add("3", "http_method", " | ".join(exp_hm), actual_hm,
                   OK if actual_hm in exp_hm else MISMATCH)
    else:
        report.add("3", "http_method", exp_hm, actual_hm,
                   OK if actual_hm == exp_hm else MISMATCH)

    # endpoint_uri
    actual_uri = rec["endpoint_uri"]
    exp_uri = expected["endpoint_uri"]
    report.add("3", "endpoint_uri", exp_uri, actual_uri,
               OK if actual_uri == exp_uri else MISMATCH)

    # params (이름 + 타입)
    params_raw = rec["params"]
    if isinstance(params_raw, str):
        params_raw = json.loads(params_raw)
    actual_params = {}
    if params_raw:
        for p in params_raw:
            actual_params[p["name"]] = p["type"]["given"]

    for pname, ptype in expected["params"].items():
        actual_type = actual_params.get(pname)
        if actual_type is None:
            report.add("3", f"param[{pname}]", ptype, "없음", MISSING)
        elif actual_type != ptype:
            report.add("3", f"param[{pname}] 타입", ptype, actual_type, MISMATCH)
        else:
            report.add("3", f"param[{pname}]", ptype, actual_type, OK)

    # param annotations
    actual_anns = {}
    if params_raw:
        for p in params_raw:
            actual_anns[p["name"]] = p.get("annotation", "")
    for pname, exp_ann in expected.get("param_annotations", {}).items():
        actual_ann = actual_anns.get(pname, "")
        if not actual_ann:
            report.add("3", f"param[{pname}] annotation", exp_ann, "(빈값)", ANN_MISSING)
        elif actual_ann != exp_ann:
            report.add("3", f"param[{pname}] annotation", exp_ann, actual_ann, MISMATCH)
        else:
            report.add("3", f"param[{pname}] annotation", exp_ann, actual_ann, OK)


# ============================================================
#  4~7단계: 관계 검증 (정방향: 기대→실제)
# ============================================================

def step4_has_parameter(db, report, ctrl, method, expected_param_types):
    """4단계. 파라미터 타입 연결 검증"""
    c = report.c
    if not expected_param_types:
        report._print(f"\n{c.CYAN}{'─' * 64}{c.RESET}")
        report._print(f"  {c.BOLD}{c.BRIGHT_CYAN}4단계. 파라미터 타입 연결 검증{c.RESET}")
        report._print(f"{c.CYAN}{'─' * 64}{c.RESET}")
        report._print(f"  {c.DIM}(해당 없음 — 복합 타입 파라미터가 없습니다){c.RESET}")
        return
    print_step_header(report, 4,
        "파라미터 타입 연결 검증",
        "메서드가 받는 복합 타입 파라미터(DTO 등)가 HAS_PARAMETER 관계로\n"
        "  TYPE 노드에 연결되어 있는지 확인합니다. (기본형 Long, String 등은 제외)",
        {
            OK:      "파라미터 타입이 정상적으로 연결되어 있습니다.",
            MISSING: "파라미터 타입 연결이 DB에 없습니다.",
        })
    records = db.execute_query("""
        MATCH (t:TYPE {name: $ctrl})-[:CONTAINS]->(m:METHOD {name: $method})
        OPTIONAL MATCH (m)-[:HAS_PARAMETER]->(pt:TYPE)
        RETURN collect(DISTINCT pt.name) AS param_types
    """, {"ctrl": ctrl, "method": method})
    actual = set(x for x in (records[0]["param_types"] if records else []) if x)
    for pt in expected_param_types:
        report.add("4", f"HAS_PARAMETER → {pt}",
                   "연결됨", "연결됨" if pt in actual else "없음",
                   OK if pt in actual else MISSING)


def step5_returns(db, report, ctrl, method, expected_return_types):
    """5단계. 리턴 타입 연결 검증"""
    c = report.c
    if not expected_return_types:
        report._print(f"\n{c.CYAN}{'─' * 64}{c.RESET}")
        report._print(f"  {c.BOLD}{c.BRIGHT_CYAN}5단계. 리턴 타입 연결 검증{c.RESET}")
        report._print(f"{c.CYAN}{'─' * 64}{c.RESET}")
        report._print(f"  {c.DIM}(해당 없음 — void 또는 기본형 반환이라 TYPE 연결 대상이 없습니다){c.RESET}")
        return
    print_step_header(report, 5,
        "리턴 타입 연결 검증",
        "메서드의 반환 타입이 RETURNS 관계로 TYPE 노드에 연결되어 있는지 확인합니다.\n"
        "  void, byte[] 등 기본형은 RETURNS 연결이 없으므로 이 단계를 건너뜁니다.",
        {
            OK:      "리턴 타입이 정상적으로 연결되어 있습니다.",
            MISSING: "리턴 타입 연결이 DB에 없습니다.",
        })
    records = db.execute_query("""
        MATCH (t:TYPE {name: $ctrl})-[:CONTAINS]->(m:METHOD {name: $method})
        OPTIONAL MATCH (m)-[:RETURNS]->(rt:TYPE)
        RETURN collect(DISTINCT rt.name) AS return_types
    """, {"ctrl": ctrl, "method": method})
    actual = set(x for x in (records[0]["return_types"] if records else []) if x)
    for rt in expected_return_types:
        report.add("5", f"RETURNS → {rt}",
                   "연결됨", "연결됨" if rt in actual else "없음",
                   OK if rt in actual else MISSING)


def step6_internal_calls(db, report, ctrl, method, expected_internal):
    """6단계. 내부 호출 체인 검증"""
    c = report.c
    if not expected_internal:
        report._print(f"\n{c.CYAN}{'─' * 64}{c.RESET}")
        report._print(f"  {c.BOLD}{c.BRIGHT_CYAN}6단계. 내부 호출 체인 검증 (사용자 작성 코드){c.RESET}")
        report._print(f"{c.CYAN}{'─' * 64}{c.RESET}")
        report._print(f"  {c.DIM}(해당 없음 — 내부 메서드 호출이 없습니다){c.RESET}")
        return
    print_step_header(report, 6,
        "내부 호출 체인 검증 (사용자 작성 코드)",
        "컨트롤러 메서드에서 출발하여 CALLS 관계를 무한 깊이로 따라가며,\n"
        "  도달해야 하는 모든 내부 메서드(프로젝트 내 사용자 작성 코드)가\n"
        "  실제로 도달 가능한지 확인합니다.\n"
        "  예: Controller.createOrder → OrderService.createOrder (1depth)\n"
        "                             → OrderValidator.validate (2depth)",
        {
            OK:      "기대하는 내부 메서드에 정상적으로 도달 가능합니다.",
            MISSING: "기대하는 내부 메서드에 도달 불가합니다.\n"
                     "                  파서가 호출 관계를 감지하지 못한 것입니다 (변수 타입 해석 실패, 체이닝 끊김 등).",
        })
    records = db.execute_query("""
        MATCH (t:TYPE {name: $ctrl})-[:CONTAINS]->(m:METHOD {name: $method})
        OPTIONAL MATCH (m)-[:CALLS*1..]->(target:METHOD)
        RETURN collect(DISTINCT target.name) AS calls,
               collect(DISTINCT target.qualname) AS qualnames
    """, {"ctrl": ctrl, "method": method})
    actual_names = set(x for x in (records[0]["calls"] if records else []) if x)
    actual_qualnames = set(x for x in (records[0]["qualnames"] if records else []) if x)
    for call in expected_internal:
        found, matched_qn = _match_call(call, actual_names, actual_qualnames)
        verdict = OK if found else MISSING
        # qualname 코멘트 생성
        qn_comment = f"  {c.DIM}# {matched_qn}{c.RESET}" if matched_qn else ""
        # 직접 출력 (qualname 코멘트 포함)
        report.results.append(("6", f"내부 호출 → {call}", "도달 가능",
                               "도달 가능" if found else "도달 불가", verdict))
        if verdict == OK:
            report._print(f"  {c.GREEN}✓{c.RESET} 내부 호출 → {call}: {c.GREEN}{verdict}{c.RESET}{qn_comment}")
        else:
            report._print(f"  {c.RED}✗{c.RESET} 내부 호출 → {call}: {c.RED}{verdict}{c.RESET}{qn_comment}")
            report._print(f"       {c.DIM}기대: 도달 가능{c.RESET}")
            report._print(f"       {c.DIM}실제: 도달 불가{c.RESET}")


def step7_external_calls(db, report, ctrl, method, expected_external):
    """7단계. 외부 호출 체인 검증"""
    c = report.c
    if not expected_external:
        report._print(f"\n{c.CYAN}{'─' * 64}{c.RESET}")
        report._print(f"  {c.BOLD}{c.BRIGHT_CYAN}7단계. 외부 호출 체인 검증 (프레임워크/라이브러리 API){c.RESET}")
        report._print(f"{c.CYAN}{'─' * 64}{c.RESET}")
        report._print(f"  {c.DIM}(해당 없음 — 외부 호출이 없습니다){c.RESET}")
        return
    print_step_header(report, 7,
        "외부 호출 체인 검증 (프레임워크/라이브러리 API)",
        "컨트롤러 메서드에서 출발하여 CALLS 관계를 무한 깊이로 따라가며,\n"
        "  도달해야 하는 모든 외부 호출(Spring, JPA 등 프레임워크/라이브러리 API)이\n"
        "  실제로 도달 가능한지 확인합니다.\n"
        "  중간에 내부 METHOD를 경유하여 도달하는 외부 호출도 포함됩니다.",
        {
            OK:      "기대하는 외부 호출에 정상적으로 도달 가능합니다.",
            MISSING: "기대하는 외부 호출에 도달 불가합니다.\n"
                     "                  파서가 해당 외부 호출을 감지하지 못한 것입니다.",
        })
    records = db.execute_query("""
        MATCH (t:TYPE {name: $ctrl})-[:CONTAINS]->(m:METHOD {name: $method})
        OPTIONAL MATCH (m)-[:CALLS*1..]->(target:EXTERNAL_CALL)
        RETURN collect(DISTINCT target.name) AS calls,
               collect(DISTINCT target.qualname) AS qualnames
    """, {"ctrl": ctrl, "method": method})
    actual_names = set(x for x in (records[0]["calls"] if records else []) if x)
    actual_qualnames = set(x for x in (records[0]["qualnames"] if records else []) if x)
    for call in expected_external:
        found, matched_qn = _match_call(call, actual_names, actual_qualnames)
        verdict = OK if found else MISSING
        # qualname 코멘트 생성
        qn_comment = f"  {c.DIM}# {matched_qn}{c.RESET}" if matched_qn else ""
        # 직접 출력 (qualname 코멘트 포함)
        report.results.append(("7", f"외부 호출 → {call}", "도달 가능",
                               "도달 가능" if found else "도달 불가", verdict))
        if verdict == OK:
            report._print(f"  {c.GREEN}✓{c.RESET} 외부 호출 → {call}: {c.GREEN}{verdict}{c.RESET}{qn_comment}")
        else:
            report._print(f"  {c.RED}✗{c.RESET} 외부 호출 → {call}: {c.RED}{verdict}{c.RESET}{qn_comment}")
            report._print(f"       {c.DIM}기대: 도달 가능{c.RESET}")
            report._print(f"       {c.DIM}실제: 도달 불가{c.RESET}")


# ============================================================
#  8단계: 역방향 검증 (실제→기대: 잉여/오분류 탐지)
# ============================================================

def step8_reverse_verification(db, report, ctrl, method, expected_internal, expected_external):
    """8단계. 역방향 검증 — DB 실측값 ↔ 소스코드 기대값 교차 비교."""
    print_step_header(report, 8,
        "역방향 검증 — DB 실측값 vs 소스코드 기대값",
        "6~7단계는 '소스코드 기대값 → DB' 방향으로 누락을 찾았다면,\n"
        "  이 단계는 반대로 'DB → 소스코드 기대값' 방향으로 교차 검증합니다.\n"
        "  DB에 있지만 기대값에 없는 항목(잉여)과, 분류가 잘못된 항목(오분류)을 찾습니다.",
        {
            SURPLUS:       "DB에서 감지했지만 소스코드 기대값(YAML)에는 없는 호출입니다.\n"
                           "                  → YAML에 기대값을 빠뜨렸거나, 파서가 존재하지 않는 호출 관계를 생성한 것입니다.",
            MISCLASSIFIED: "internal(사용자 작성)/external(라이브러리) 분류가 소스코드와 다릅니다.\n"
                           "                  → 파서가 변수 타입을 해석하지 못해 잘못 분류한 것입니다.",
        })

    # DB에서 전체 호출 수집 (CALLS*1.. 전체 깊이, name + qualname 쌍)
    records = db.execute_query("""
        MATCH (t:TYPE {name: $ctrl})-[:CONTAINS]->(m:METHOD {name: $method})
        OPTIONAL MATCH (m)-[:CALLS*1..]->(int_target:METHOD)
        OPTIONAL MATCH (m)-[:CALLS*1..]->(ext_target:EXTERNAL_CALL)
        RETURN collect(DISTINCT [int_target.name, int_target.qualname]) AS db_internal,
               collect(DISTINCT [ext_target.name, ext_target.qualname]) AS db_external
    """, {"ctrl": ctrl, "method": method})

    # DB 결과를 (name, qualname) 쌍 리스트로 정리
    db_internal_pairs = [(p[0], p[1] or "") for p in (records[0]["db_internal"] if records else []) if p[0]]
    db_external_pairs = [(p[0], p[1] or "") for p in (records[0]["db_external"] if records else []) if p[0]]
    exp_internal = set(expected_internal) if expected_internal else set()
    exp_external = set(expected_external) if expected_external else set()
    all_expected = exp_internal | exp_external

    c = report.c

    # ── 8-1. 잉여 내부 호출 ──
    surplus_int = [(n, q) for n, q in db_internal_pairs
                   if not _reverse_match(n, q, all_expected)]
    surplus_int.sort(key=lambda x: x[0])
    report._print(f"\n  {c.BOLD}8-1. 잉여 내부 호출 ({len(surplus_int)}건){c.RESET}")
    report._print(f"       {c.DIM}DB가 내부 메서드(METHOD)로 감지했지만, 소스코드 기대값(YAML)의{c.RESET}")
    report._print(f"       {c.DIM}internal_calls / external_calls 어디에도 없는 호출입니다.{c.RESET}")
    if surplus_int:
        for n, q in surplus_int:
            report.add("8", f"[잉여 내부 호출] {n} (qualname: {q})",
                       "YAML에 있어야 하나 없음 (YAML 누락 또는 파서 오류)",
                       "DB에서 내부 메서드(METHOD)로 감지됨", SURPLUS)
    else:
        report._print(f"    {c.DIM}(없음 — 모든 DB 내부 호출이 기대값과 일치){c.RESET}")

    # ── 8-2. 잉여 외부 호출 ──
    surplus_ext = [(n, q) for n, q in db_external_pairs
                   if not _reverse_match(n, q, all_expected)]
    surplus_ext.sort(key=lambda x: x[0])
    report._print(f"\n  {c.BOLD}8-2. 잉여 외부 호출 ({len(surplus_ext)}건){c.RESET}")
    report._print(f"       {c.DIM}DB가 외부 호출(EXTERNAL_CALL)로 감지했지만, 소스코드 기대값(YAML)의{c.RESET}")
    report._print(f"       {c.DIM}internal_calls / external_calls 어디에도 없는 호출입니다.{c.RESET}")
    if surplus_ext:
        for n, q in surplus_ext:
            report.add("8", f"[잉여 외부 호출] {n} (qualname: {q})",
                       "YAML에 있어야 하나 없음 (YAML 누락 또는 파서 오류)",
                       "DB에서 외부 호출(EXTERNAL_CALL)로 감지됨", SURPLUS)
    else:
        report._print(f"    {c.DIM}(없음 — 모든 DB 외부 호출이 기대값과 일치){c.RESET}")

    # ── 8-3. 오분류: 소스코드에서는 내부 메서드인데 DB에서는 EXTERNAL_CALL ──
    # DB 외부 호출 중 YAML internal에만 매칭되는 것 (external에는 매칭 안 됨)
    misclass_int_to_ext = [(n, q) for n, q in db_external_pairs
                           if _reverse_match(n, q, exp_internal)
                           and not _reverse_match(n, q, exp_external)]
    misclass_int_to_ext.sort(key=lambda x: x[0])
    report._print(f"\n  {c.BOLD}8-3. 오분류: 내부 → 외부 ({len(misclass_int_to_ext)}건){c.RESET}")
    report._print(f"       {c.DIM}소스코드상 사용자가 직접 작성한 내부 메서드인데,{c.RESET}")
    report._print(f"       {c.DIM}파서가 EXTERNAL_CALL(라이브러리 호출)로 잘못 분류한 경우입니다.{c.RESET}")
    if misclass_int_to_ext:
        for n, q in misclass_int_to_ext:
            report.add("8", f"[오분류 내부→외부] {n} (qualname: {q})",
                       "내부 메서드(METHOD)로 분류되어야 함",
                       "EXTERNAL_CALL로 잘못 분류됨", MISCLASSIFIED)
    else:
        report._print(f"    {c.DIM}(없음){c.RESET}")

    # ── 8-4. 오분류: 소스코드에서는 외부 호출인데 DB에서는 내부 METHOD ──
    # DB 내부 호출 중 YAML external에만 매칭되는 것 (internal에는 매칭 안 됨)
    misclass_ext_to_int = [(n, q) for n, q in db_internal_pairs
                           if _reverse_match(n, q, exp_external)
                           and not _reverse_match(n, q, exp_internal)]
    misclass_ext_to_int.sort(key=lambda x: x[0])
    report._print(f"\n  {c.BOLD}8-4. 오분류: 외부 → 내부 ({len(misclass_ext_to_int)}건){c.RESET}")
    report._print(f"       {c.DIM}소스코드상 프레임워크/라이브러리의 외부 호출인데,{c.RESET}")
    report._print(f"       {c.DIM}파서가 내부 METHOD(사용자 작성 코드)로 잘못 분류한 경우입니다.{c.RESET}")
    if misclass_ext_to_int:
        for n, q in misclass_ext_to_int:
            report.add("8", f"[오분류 외부→내부] {n} (qualname: {q})",
                       "외부 호출(EXTERNAL_CALL)로 분류되어야 함",
                       "내부 METHOD로 잘못 분류됨", MISCLASSIFIED)
    else:
        report._print(f"    {c.DIM}(없음){c.RESET}")


# ============================================================
#  9단계: DTO 필드 검증
# ============================================================

def step9_dto_fields(db, report, dto_expectations):
    """9단계. DTO/VO 필드 검증"""
    print_step_header(report, 9,
        "DTO 필드 검증",
        "메서드와 관련된 DTO/VO 클래스의 필드가 DB에 올바르게 저장되어 있는지 확인합니다.\n"
        "  검증 항목: 필드 존재 여부, 필드 타입 일치 여부, 제약조건 어노테이션(@Valid 등)",
        {
            OK:          "필드 정보가 소스코드와 일치합니다.",
            MISSING:     "기대하는 필드 또는 TYPE 노드가 DB에 없습니다.",
            MISMATCH:    "필드 타입이 소스코드와 다릅니다.",
            ANN_MISSING: "제약조건 어노테이션(@NotNull, @Valid 등)이 DB에 없습니다.",
        })
    if not dto_expectations:
        report._print(f"  {report.c.DIM}(해당 없음 — 검증 대상 DTO가 없습니다){report.c.RESET}")
        return
    for dto_name, fields in dto_expectations.items():
        report._print(f"\n  ── {dto_name} ──")
        records = db.execute_query("""
            MATCH (t:TYPE {name: $dto})-[:CONTAINS]->(f:FIELD)
            RETURN f.name AS name, f.type AS type, f.constraint AS constraint
        """, {"dto": dto_name})

        if not records:
            type_exists = db.execute_query(
                "MATCH (t:TYPE {name: $dto}) RETURN t.name", {"dto": dto_name})
            if not type_exists:
                report.add("9", f"{dto_name} TYPE 노드", "존재", "없음", MISSING)
                continue

        actual_fields = {}
        for r in records:
            ftype = r["type"]
            if isinstance(ftype, str):
                try:
                    ftype = json.loads(ftype)
                except (json.JSONDecodeError, TypeError):
                    pass
            actual_fields[r["name"]] = {
                "type": ftype.get("given", "") if isinstance(ftype, dict) else str(ftype),
                "constraint": r["constraint"] or "",
            }

        for fname, fexp in fields.items():
            actual = actual_fields.get(fname)
            if actual is None:
                report.add("9", f"{dto_name}.{fname}", "존재", "없음", MISSING)
                continue
            if actual["type"] == fexp["type"]:
                report.add("9", f"{dto_name}.{fname} 타입",
                           fexp["type"], actual["type"], OK)
            else:
                report.add("9", f"{dto_name}.{fname} 타입",
                           fexp["type"], actual["type"], MISMATCH)
            if fexp["constraint"]:
                if actual["constraint"] == fexp["constraint"]:
                    report.add("9", f"{dto_name}.{fname} constraint",
                               fexp["constraint"], actual["constraint"], OK)
                elif not actual["constraint"]:
                    report.add("9", f"{dto_name}.{fname} constraint",
                               fexp["constraint"], "(빈값)", ANN_MISSING)
                else:
                    report.add("9", f"{dto_name}.{fname} constraint",
                               fexp["constraint"], actual["constraint"], MISMATCH)


# ============================================================
#  원인 분석 (교차 검증) — 실패 시 상세 원인 제공
# ============================================================

def cross_check(db, report, ctrl, method, all_expected_calls):
    """교차 검증: 실패 원인을 3가지 관점에서 분석.

    1. 오분류 상세: EXTERNAL_CALL인데 동명 METHOD가 프로젝트 내에 존재
    2. 완전 누락: METHOD에도 EXTERNAL_CALL에도 없는 기대 호출
    3. qualname 불완전: receiver가 해석되지 않은 EXTERNAL_CALL
    """
    # 1. 오분류 상세 — EXTERNAL_CALL인데 동명 내부 METHOD가 존재하는 것
    misclassified_raw = db.execute_query("""
        MATCH (c:TYPE {name: $ctrl})-[:CONTAINS]->(m:METHOD {name: $method})
        MATCH (m)-[:CALLS*1..]->(ext:EXTERNAL_CALL)
        WHERE EXISTS { MATCH (:TYPE)-[:CONTAINS]->(im:METHOD) WHERE im.name = ext.name }
        MATCH (it:TYPE)-[:CONTAINS]->(im:METHOD) WHERE im.name = ext.name
        RETURN DISTINCT ext.name AS ext_name, ext.qualname AS ext_qn,
               im.qualname AS int_qn, it.name AS owner
    """, {"ctrl": ctrl, "method": method})

    # false positive 필터링: EXTERNAL_CALL qualname의 타입 접두어(대문자 시작)가
    # 내부 메서드 owner와 다르면 동명이지만 별개 메서드 → 오분류 아님
    #   예: Instant.now (타입=Instant) vs Meta.now (owner=Meta) → 제외
    misclassified = []
    for r in misclassified_raw:
        ext_qn = r.get("ext_qn") or ""
        owner = r.get("owner") or ""
        if "." in ext_qn:
            # qualname에서 메서드명 직전의 타입 부분 추출
            ext_type_part = ext_qn.rsplit(".", 1)[0].rsplit(".", 1)[-1]
            # '$' 포함 시 내부 클래스명만 추출 (예: ApiResponse$Meta → Meta)
            if "$" in ext_type_part:
                ext_type_part = ext_type_part.rsplit("$", 1)[-1]
            # 대문자 시작(타입명) + owner와 불일치 → false positive
            if ext_type_part and ext_type_part[0].isupper() and ext_type_part != owner:
                continue
        misclassified.append(r)

    # 2. 완전 누락 — METHOD에도 EXTERNAL_CALL에도 없는 기대 호출
    missing = []
    if all_expected_calls:
        all_captured_records = db.execute_query("""
            MATCH (c:TYPE {name: $ctrl})-[:CONTAINS]->(m:METHOD {name: $method})
            OPTIONAL MATCH (m)-[:CALLS*1..]->(t:METHOD)
            OPTIONAL MATCH (m)-[:CALLS*1..]->(e:EXTERNAL_CALL)
            RETURN collect(DISTINCT t.name) + collect(DISTINCT e.name) AS all_names,
                   collect(DISTINCT t.qualname) + collect(DISTINCT e.qualname) AS all_qualnames
        """, {"ctrl": ctrl, "method": method})
        all_names = set(
            x for x in (all_captured_records[0]["all_names"] if all_captured_records else []) if x
        )
        all_qualnames = set(
            x for x in (all_captured_records[0]["all_qualnames"] if all_captured_records else []) if x
        )
        missing = [c for c in all_expected_calls if not _match_call(c, all_names, all_qualnames)[0]]

    # 3. qualname 불완전 — receiver가 해석되지 않은 EXTERNAL_CALL
    incomplete = db.execute_query("""
        MATCH (c:TYPE {name: $ctrl})-[:CONTAINS]->(m:METHOD {name: $method})
        MATCH (m)-[:CALLS*1..]->(ext:EXTERNAL_CALL)
        WHERE NOT ext.qualname CONTAINS '.'
        RETURN DISTINCT ext.name AS name, ext.qualname AS qualname
    """, {"ctrl": ctrl, "method": method})

    if not misclassified and not missing and not incomplete:
        return

    c = report.c
    report._print(f"\n{c.BOLD}{'━' * 64}{c.RESET}")
    report._print(f"  {c.BOLD}{c.MAGENTA}원인 분석 (교차 검증): {ctrl}.{method}{c.RESET}")
    report._print(f"{c.BOLD}{'━' * 64}{c.RESET}")

    if misclassified:
        report._print(f"\n  {c.YELLOW}[오분류 상세]{c.RESET} 외부 호출(EXTERNAL_CALL)로 분류되었지만, 프로젝트 내에 동명 내부 METHOD가 존재 ({len(misclassified)}건)")
        report._print(f"  {c.DIM}→ 파서가 변수 타입을 해석하지 못해, 사용자 작성 메서드를 외부 호출로 잡은 것입니다.{c.RESET}")
        for r in misclassified:
            report._print(f"    {c.RED}✗{c.RESET} {r['ext_name']}")
            report._print(f"      {c.DIM}현재 DB 분류: EXTERNAL_CALL (qualname: {r['ext_qn']}){c.RESET}")
            report._print(f"      {c.DIM}실제 소스코드: {r['owner']}.{r['ext_name']} (qualname: {r['int_qn']}){c.RESET}")

    if missing:
        report._print(f"\n  {c.RED}[완전 누락]{c.RESET} 내부 METHOD에도 외부 EXTERNAL_CALL에도 없음 ({len(missing)}건)")
        report._print(f"  {c.DIM}→ 파서가 해당 호출을 전혀 감지하지 못한 것입니다 (메서드 레퍼런스 ::, 체이닝 끊김 등).{c.RESET}")
        for m in missing:
            report._print(f"    {c.RED}✗{c.RESET} {m}")

    if incomplete:
        report._print(f"\n  {c.YELLOW}[qualname 불완전]{c.RESET} receiver가 해석되지 않은 외부 호출 ({len(incomplete)}건)")
        report._print(f"  {c.DIM}→ qualname에 '.'이 없어서 어떤 객체에서 호출되는지 파악할 수 없습니다.{c.RESET}")
        for r in incomplete:
            report._print(f"    {c.RED}✗{c.RESET} {r['name']}: {c.DIM}qualname=\"{r['qualname']}\"{c.RESET}")


# ============================================================
#  검증 실행 오케스트레이터
# ============================================================

def execute_verify(endpoint: str, output_filename: str | None):
    """검증 실행 메인.

    실행 순서:
      사전확인. FILE→TYPE→METHOD 존재 여부 (실패 시 중단)
      1단계. 클래스 → 필드(DI 주입) 소속 확인
      2단계. 필드 → 타입 연결 확인
      3단계. 메서드 속성 검증
      4단계. 파라미터 타입 연결 검증
      5단계. 리턴 타입 연결 검증
      6단계. 내부 호출 체인 검증
      7단계. 외부 호출 체인 검증
      8단계. 역방향 검증 (잉여/오분류 탐지)
      9단계. DTO 필드 검증
      최종 리포트 + 원인 분석
    """
    from graph_db.client import DBClient

    ctrl, method = parse_endpoint(endpoint)
    output_path = resolve_output_path(output_filename, ".txt")

    out = open(output_path, "w", encoding="utf-8") if output_path else sys.stdout

    try:
        db = DBClient()
        method_expected = EXPECTED[ctrl][method]
        class_level = EXPECTED[ctrl].get("class_level", {})
        related_types = method_expected.get("related_types", {})

        report = Report(out)
        expected_fields = class_level.get("fields", {})
        expected_internal = method_expected.get("internal_calls", [])
        expected_external = method_expected.get("external_calls", [])
        expected_param_types = method_expected.get("param_types", [])
        expected_return_types = method_expected.get("return_types", [])

        c = report.c
        print_to = lambda *a, **kw: print(*a, file=out, **kw)
        print_to(f"{c.BOLD}{'━' * 64}{c.RESET}")
        print_to(f"  {c.BOLD}{c.BRIGHT_CYAN}V&V 검증: {ctrl}.{method}{c.RESET}")
        print_to(f"{c.BOLD}{'━' * 64}{c.RESET}")

        # ── 사전 확인: FILE→TYPE→METHOD 존재 여부 ──
        if not precheck(db, out, ctrl, method):
            db.close()
            if output_path:
                out.close()
                print(f"검증 중단: {ctrl}.{method} — 사전 확인 실패")
                print(f"  리포트 저장: {output_path}")
            return

        # ── 구조 검증 (1~2단계) ──
        step1_type_contains_field(db, report, ctrl, expected_fields)
        step2_field_contains_type(db, report, ctrl, expected_fields, related_types)

        # ── 속성 검증 (3단계) ──
        step3_method_attributes(db, report, ctrl, method, method_expected)

        # ── 관계 검증 (4~7단계) ──
        step4_has_parameter(db, report, ctrl, method, expected_param_types)
        step5_returns(db, report, ctrl, method, expected_return_types)
        step6_internal_calls(db, report, ctrl, method, expected_internal)
        step7_external_calls(db, report, ctrl, method, expected_external)

        # ── 역방향 검증 (8단계) ──
        step8_reverse_verification(
            db, report, ctrl, method, expected_internal, expected_external
        )

        # ── DTO 필드 검증 (9단계) ──
        step9_dto_fields(db, report, related_types)

        # ── 최종 리포트 ──
        failed = report.summary()

        # ── 원인 분석 (실패/파서버그 있을 때) ──
        if failed > 0:
            all_expected = (expected_internal or []) + (expected_external or [])
            cross_check(db, report, ctrl, method, all_expected)

        db.close()

        if output_path:
            out.close()
            # stdout에도 간결한 요약 출력
            total = len(report.results)
            passed = sum(1 for r in report.results if r[4] == OK)
            print(f"검증 완료: {ctrl}.{method}")
            print(f"  전체: {total}건  |  통과: {passed}건  |  실패+파서버그: {failed}건")
            print(f"  리포트 저장: {output_path}")

    except Exception as e:
        if output_path and not out.closed:
            out.close()
        raise e


# ============================================================
#  CLI
# ============================================================

def list_all_endpoints():
    """등록된 전체 엔드포인트 목록"""
    lines = []
    for ctrl, data in EXPECTED.items():
        for method in data:
            if method == "class_level":
                continue
            exp = data[method]
            http = exp.get("http_method", "?")
            if isinstance(http, list):
                http = ",".join(http)
            uri = exp.get("endpoint_uri", "?")
            lines.append(f"  {ctrl}.{method:<28s}  {http:<12s}  {uri}")
    return "\n".join(lines)


HELP_TEXT = """
사용법:
  .venv/bin/python scripts/verify.py [옵션] [엔드포인트]

옵션:
  -v, --view-expected ENDPOINT   기대값(EXPECTED) 조회 (JSON)
  -x, --execute ENDPOINT         Neo4j 대조 검증 실행
  -o, --output FILENAME          결과를 파일로 저장 (-v: .json, -x: .txt)
  -l, --list                     등록된 전체 엔드포인트 목록
  -h, --help                     이 도움말 표시

엔드포인트 형식:
  Controller.method              예: AuthController.login

검증 단계 (9단계):
  [사전확인] FILE→TYPE→METHOD 존재 여부 (실패 시 중단)
  [1단계]  클래스 → 필드(DI 주입) 소속 확인
  [2단계]  필드 → 타입 연결 확인
  [3단계]  메서드 속성 검증 (HTTP 메서드, URI, 파라미터, 어노테이션)
  [4단계]  파라미터 타입 연결 검증
  [5단계]  리턴 타입 연결 검증
  [6단계]  내부 호출 체인 검증 (사용자 작성 코드)
  [7단계]  외부 호출 체인 검증 (프레임워크/라이브러리)
  [8단계]  역방향 검증 — 잉여/오분류 탐지
  [9단계]  DTO 필드 검증 (이름, 타입, 제약조건)

예시:
  # 기대값 조회 (stdout)
  .venv/bin/python scripts/verify.py -v AuthController.login

  # 기대값 파일 저장
  .venv/bin/python scripts/verify.py -v AuthController.login -o ex_login

  # 검증 실행 (stdout)
  .venv/bin/python scripts/verify.py -x AuthController.login

  # 검증 실행 + 파일 저장
  .venv/bin/python scripts/verify.py -x AuthController.login -o result_login
"""


def main():
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("-v", "--view-expected", metavar="ENDPOINT")
    parser.add_argument("-x", "--execute", metavar="ENDPOINT")
    parser.add_argument("-o", "--output", metavar="FILENAME")
    parser.add_argument("-l", "--list", action="store_true")
    parser.add_argument("-h", "--help", action="store_true")

    args = parser.parse_args()

    if args.help or (not args.view_expected and not args.execute and not args.list):
        print(HELP_TEXT)
        if not args.list:
            count = sum(1 for c in EXPECTED.values() for k in c if k != "class_level")
            print(f"등록된 엔드포인트 ({count}개):")
            print(list_all_endpoints())
        return

    if args.list:
        count = sum(1 for c in EXPECTED.values() for k in c if k != "class_level")
        print(f"등록된 엔드포인트 ({count}개):")
        print(list_all_endpoints())
        return

    if args.view_expected:
        view_expected(args.view_expected, args.output)

    elif args.execute:
        execute_verify(args.execute, args.output)


if __name__ == "__main__":
    main()
