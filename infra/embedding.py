import os
import logging
from openai import OpenAI
from typing import List, Optional

logger = logging.getLogger(__name__)

class EmbeddingService:
    """
    OpenAI API를 사용하여 텍스트의 임베딩 벡터를 생성하는 서비스입니다.
    현재 비용 절감을 위해 기본적으로 비활성화되어 있습니다.
    """
    def __init__(self):
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            logger.warning("OPENAI_API_KEY not found in environment variables. Embedding service disabled.")
            self.client = None
        else:
            self.client = OpenAI(api_key=api_key)

    def get_embedding(self, text: str) -> Optional[List[float]]:
        """
        주어진 텍스트의 임베딩을 반환합니다.
        현재는 None을 반환하도록 설정되어 있습니다. (필요 시 주석 해제)
        """
        # 임베딩 비용 절감을 위해 비활성화
        return None
