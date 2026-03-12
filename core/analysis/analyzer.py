import logging
import os
import hashlib
import uuid
from graph_db.client import DBClient
from core.analysis.lang import PARSERS, collect_root_patterns
from core.analysis.store.models import ParsedRegistry, ParsedType, ParsedField, ParsedMethod
from core.analysis.store.edge_linker import EdgeLinker
from core.analysis.store.graph_writer import GraphWriter
from config import Config
from graph_db.queries import CypherQueries

logger = logging.getLogger(__name__)


class Analyzer:
    """
    [분석 파이프라인 (Orchestrator)]
    전체 파일 분석 프로세스를 관리하고 조정하는 핵심 클래스입니다.

    파일의 변경 사항(생성, 수정, 삭제)을 감지하고,
    적절한 파서(Parser)를 호출하여 그래프 DB를 업데이트합니다.

    분석 파이프라인 개요:
        cleanup → snapshot → map rel paths    (전처리)
        parse → restore → resolve             (파싱)    
        write → prune → detect deletions      (후처리)

    파이프라인 상세는 analyze() docstring 참조
    """

    def __init__(self, connector: DBClient):
        self.connector = connector
        self.writer = GraphWriter(connector)

    # ──────────────────────────────────────────────
    #  Public API
    # ──────────────────────────────────────────────

    def analyze(self, files_data: list[dict], project: str | None = None) -> list[str]:
        """
        [분석 실행]
        사용자가 업로드한 파일 목록(files_data)을 받아 전체 분석을 수행합니다.

        파이프라인 단계:
            1. cleanup old deletions  — 지난 분석에서 삭제 표시된 노드 청소
            2. snapshot (prev hash)   — DB에서 이전 스캔파일 해시들을 조회 (변경 비교용)
            3. map rel-paths          — DB 저장용 상대경로로 변환 - 매핑
            4. parse changed          — 각 파일을 읽어 변경된 파일만 파싱
            5. restore registry       — 변경 없는 파일의 노드를 DB에서 읽어 인메모리 인덱스 복원 
            6. resolve edges          — 복원된 인메모리 인덱스를 사용해 엣지 보강
            7. write to DB            — DB에 일괄로 저장
            8. prune methods          — 소스에서 삭제된 메서드를 DB에서 격리
            9. detect deletions       — 업로드에서 빠진 파일의 메서드를 격리하고 구조 노드를 삭제

        Args:
            files_data: [{'path': str, 'content': bytes}, ...] 형태의 파일 목록
            project: 프로젝트 식별자 (기본값: "default")

        Returns:
            처리된 파일들의 경로 목록 (Frontend 갱신용)
        """
        project = project or "default"
        registry = ParsedRegistry() # 메모리 저장소

        # 1. 이전 DELETED 노드 정리
        self._clean_old_deleted_nodes(project)

        # 2. DB 스냅샷: {상대경로 → 해시} 매핑
        oldfile_hashes = self._snapshot_old_scan(project)

        # 3. 소스 루트 마커 기반 상대경로 계산
        relative_paths = self._map_to_relative_paths(files_data)

        # 4. 변경 감지 + 변경 파일 파싱 → registry 축적
        unchanged, changed = self._parse(files_data, oldfile_hashes, relative_paths, project, registry)

        # 5. 변경 없는 파일의 노드를 DB에서 복원 (EdgeLinker 인덱스용)
        self._restore_registry(unchanged, project, registry)

        # 6. 호출 관계 해석
        registry.resolved = EdgeLinker(registry).resolve()

        # 7. 분석 결과 DB 일괄 저장 (AS-IS status → FILE → 노드 → 엣지)
        self.writer.write(registry, changed, unchanged, project)

        # 8. 삭제된 메서드 정리 (write 후 실행하여 기존 CALLS 보존)
        self.writer.prune_removed_methods(
            [{"file_path": f["path"], "scan_id": f["scan_id"]} for f in changed]
        )

        # 9. 삭제된 파일 감지 + DELETED 마킹
        uploaded = set(relative_paths.values())
        deleted = self._detect_deletions(oldfile_hashes, uploaded, project)

        return list(uploaded) + deleted

    # ──────────────────────────────────────────────
    #  Pipeline Stages
    # ──────────────────────────────────────────────

    def _clean_old_deleted_nodes(self, project: str):
        """
        [1단계: 유령 노드 정리]
        이전 분석 사이클에서 'DELETED'로 마킹된 노드들을 DB에서 영구 삭제합니다.

        왜 즉시 삭제하지 않고 마킹 후 다음 사이클에 삭제하는가?
        → 삭제 직후 프론트엔드가 해당 노드를 참조할 수 있으므로,
          한 사이클의 유예 기간을 두어 안전하게 제거합니다.
        """
        logger.info(f"Cleaning up ghost nodes for project: {project}")
        self.connector.execute_query(
            CypherQueries.DELETE_PROJECT_DELETED_NODES,
            {"project": project}
        )

    def _snapshot_old_scan(self, project: str) -> dict[str, str]:
        """
        [2단계: DB 스냅샷]
        현재 DB에 저장된 파일 목록과 해시값을 조회합니다.
        이 스냅샷이 변경 감지의 기준점이 됩니다.

        Returns:
            {상대경로: SHA-256 해시} 매핑
        """
        rows = self.connector.execute_query(
            CypherQueries.GET_PROJECT_FILES_HASH,
            {"project": project}
        )
        return {row['path']: row['hash'] for row in rows}

    def _map_to_relative_paths(self, files_data: list[dict]) -> dict[str, str]:
        """
        [3단계: 상대경로 계산]
        각 파일의 원본 경로를 DB 저장용 상대경로로 변환합니다.

        소스 루트 패턴(src/main/java/ 등)을 탐지하여:
          - 패턴 앞: 마지막 세그먼트를 모듈명으로 보존
          - 패턴 뒤: 패키지/소스 경로를 전체 보존
          - 결과: {모듈명}/{패키지경로}

        패턴이 없는 파일은 공통 prefix 제거 fallback을 사용합니다.

        예시:
          backend/user-service/src/main/java/com/ex/A.java
          → user-service/com/ex/A.java

        Returns:
            {원본경로: 상대경로} 매핑
        """
        patterns = collect_root_patterns()
        rel_path_map = {}
        unresolved = []

        for file_data in files_data:
            original = file_data['path']
            relative = self._resolve_by_pattern(original, patterns)
            if relative is not None:
                rel_path_map[original] = relative
            else:
                unresolved.append(original)

        # 패턴 미발견 파일: 공통 prefix 제거 fallback
        if unresolved:
            fallback = self._common_prefix_fallback(unresolved)
            rel_path_map.update(fallback)

        return rel_path_map

    def _resolve_by_pattern(self, path: str, patterns: list[str]) -> str | None:
        """
        소스 루트 패턴으로 상대경로를 계산합니다.

        패턴 기준으로 경로를 분할:
          - 패턴 앞 마지막 세그먼트 = 모듈명 (없으면 생략)
          - 패턴 뒤 = 패키지/소스 경로

        Args:
            path: 원본 파일 경로
            patterns: 소스 루트 패턴 목록 (우선순위 순)

        Returns:
            상대경로 (패턴 발견 시), None (패턴 미발견 시)
        """
        for marker in patterns:
            idx = path.find(marker)
            if idx < 0:
                continue

            # 마커 뒤 = 패키지 경로
            package_path = path[idx + len(marker):]

            # 마커 앞에서 마지막 세그먼트 = 모듈명
            prefix = path[:idx].rstrip('/')
            module_name = prefix.rsplit('/', 1)[-1] if prefix else ""

            if module_name:
                return f"{module_name}/{package_path}"
            return package_path

        return None

    def _common_prefix_fallback(self, paths: list[str]) -> dict[str, str]:
        """
        소스 루트 마커가 없는 파일들의 fallback 상대경로 계산.
        공통 경로 세그먼트를 앞에서부터 비교하여 제거합니다.
        """
        if len(paths) == 1:
            root = os.path.dirname(paths[0])
        else:
            parts_list = [p.split('/') for p in paths]
            common_parts = []
            for i, part in enumerate(parts_list[0]):
                if all(
                    i < len(parts) and parts[i] == part
                    for parts in parts_list
                ):
                    common_parts.append(part)
                else:
                    break
            root = '/'.join(common_parts) if common_parts else ''

        return {
            p: os.path.relpath(p, root) if root else p
            for p in paths
        }

    def _parse(self, files_data: list[dict], hash_map: dict[str, str], rel_path_map: dict[str, str], project: str, registry: ParsedRegistry) -> tuple[list[str], list[dict]]:
        """
        [4단계: 변경 감지 + 변경 파일 파싱]
        업로드된 파일들을 순회하며 각각의 변경 상태를 판별하고,
        NEW/MODIFIED 파일만 언어별 파서로 분석하여 ParsedRegistry에 축적합니다.
        AS-IS 파일은 경로만 수집합니다 (DB 복원은 analyze()에서 별도 수행).

        DB 접근 없음 — 순수 파싱 + 분류만 수행합니다.

        Args:
            files_data: 업로드 파일 목록
            hash_map: DB 스냅샷 (변경 감지 기준)
            rel_path_map: {원본경로: 상대경로} 매핑 (_map_to_relative_paths 결과)
            project: 프로젝트 식별자
            registry: 파싱 결과를 축적할 인메모리 등록소

        Returns:
            (unchanged, changed) 튜플
            - unchanged: 변경 없는 파일 경로 목록 (DB 복원 대상)
            - changed: FILE 노드 메타데이터 + scan_id (upsert/prune 겸용)
        """
        unchanged = []
        changed = []

        for file_data in files_data:
            try:
                path, file_row = self._process_file(file_data, hash_map, rel_path_map, project, registry)

                if file_row is not None:                             # NEW/MODIFIED
                    changed.append(file_row)
                else:                                                # AS-IS
                    unchanged.append(path)
            except Exception as e:
                logger.error(f"Failed to process {file_data['path']}: {e}")

        return unchanged, changed

    def _process_file(self, file_data: dict, hash_map: dict[str, str], rel_path_map: dict[str, str], project: str, registry: ParsedRegistry) -> tuple[str, dict | None]:
        """
        [단일 파일 처리 — DB 접근 없음]
        하나의 파일에 대해 다음을 수행합니다:
            1. SHA-256 해시 계산 → 변경 상태 판별 (NEW / MODIFIED / AS-IS)
            2. AS-IS → 파싱 건너뛰기 (DB 복원은 _restore_registry()에서 일괄 처리)
            3. NEW/MODIFIED → FILE 메타데이터 구성 + 언어 파서 호출 → registry에 축적

        DB 기록은 analyze()에서 배치로 일괄 수행됩니다.

        Args:
            file_data: {'path': str, 'content': bytes}
            hash_map: DB 스냅샷
            rel_path_map: {원본경로: 상대경로} 매핑
            project: 프로젝트 식별자
            registry: 파싱 결과를 축적할 인메모리 등록소

        Returns:
            (relative_path, file_row) 튜플
            - AS-IS: file_row=None (파싱 불필요)
            - NEW/MODIFIED: file_row=FILE 메타데이터 + scan_id
        """
        file_path = file_data['path']
        content = file_data['content']

        # 경로 및 해시 계산
        file_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
        relative_path = rel_path_map[file_path]
        file_name = os.path.basename(file_path)

        # 변경 상태 판별: DB 해시와 비교
        if relative_path not in hash_map:
            status = "NEW"
        elif hash_map[relative_path] != file_hash:
            status = "MODIFIED"
        else:
            status = "AS-IS"

        logger.info(f"Processing {relative_path}: {status}")

        # AS-IS: 파싱 건너뛰기 (DB 복원으로 대체)
        if status == "AS-IS":
            return relative_path, None

        # NEW/MODIFIED: 언어 판별 + 파싱 + 메모리 축적
        ext = os.path.splitext(file_name)[1]
        language = Config.ALLOWED_EXTENSIONS.get(ext, "UNKNOWN")

        # 파싱 + 메모리 축적 (dirty 자동 추적)
        scan_id = str(uuid.uuid4())
        lang_parser = PARSERS.get(language)
        if lang_parser:
            source_bytes = content.encode("utf-8") if isinstance(content, str) else content
            result = lang_parser.parse(source_bytes, relative_path, scan_id)
            registry.collect(result)

        # FILE 노드 메타데이터 (배치용, scan_id 포함 — prune에서도 사용)
        file_row = {
            "path": relative_path,
            "name": file_name,
            "hash": file_hash,
            "language": language,
            "project": project,
            "scan_id": scan_id,
        }

        return relative_path, file_row

    def _restore_registry(self, unchanged: list[str], project: str, registry: ParsedRegistry):
        """
        [5단계: registry 복원 — 증분 분석 최적화]
        변경 없는 파일의 TYPE/FIELD/METHOD 노드를 DB에서 복원하여
        registry에 추가합니다 (dirty 미포함 → write 대상 아님).

        목적:
            EdgeLinker가 호출 관계를 해석할 때, 변경 없는 타입/메서드도
            인메모리 인덱스에 포함되어야 정확한 해석이 가능합니다.
            tree-sitter 파싱 대신 DB에서 이전 사이클의 결과를 재활용합니다.
        """
        if not unchanged:
            return

        params = {"paths": unchanged, "project": project}

        for row in self.connector.execute_query(CypherQueries.LOAD_ASIS_TYPES, params):
            registry.types[row["qualname"]] = ParsedType.from_db_record(row)

        for row in self.connector.execute_query(CypherQueries.LOAD_ASIS_FIELDS, params):
            registry.fields[row["qualname"]] = ParsedField.from_db_record(row)

        for row in self.connector.execute_query(CypherQueries.LOAD_ASIS_METHODS, params):
            registry.methods[row["qualname"]] = ParsedMethod.from_db_record(row)

        logger.info(f"Restored {len(unchanged)} unchanged files from DB "
                     f"({len(registry.types)} types, {len(registry.fields)} fields, "
                     f"{len(registry.methods)} methods total)")

    def _detect_deletions(self, hash_map: dict[str, str], uploaded: set[str], project: str) -> list[str]:
        """
        [9단계: 삭제 파일 감지 — 2-Phase Mixed Strategy]
        DB 스냅샷(hash_map)에는 있지만 이번 업로드(uploaded)에는 없는 파일을 감지합니다.

        Phase 1: METHOD를 DELETED로 마킹하고 CALLS를 끊어 격리 (이력 보존)
        Phase 2: FILE, TYPE, FIELD 등 구조적 노드를 DB에서 영구 삭제

        METHOD를 즉시 삭제하지 않는 이유:
        → 파일이 삭제되어도 메서드의 존재 이력이나 ID 기반 조회가 가능하도록 보존합니다.
          다음 사이클의 _clean_old_deleted_nodes()에서 영구 삭제됩니다. (1사이클 유예)
        """
        deleted_paths = set(hash_map.keys()) - uploaded
        if not deleted_paths:
            return []

        batch = [{"path": p, "project": project} for p in deleted_paths]
        logger.info(f"Marking {len(batch)} file(s) as DELETED")

        # Phase 1: METHOD 격리 (DELETED 마킹 + CALLS 끊기)
        self.connector.execute_query(
            CypherQueries.BATCH_ISOLATE_DELETED_FILE_METHODS, {"batch": batch}
        )

        # Phase 2: FILE/TYPE/FIELD 구조적 노드 영구 삭제
        self.connector.execute_query(
            CypherQueries.BATCH_DELETE_FILE_STRUCTURES, {"batch": batch}
        )

        return list(deleted_paths)
