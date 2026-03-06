import logging
import os
import hashlib
import uuid
from graph_db.client import DBClient
from core.analysis.lang import PARSERS
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
        cleanup → snapshot → find_root → parse → detect_deletions → flush
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
            3. find_root        — 업로드 파일들의 공통 루트 경로 계산 (상대경로 산출용)
            4. parse            — 각 파일의 변경 상태를 판별하고, 파서로 분석 후 메모리에 축적
            5. detect_deletions — 업로드 목록에 없는 기존 파일을 DELETED로 마킹
            6. flush            — 메모리에 축적된 분석 결과를 일괄 DB 기록 + 호출 관계 해석

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

        # 3. 업로드 파일들의 공통 루트 계산
        root = self._find_root(files_data)

        # 4. 파일별 파싱 + 메모리 축적
        updated, processed = self._parse(files_data, existing, root, project)

        # 5. 삭제된 파일 감지 + DELETED 마킹
        deleted = self._detect_deletions(existing, processed, project)

        # 6. 결과 일괄 기록
        if updated or deleted:
            logger.info("Flushing analysis results to DB...")
            self.writer.flush()

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

    def _find_root(self, files_data: list[dict]) -> str:
        """
        [3단계: 공통 루트 경로 계산]
        업로드된 파일들의 경로에서 공통 상위 디렉토리를 찾습니다.
        이 루트를 기준으로 상대 경로를 계산하여 DB에 저장합니다.

        예시:
            입력: ['src/main/A.java', 'src/main/B.java', 'src/test/C.java']
            공통 루트: 'src'
            상대경로: 'main/A.java', 'main/B.java', 'test/C.java'

        NOTE: 단일 모듈에서 패키지 구조가 과도하게 잘릴 수 있는 문제가 있습니다.
              추후 uploads.py로 이동하거나 로직 개선이 필요합니다.
        """
        if not files_data:
            return ""

        paths = [f['path'] for f in files_data]

        # 파일이 1개면 해당 파일의 디렉토리가 루트
        if len(paths) == 1:
            return os.path.dirname(paths[0])

        # 여러 파일이면 공통 경로 세그먼트를 앞에서부터 비교
        common_parts = []
        first_parts = paths[0].split('/')
        for i, part in enumerate(first_parts):
            if all(
                i < len(p.split('/')) and p.split('/')[i] == part
                for p in paths
            ):
                common_parts.append(part)
            else:
                break

        return '/'.join(common_parts) if common_parts else ''

    def _parse(self, files_data: list[dict], existing: dict[str, str], root: str, project: str) -> tuple[list[str], set[str]]:
        """
        [4단계: 파일별 파싱 + 메모리 축적]
        업로드된 파일들을 순회하며 각각의 변경 상태를 판별하고,
        언어별 파서로 분석한 결과를 GraphWriter 메모리에 축적합니다.

        Memory-First 설계:
            호출 관계(CALLS) 해석은 모든 타입/메서드가 메모리에 있어야 정확합니다.
            따라서 AS-IS(변경 없음) 파일도 파싱하여 메모리 인덱스를 완성합니다.
            DB 기록은 flush()에서 일괄 수행됩니다.

        Args:
            files_data: 업로드 파일 목록
            existing: DB 스냅샷 (변경 감지 기준)
            root: 공통 루트 경로
            project: 프로젝트 식별자

        Returns:
            (updated_files, processed_paths) 튜플
            - updated_files: 처리된 파일 경로 목록
            - processed_paths: 처리된 상대경로 집합 (삭제 감지용)
        """
        updated_files = []
        processed_paths = set()

        # 파일별 처리
        for file_data in files_data:
            try:
                result = self._process_file(file_data, existing, root, project)
                if result:
                    path, _ = result
                    updated_files.append(path)
                    processed_paths.add(path)
            except Exception as e:
                logger.error(f"Failed to process {file_data['path']}: {e}")

        return updated_files, processed_paths

    def _process_file(self, file_data: dict, existing: dict[str, str], root: str, project: str) -> tuple[str, str] | None:
        """
        [단일 파일 처리]
        하나의 파일에 대해 다음을 수행합니다:
            1. SHA-256 해시 계산 → 변경 상태 판별 (NEW / MODIFIED / AS-IS)
            2. FILE 노드 MERGE (DB에 파일 메타데이터 기록)
            3. 언어 파서로 소스 코드 파싱 → 결과를 writer에 축적
            4. prune: 이번 스캔에서 발견되지 않은 메서드를 DELETED 처리

        Args:
            file_data: {'path': str, 'content': bytes}
            existing: DB 스냅샷
            root: 공통 루트 경로
            project: 프로젝트 식별자

        Returns:
            (relative_path, status) 또는 None (처리 실패 시)
        """
        file_path = file_data['path']
        content = file_data['content']

        # 경로 및 해시 계산
        file_hash = hashlib.sha256(content).hexdigest()
        relative_path = os.path.relpath(file_path, root) if root else file_path
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

        # FILE 노드 upsert
        query = """
        MERGE (f:FILE {path: $path, project: $project})
        SET f.name = $name,
        f.hash = $hash,
        f.language = $language
        """
        self.connector.execute_query(query, {
            "path": relative_path,
            "name": file_name,
            "hash": file_hash,
            "language": language,
            "project": project
        })

        # 파싱 + 메모리 축적
        # AS-IS도 파싱하는 이유: Memory-First에서는 flush 후 메모리가 초기화되므로,
        # 매 분석 사이클마다 전체 타입/메서드 인덱스를 다시 구축해야 합니다.
        scan_id = str(uuid.uuid4())
        lang_parser = PARSERS.get(language)
        if lang_parser:
            result = lang_parser.parse(content, relative_path, scan_id)
            self.writer.collect(result)

        # 이번 스캔에서 발견되지 않은 메서드 정리
        self._prune(relative_path, scan_id)

        return relative_path, status

    def _detect_deletions(self, existing: dict[str, str], processed: set[str], project: str) -> list[str]:
        """
        [5단계: 삭제 파일 감지]
        DB 스냅샷(existing)에는 있지만 이번 업로드(processed)에는 없는 파일을
        찾아 DELETED로 마킹하고, 다른 노드와의 관계를 끊어 그래프에서 격리합니다.

        즉시 삭제하지 않는 이유:
        → 다음 사이클의 _cleanup()에서 영구 삭제됩니다. (1사이클 유예)
        """
        deleted_paths = set(existing.keys()) - processed
        deleted_files = []

        for path in deleted_paths:
            logger.info(f"Marking {path} as DELETED")
            self.connector.execute_query(
                CypherQueries.MARK_FILE_DELETED_AND_ISOLATE,
                {"path": path, "project": project}
            )
            deleted_files.append(path)

        return deleted_files

    # ──────────────────────────────────────────────
    #  Internal Helpers
    # ──────────────────────────────────────────────

    def _prune(self, file_path: str, scan_id: str):
        """
        [메서드 가지치기 (Pruning)]
        이번 스캔(scan_id)에서 발견되지 않은 메서드는
        소스 코드에서 삭제된 것으로 간주합니다.

        해당 메서드를 'DELETED'로 마킹하고,
        다른 메서드와의 호출 관계(CALLS)를 끊어 분석 결과 오염을 방지합니다.

        활용 시나리오:
            - 파일 내 메서드가 삭제/리네임된 경우
            - 증분 분석 시 이전 사이클의 잔여 메서드 정리
        """
        query = """
        MATCH (f:FILE {path: $file_path})
        MATCH (f)-[:CONTAINS*1..3]->(m:METHOD)

        WHERE m.last_scan_id <> $scan_id

        // Mark as DELETED
        SET m.status = 'DELETED'

        WITH m
        // [격리] 다른 메서드와의 호출 관계 제거 (분석 방해 방지)
        OPTIONAL MATCH (m)-[r:CALLS]-()
        DELETE r
        """
        try:
            self.connector.execute_query(
                query,
                {"file_path": file_path, "scan_id": scan_id}
            )
            logger.info(f"Pruned stale methods for {file_path} (scan: {scan_id[:8]})")
        except Exception as e:
            logger.error(f"Pruning error ({file_path}): {e}")
