import logging
import os
import hashlib
import uuid
from graph_db.client import DBClient
from core.analysis.lang import PARSERS, collect_root_patterns
from core.analysis.store.models import ParsedRegistry
from core.analysis.store.edge_linker import EdgeLinker
from core.analysis.store.graph_writer import GraphWriter
from config import Config
from graph_db.queries import CypherQueries

logger = logging.getLogger(__name__)


class Analyzer:
    """
    [분석 조정자 (Orchestrator)]
    전체 파일 분석 프로세스를 관리하고 조정하는 핵심 클래스입니다.

    파일의 변경 사항(생성, 수정, 삭제)을 감지하고,
    적절한 파서(Parser)를 호출하여 그래프 DB를 업데이트합니다.

    분석 파이프라인 (analyze 메서드 참조):
        cleanup → snapshot → compute_paths → parse → detect_deletions → resolve → flush
    """

    def __init__(self, connector: DBClient):
        self.connector = connector
        self.writer = GraphWriter(connector)

    # ──────────────────────────────────────────────
    #  Public API
    # ──────────────────────────────────────────────

    def analyze(self, files_data: list[dict], project: str | None = None) -> list[str]:
        """
        [메인 분석 파이프라인]
        사용자가 업로드한 파일 목록(files_data)을 받아 전체 분석을 수행합니다.

        파이프라인 단계:
            1. cleanup          — 이전 분석에서 DELETED로 마킹된 유령 노드를 DB에서 영구 삭제
            2. snapshot         — 현재 DB에 저장된 파일 해시를 조회하여 비교 기준점 확보
            3. compute_paths    — 소스 루트 패턴 기반 상대경로 계산 (패키지 구조 보존)
            4. parse            — 각 파일의 변경 상태를 판별하고, 파서로 분석 후 ParsedRegistry에 축적
            5. detect_deletions — 업로드 목록에 없는 기존 파일을 DELETED로 마킹
            6. resolve + flush  — 인메모리 엣지 해석 후, 분석 결과를 일괄 DB 기록

        Args:
            files_data: [{'path': str, 'content': bytes}, ...] 형태의 파일 목록
            project: 프로젝트 식별자 (기본값: "default")

        Returns:
            업데이트된 파일들의 경로 목록 (Frontend 갱신용)
        """
        project = project or "default"

        # 1. 이전 DELETED 노드 정리
        self._cleanup(project)

        # 2. DB 스냅샷: {상대경로 → 해시} 매핑
        existing = self._snapshot(project)

        # 3. 소스 루트 마커 기반 상대경로 계산
        path_map = self._compute_relative_paths(files_data)

        # 4. 파일별 파싱 + 메모리에 축적
        registry = ParsedRegistry() # 사용자 요청별로 인스턴스화(요청별 공유 방지 설계)
        updated, processed = self._parse(files_data, existing, path_map, project, registry)

        # 5. 삭제된 파일 감지 + DELETED 마킹
        deleted = self._detect_deletions(existing, processed, project)

        # 6. 엣지 보강 + DB 일괄 저장
        if updated or deleted:
            logger.info("Resolving edges and flushing to DB...")
            registry.resolved = EdgeLinker(registry).resolve()          # 인메모리 해석
            self.writer.flush(registry)                                 # DB 저장

        return updated + deleted

    # ──────────────────────────────────────────────
    #  Pipeline Stages
    # ──────────────────────────────────────────────

    def _cleanup(self, project: str):
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

    def _snapshot(self, project: str) -> dict[str, str]:
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

    def _compute_relative_paths(self, files_data: list[dict]) -> dict[str, str]:
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
        path_map = {}
        unresolved = []

        for file_data in files_data:
            original = file_data['path']
            relative = self._resolve_by_pattern(original, patterns)
            if relative is not None:
                path_map[original] = relative
            else:
                unresolved.append(original)

        # 패턴 미발견 파일: 공통 prefix 제거 fallback
        if unresolved:
            fallback = self._common_prefix_fallback(unresolved)
            path_map.update(fallback)

        return path_map

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

    def _parse(self, files_data: list[dict], existing: dict[str, str], path_map: dict[str, str], project: str, registry: ParsedRegistry) -> tuple[list[str], set[str]]:
        """
        [4단계: 파일별 파싱 + 메모리 축적 + 일괄 DB 기록]
        업로드된 파일들을 순회하며 각각의 변경 상태를 판별하고,
        언어별 파서로 분석한 결과를 ParsedRegistry에 축적합니다.

        Memory-First 설계:
            호출 관계(CALLS) 해석은 모든 타입/메서드가 메모리에 있어야 정확합니다.
            따라서 AS-IS(변경 없음) 파일도 파싱하여 메모리 인덱스를 완성합니다.
            DB 기록은 flush()에서 일괄 수행됩니다.

        배치 설계:
            FILE 노드 upsert와 메서드 가지치기(prune)를 파일별로 개별 실행하지 않고,
            루프에서 배치 데이터를 수집한 뒤 UNWIND 쿼리로 일괄 실행합니다.

        Args:
            files_data: 업로드 파일 목록
            existing: DB 스냅샷 (변경 감지 기준)
            path_map: {원본경로: 상대경로} 매핑
            project: 프로젝트 식별자
            registry: 파싱 결과를 축적할 인메모리 등록소

        Returns:
            (updated_files, processed_paths) 튜플
            - updated_files: 처리된 파일 경로 목록
            - processed_paths: 처리된 상대경로 집합 (삭제 감지용)
        """
        updated_files = []
        processed_paths = set()
        file_batch = []
        prune_batch = []

        # 파일별 파싱 + 배치 수집 (DB 접근 없음)
        for file_data in files_data:
            try:
                path, file_row, scan_id = self._process_file(file_data, existing, path_map, project, registry)
                updated_files.append(path)
                processed_paths.add(path)
                file_batch.append(file_row)
                prune_batch.append({"file_path": path, "scan_id": scan_id})
            except Exception as e:
                logger.error(f"Failed to process {file_data['path']}: {e}")

        # FILE 노드 일괄 upsert
        if file_batch:
            self.connector.execute_query(
                CypherQueries.BATCH_UPSERT_FILES, {"batch": file_batch}
            )

        # 스캔에서 누락된 메서드 일괄 가지치기
        if prune_batch:
            self.connector.execute_query(
                CypherQueries.BATCH_PRUNE_STALE_METHODS, {"batch": prune_batch}
            )

        return updated_files, processed_paths

    def _process_file(self, file_data: dict, existing: dict[str, str], path_map: dict[str, str], project: str, registry: ParsedRegistry) -> tuple[str, dict, str]:
        """
        [단일 파일 처리 — DB 접근 없음]
        하나의 파일에 대해 다음을 수행합니다:
            1. SHA-256 해시 계산 → 변경 상태 판별 (NEW / MODIFIED / AS-IS)
            2. FILE 노드 메타데이터 구성 (배치용)
            3. 언어 파서로 소스 코드 파싱 → 결과를 store에 축적

        DB 기록은 _parse()에서 배치로 일괄 수행됩니다.

        Args:
            file_data: {'path': str, 'content': bytes}
            existing: DB 스냅샷
            path_map: {원본경로: 상대경로} 매핑
            project: 프로젝트 식별자
            registry: 파싱 결과를 축적할 인메모리 등록소

        Returns:
            (relative_path, file_row, scan_id) 튜플
            - file_row: FILE 노드 upsert용 배치 데이터
            - scan_id: 메서드 가지치기(prune)용 스캔 식별자
        """
        file_path = file_data['path']
        content = file_data['content']

        # 경로 및 해시 계산
        file_hash = hashlib.sha256(content).hexdigest()
        relative_path = path_map[file_path]
        file_name = os.path.basename(file_path)

        # 언어 판별
        ext = os.path.splitext(file_name)[1]
        language = Config.ALLOWED_EXTENSIONS.get(ext, "UNKNOWN")

        # 변경 상태 판별: DB 해시와 비교
        if relative_path not in existing:
            status = "NEW"
        elif existing[relative_path] != file_hash:
            status = "MODIFIED"
        else:
            status = "AS-IS"

        logger.info(f"Processing {relative_path}: {status}")

        # FILE 노드 메타데이터 (배치용)
        file_row = {
            "path": relative_path,
            "name": file_name,
            "hash": file_hash,
            "language": language,
            "project": project,
        }

        # 파싱 + 메모리 축적
        # AS-IS도 파싱하는 이유: Memory-First에서는 flush 후 메모리가 초기화되므로,
        # 매 분석 사이클마다 전체 타입/메서드 인덱스를 다시 구축해야 합니다.
        scan_id = str(uuid.uuid4())
        lang_parser = PARSERS.get(language)
        if lang_parser:
            result = lang_parser.parse(content, relative_path, scan_id)
            registry.collect(result)

        return relative_path, file_row, scan_id

    def _detect_deletions(self, existing: dict[str, str], processed: set[str], project: str) -> list[str]:
        """
        [5단계: 삭제 파일 감지 — 2-Phase Mixed Strategy]
        DB 스냅샷(existing)에는 있지만 이번 업로드(processed)에는 없는 파일을 감지합니다.

        Phase 1: METHOD를 DELETED로 마킹하고 CALLS를 끊어 격리 (이력 보존)
        Phase 2: FILE, TYPE, FIELD 등 구조적 노드를 DB에서 영구 삭제

        METHOD를 즉시 삭제하지 않는 이유:
        → 파일이 삭제되어도 메서드의 존재 이력이나 ID 기반 조회가 가능하도록 보존합니다.
          다음 사이클의 _cleanup()에서 영구 삭제됩니다. (1사이클 유예)
        """
        deleted_paths = set(existing.keys()) - processed
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
