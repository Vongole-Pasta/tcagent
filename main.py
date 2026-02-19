"""
TcAgent CLI 진입점
서버 실행 및 유틸리티 명령어를 제공합니다.

사용법:
    # FastAPI 서버 실행 (개발 모드)
    python main.py serve

    # FastAPI 서버 실행 (운영 모드)
    APP_ENV=prd python main.py serve

    # DB 초기화
    python main.py init-db
"""
import sys


def serve():
    """FastAPI 개발 서버를 실행합니다."""
    import uvicorn
    uvicorn.run("api.main:app", host="0.0.0.0", port=8000, reload=True)


def init_db():
    """DB 인덱스 및 제약조건을 생성합니다."""
    from infra.db_client import DBClient
    client = DBClient()
    client.create_constraints()
    print("✅ DB 인덱스 및 제약조건 생성 완료")
    client.close()


def main():
    """CLI 커맨드 라우터"""
    commands = {
        "serve": serve,
        "init-db": init_db,
    }

    if len(sys.argv) < 2 or sys.argv[1] not in commands:
        print("사용법: python main.py <command>")
        print(f"가능한 명령어: {', '.join(commands.keys())}")
        sys.exit(1)

    commands[sys.argv[1]]()


if __name__ == "__main__":
    main()
