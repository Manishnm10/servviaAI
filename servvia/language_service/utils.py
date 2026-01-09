import logging

from database.database_config import db_conn
from database. db_operations import get_record_by_field
from database.models import Language
from django_core. config import Config

logger = logging. getLogger(__name__)


def get_language_by_code(language_code, with_db_config=Config. WITH_DB_CONFIG):
    """Get language details by code"""
    language = None
    
    # Fallback dictionary
    languages = {
        'en': {'code': 'en', 'name': 'English', 'bcp_code':  'en-US'},
        'kn': {'code': 'kn', 'name':  'Kannada', 'bcp_code': 'kn-IN'},
        'hi': {'code': 'hi', 'name': 'Hindi', 'bcp_code': 'hi-IN'},
        'ta': {'code': 'ta', 'name': 'Tamil', 'bcp_code':  'ta-IN'},
        'te': {'code': 'te', 'name': 'Telugu', 'bcp_code': 'te-IN'},
        'ml': {'code': 'ml', 'name': 'Malayalam', 'bcp_code': 'ml-IN'},
        'bn': {'code':  'bn', 'name':  'Bengali', 'bcp_code': 'bn-IN'},
        'mr': {'code': 'mr', 'name': 'Marathi', 'bcp_code': 'mr-IN'},
    }
    
    if with_db_config:
        try:
            with db_conn:
                language_query = Language.select(
                    (Language.id).alias("language_id"),
                    Language.name,
                    Language. code,
                    Language.bcp_code,
                ).where(Language.is_deleted == False, Language.code == language_code)

                if language_query. count() >= 1:
                    language = list(language_query.dicts().execute())[0]
        except Exception as error:
            logger.warning(f"Language by code {language_code} does not exist in DB")
    
    # Fallback to dictionary if not in DB
    if not language:
        language = languages. get(language_code, languages['en'])
    
    return language


def get_all_languages(with_db_config=Config.WITH_DB_CONFIG) -> list:
    """Query the list of all active languages."""
    language_list = []
    if with_db_config: 
        try:
            with db_conn:
                language_query = Language.select(
                    (Language.id).alias("language_id"),
                    (Language. name).alias("language_name"),
                    (Language.display_name).alias("language_display_name"),
                    (Language. code).alias("language_code"),
                    (Language.latn_code).alias("language_latn_code"),
                    (Language.bcp_code).alias("language_bcp_code"),
                ).where(Language.is_deleted == False)

                if language_query.count() >= 1:
                    language_list = list(language_query. dicts().execute())
        except Exception as error:
            logger.error(error, exc_info=True)

    return language_list


def get_language_by_id(language_id, with_db_config=Config.WITH_DB_CONFIG):
    """Query a specific language by the given language ID."""
    language = {}
    if with_db_config:
        try:
            with db_conn:
                language_query = Language.select(
                    (Language.id).alias("language_id"),
                    Language.name,
                    Language.display_name,
                    Language.code,
                    Language.latn_code,
                    Language.bcp_code,
                ).where(Language.is_deleted == False, Language.id == language_id)

                if language_query. count() >= 1:
                    language = list(language_query.dicts().execute())[0]
        except Exception as error: 
            logger.error(error, exc_info=True)

    return language