"""演示类模块。"""


class DemoClass:
    """简单的演示类。"""
    
    def __init__(self, name: str):
        """初始化演示类。
        
        Args:
            name: 此演示实例的名称
        """
        self.name = name
    
    def greet(self) -> str:
        """生成问候消息。
        
        Returns:
            问候消息
        """
        return f"来自DemoClass的问候，{self.name}！"
    
    def __str__(self) -> str:
        """对象的字符串表示。
        
        Returns:
            字符串表示
        """
        return f"DemoClass(name='{self.name}')"


if __name__ == "__main__":
    # 使用示例
    demo = DemoClass("示例")
    print(demo.greet())