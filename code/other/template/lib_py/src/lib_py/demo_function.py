"""演示函数模块。"""


def demo_function(name: str) -> str:
    """简单的演示函数，用于问候某人。
    
    Args:
        name: 要问候的人的姓名
        
    Returns:
        问候消息
    """
    return f"你好，{name}！这是一个演示函数。"


if __name__ == "__main__":
    # 使用示例
    result = demo_function("世界")
    print(result)