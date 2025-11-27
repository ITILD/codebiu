import polars as pl
from datetime import datetime
from pathlib import Path
import os


class ExcelService:
    """Excel文件处理服务类"""

    def __init__(self):
        pass

    async def read_and_analyze(self, file_path: str) -> dict:
        """
        读取并分析Excel文件
        
        Args:
            file_path: Excel文件路径
            
        Returns:
            包含分析结果的字典
        """
        try:
            # 直接使用polars读取Excel文件
            df = pl.read_excel(file_path, sheet_id=1)
            
            # 基本信息分析
            analysis_result = {
                "shape": df.shape,  # (行数, 列数)
                "columns": df.columns,
                "data_types": {col: str(dtype) for col, dtype in zip(df.columns, df.dtypes)},
                "null_counts": df.null_count().to_dict(as_series=False),
                "sample_data": df.head().to_dict(as_series=False)
            }
            
            # 数值列的统计信息
            numeric_columns = df.select(pl.col(pl.NUMERIC_DTYPES)).columns
            if numeric_columns:
                stats = df.select([
                    pl.col(numeric_columns).mean().name.suffix("_mean"),
                    pl.col(numeric_columns).median().name.suffix("_median"),
                    pl.col(numeric_columns).std().name.suffix("_std"),
                    pl.col(numeric_columns).min().name.suffix("_min"),
                    pl.col(numeric_columns).max().name.suffix("_max")
                ])
                analysis_result["numeric_stats"] = stats.to_dict(as_series=False)
            
            return analysis_result
            
        except Exception as e:
            raise Exception(f"读取或分析Excel文件时出错: {str(e)}")

    async def save_analysis_result(self, file_path: str, output_dir: str = None) -> str:
        """
        读取Excel文件，进行分析并将结果保存到同级目录下，文件名加上时间戳
        
        Args:
            file_path: Excel文件路径
            output_dir: 输出目录，默认为与输入文件相同的目录
            
        Returns:
            保存的分析结果文件路径
        """
        try:
            # 如果没有指定输出目录，则使用与输入文件相同的目录
            if output_dir is None:
                output_dir = os.path.dirname(file_path)
            
            # 确保输出目录存在
            Path(output_dir).mkdir(parents=True, exist_ok=True)
            
            # 读取并分析Excel文件
            analysis_result = await self.read_and_analyze(file_path)
            
            # 生成带时间戳的新文件名
            base_name = os.path.splitext(os.path.basename(file_path))[0]
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_filename = f"{base_name}_analysis_{timestamp}.xlsx"
            output_path = os.path.join(output_dir, output_filename)
            
            # 准备适合保存到Excel的数据格式
            # 将复杂的数据结构转换为字符串表示形式
            simplified_result = {}
            for key, value in analysis_result.items():
                if isinstance(value, dict):
                    # 将字典转换为格式化的JSON字符串
                    simplified_result[key] = [str(value)]
                elif isinstance(value, (list, tuple)):
                    # 将列表或元组转换为字符串
                    simplified_result[key] = [str(value)]
                else:
                    # 保持其他类型的值不变，但确保是列表形式
                    simplified_result[key] = [str(value)]
            
            # 保存分析结果到excel文件
            df = pl.DataFrame(simplified_result)
            df.write_excel(output_path)
            
            return output_path
            
        except Exception as e:
            raise Exception(f"保存分析结果时出错: {str(e)}")


if __name__ == "__main__":
    import asyncio
    from common.config.path import DIR_UPLOAD
    async def main():
        # 示例用法
        service = ExcelService()
        
        
        # 注意：这里需要一个真实的Excel文件路径进行测试
        test_file_path = DIR_UPLOAD / 'test.xlsx'
        result_path = await service.save_analysis_result(test_file_path)
        print(f"分析结果已保存到: {result_path}")
        pass
        
    asyncio.run(main())