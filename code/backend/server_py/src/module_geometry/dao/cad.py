
from config.db import Data
from do.feature import Feature
from uuid import UUID

class FeatureDao:
    @Data
    def insert(feature:Feature,session=None):
            return session.add(feature)
        # 不需要显式调用 session.commit()，因为装饰器已经处理了
    @Data
    def insert_batch(features:[Feature],session=None):
            for feature in features:
                session.add(feature)
        
    @Data
    def select_by_id(id:UUID,session=None):
        # 快捷方式 id
        feature = session.get(Feature, id)
        print(feature)
        return feature
        