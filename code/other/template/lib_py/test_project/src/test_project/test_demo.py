"""演示包的测试模块。"""

from lib_py import demo_function, DemoClass


def test_demo_function():
    """测试演示函数。"""
    result = demo_function("世界")
    print(f"函数结果: {result}")
    assert result == "你好，世界！这是一个演示函数。"


def test_demo_class():
    """测试演示类。"""
    demo_instance = DemoClass("测试")
    result = demo_instance.greet()
    print(f"类结果: {result}")
    assert result == "来自DemoClass的问候，测试！"


if __name__ == "__main__":
    print("测试演示函数...")
    test_demo_function()
    
    print("测试演示类...")
    test_demo_class()
    
    print("所有测试通过！")