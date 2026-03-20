from fastapi import Depends
from module_nlp.dao.synonym import SynonymGroupDao, SynonymDao
from module_nlp.service.synonym import SynonymGroupService, SynonymService


async def get_synonym_group_dao() -> SynonymGroupDao:
    """同义词组DAO工厂"""
    return SynonymGroupDao()


async def get_synonym_dao() -> SynonymDao:
    """同义词DAO工厂"""
    return SynonymDao()


async def get_synonym_group_service(
    dao: SynonymGroupDao = Depends(get_synonym_group_dao)
) -> SynonymGroupService:
    """同义词组Service工厂"""
    return SynonymGroupService(dao)


async def get_synonym_service(
    dao: SynonymDao = Depends(get_synonym_dao)
) -> SynonymService:
    """同义词Service工厂"""
    return SynonymService(dao)