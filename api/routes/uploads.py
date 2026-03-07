from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Request
from typing import List
import os
import logging
from config import Config, should_exclude_path
import zipfile

logger = logging.getLogger(__name__)

router = APIRouter()

from typing import List, Optional
    
@router.post("/upload")
async def upload_files(request: Request, project: Optional[str] = Form(None), files: List[UploadFile] = File(...)):
    """
    소스 파일 또는 ZIP 파일을 업로드하고 분석을 시작합니다.
    - 개별 파일: 메모리에서 직접 분석
    - ZIP 파일: 자동 압축 해제 후 메모리에서 분석
    **Java(.java) 파일만 처리됩니다.**
    """
    analyzer = getattr(request.app.state, "analyzer", None)
    if not analyzer:
        raise HTTPException(status_code=503, detail="Analysis Agent not initialized")
    
    # Project Name Logic
    # 1. If provided, use it.
    # 2. If not, wait until we see a Zip file to decide.
    safe_project = None
    if project:
        safe_project = "".join(c for c in project if c.isalnum() or c in ('-', '_'))
    
    # If still None, we will set it from the first Zip file found.

    
    files_data = [] # [{"path": "relative/path.java", "content": b"..."}]
    
    for file in files:
        # Check hidden files
        if os.path.basename(file.filename).startswith('.'):
            continue
        
        # Check ZIP
        if file.filename.endswith('.zip'):
             if not safe_project:
                 # Default project name from Zip filename
                 raw_name = os.path.splitext(file.filename)[0]
                 safe_project = "".join(c for c in raw_name if c.isalnum() or c in ('-', '_'))
             
             try:
                # ZIP 전체를 메모리에 올리지 않고, 디스크 임시파일에서 직접 읽기
                # (FastAPI UploadFile은 1MB 초과 시 자동으로 디스크 SpooledTemporaryFile 사용)
                await file.seek(0)
                with zipfile.ZipFile(file.file, 'r') as zip_ref:
                    for zip_info in zip_ref.namelist():
                        if zip_info.endswith('/') or os.path.basename(zip_info).startswith('.'):
                            continue
                        
                        # 제외 대상 경로 필터링
                        if should_exclude_path(zip_info, Config.EXCLUDED_DIRS):
                            continue

                        # Check extension (Java Only)
                        _, ext = os.path.splitext(zip_info)
                        if ext not in Config.ALLOWED_EXTENSIONS:
                            continue
                        
                        content = zip_ref.read(zip_info)
                        files_data.append({"path": zip_info, "content": content})
                        
             except zipfile.BadZipFile:
                raise HTTPException(status_code=400, detail=f"Invalid ZIP file: {file.filename}")
        
        else:
            # Regular File
            if should_exclude_path(file.filename, Config.EXCLUDED_DIRS):
                continue

            _, ext = os.path.splitext(file.filename)
            if ext not in Config.ALLOWED_EXTENSIONS:
                continue
            
            content = await file.read()
            files_data.append({"path": file.filename, "content": content})
            
    if not files_data:
        raise HTTPException(status_code=400, detail="No valid Java files found")
        
    # Process Files
    if not safe_project:
        safe_project = "default_project"

    try:
        # Calls IncrementalAnalyzer.process_files_from_memory
        result_files = analyzer.analyze(files_data, project=safe_project)
        
        # Get processed method list for UI response
        method_list = []
        for rel_path in result_files:
             methods = analyzer.connector.execute_query(
                """
                MATCH (f:FILE {path: $path, project: $project})-[:CONTAINS*]->(m:METHOD)
                WITH DISTINCT m, f
                RETURN m.name as name, m.signature as sig, elementId(m) as id, f.path as file
                """,
                {"path": rel_path, "project": safe_project}
            )
             if methods:
                for m in methods:
                    method_list.append({
                        "id": m.get('id'),
                        "name": m.get('name'),
                        "file": m.get('file'),
                        "status": "Unknown", # f.status Removed
                        "signature": m.get('sig')
                    })
        
        return {
            "result": {
                "message": f"Successfully analyzed {len(result_files)} files.",
                "changes": [{"file_path": f, "status": "processed"} for f in result_files],
                "methods": method_list,
                "graph": {"nodes": [], "edges": []} # Graph not returned to optimize performance
            }
        }
    except Exception as e:
        logger.error(f"Analysis failed: {e}")
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")
