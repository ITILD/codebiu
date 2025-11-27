from dao.cad import FeatureDao

def get_feature_dao() -> FeatureDao:
    return FeatureDao()
def get_cad_service(Depends) -> CadService:
    return CadService()
