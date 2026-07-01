from fastapi import Depends
from module_authorization.service.casbin_rule import CasbinRuleService
from module_authorization.dao.casbin_rule import CasbinRuleDao

async def get_casbin_rule_dao():
    return CasbinRuleDao()
    
    
async def get_casbin_rule_service(
    dao: CasbinRuleDao = Depends(get_casbin_rule_dao)
):
    """Service工厂"""
    return CasbinRuleService(dao)