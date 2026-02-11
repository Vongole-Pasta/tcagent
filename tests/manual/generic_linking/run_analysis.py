import asyncio
import os
import sys

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../..")))

from infra.db_client import DBClient
from core.analysis.analyzer import Analyzer
import logging

logging.basicConfig(level=logging.INFO)

async def main():
    db_client = DBClient()
    analyzer = Analyzer(db_client)
    
    project_path = "tests/manual/generic_linking/src"
    print(f"Analyzing project: {project_path}")

    # Read files manually
    files_data = []
    for root, dirs, files in os.walk(project_path):
        for file in files:
            if file.endswith(".java"):
                full_path = os.path.join(root, file)
                with open(full_path, "rb") as f:
                    content = f.read()
                files_data.append({"path": full_path, "content": content})
    
    # Analyze
    if files_data:
        analyzer.process_files_from_memory(files_data, project="temp_test_project")
        print(f"Analysis complete. Processed {len(files_data)} files.")
    else:
        print("No Java files found.")
        
    db_client.close()

if __name__ == "__main__":
    asyncio.run(main())
