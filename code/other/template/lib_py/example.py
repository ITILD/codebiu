"""演示demo包的示例脚本。"""

from src.lib_py import demo_function, DemoClass


def main():
    """主函数，用于演示包的使用。"""
    print("测试演示函数:")
    result = demo_function("世界")
    print(f"  结果: {result}")
    
    print("\n测试演示类:")
    demo_instance = DemoClass("示例")
    result = demo_instance.greet()
    print(f"  结果: {result}")
    
    print("\n所有演示已成功完成！")


if __name__ == "__main__":
    main()