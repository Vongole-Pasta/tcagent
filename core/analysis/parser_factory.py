from tree_sitter_languages import get_language, get_parser
import logging

logger = logging.getLogger(__name__)

class ParserFactory:
    @staticmethod
    def get_parser(extension: str):
        lang_name = ParserFactory._get_language_name(extension)
        if not lang_name:
            raise ValueError(f"Unsupported extension: {extension}")
        try:
            return get_parser(lang_name)
        except Exception as e:
            logger.error(f"Failed to get parser for {lang_name}: {e}")
            raise

    @staticmethod
    def get_language(extension: str):
        lang_name = ParserFactory._get_language_name(extension)
        if not lang_name:
            raise ValueError(f"Unsupported extension: {extension}")
        try:
            return get_language(lang_name)
        except Exception as e:
            logger.error(f"Failed to get language for {lang_name}: {e}")
            raise

    @staticmethod
    def _get_language_name(extension: str):
        if extension == ".java":
            return "java"
        return None
