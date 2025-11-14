from bs4 import BeautifulSoup
import zipfile

class DocxService:
    """docx"""

    def __init__(self):
        pass

    async def read(self, file_path_in: str, file_path_out: str) -> bytes:
        """读取docx文件"""
        with zipfile.ZipFile(file_path_in, 'r') as zip_ref:
            # 获取doc里的文字
            with zip_ref.open('word/document.xml') as doc_file:
                # soup = BeautifulSoup(doc_file, 'xml')
                soup = BeautifulSoup(doc_file, 'lxml')
                text = soup.get_text(separator='\n')
                print(text)
                
if __name__ == "__main__":
    from common.config.path import DIR_UPLOAD
    import asyncio
    async def main():
        docx_service = DocxService()
        await docx_service.read(DIR_UPLOAD / 'test.docx', 'test_out')
    asyncio.run(main())
        
        
        
