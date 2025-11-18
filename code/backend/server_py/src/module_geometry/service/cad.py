from ezdxf.math import bbox
from ezdxf.addons import odafc
from common.config.cad import DIR_CAD_APP
from dao.cad import FeatureDao

odafc.win_exec_path = DIR_CAD_APP

class CadService:
    def __init__(self, cad_dao: CadDao):
        self.cad_dao = cad_dao or CadDao()

    async def bbox(self, dwg: ezdxf.document.Drawing) -> list[float]:
        return bbox(dwg)
    async def convert(self, dwg: ezdxf.document.Drawing) -> None:
            # 1 读取dwg文件
        doc = odafc.readfile(os.path.join(path_cad, 'test_feicui','Drawing1.dwg')) # dwg文件名或者路径)
        # 2 转换保存 DXF 文件留档
        # doc.saveas(os.path.join(path_cad, 'test_feicui','Drawing1.dxf'))

        # 3 DXF内图形转换geojson
        feature_collection = dxf_to_geojson(doc)
        # TODO 性能生产消费者 每读100条分线程处理下一步
        # print(feature_collection)

        # 4 存入空间数据库
        # 初始化数据库表
        await TableService.create()
        # # new User
        # user = User(name='test', email='test11111@qq.com')
        # await UserDao.insert(user)
        
        # 每个文件一个uuid 
        uuid_pwg =uuid.uuid4()
        
        #test单条数据插入
        await FeatureDao.insert(Feature(
                pid = uuid_pwg,
                geometry=functions.ST_GeomFromGeoJSON(str(feature_collection.features[0].geometry)),
                properties=feature_collection.features[0].properties),
            )