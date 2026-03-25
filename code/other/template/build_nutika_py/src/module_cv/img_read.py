# 制作棋盘测试图 https://calib.io/zh/pages/camera-calibration-pattern-generator
import cv2

def detect_black_squares(image_path: str, output_path: str | None = None,test_out_dir: str = None) -> None:
    """检测图片中的黑色方块并用红色矩形框标记
    
    Args:
        image_path: 输入图片路径
        output_path: 输出图片路径，如果为 None 则显示图片
    """
    # 读取图片
    image = cv2.imread(image_path)
    if image is None:
        raise FileNotFoundError(f"无法读取图片: {image_path}")
    
    # 转换为灰度图
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    
    # 二值化处理，检测所有非白色区域（阈值设为200）
    # 灰度值<220的区域（黑色、灰色等）设为白色(255)，白色区域设为黑色(0)
    _, binary = cv2.threshold(gray, 220, 255, cv2.THRESH_BINARY_INV)
    # 输出中间图像
    cv2.imwrite(f"{test_out_dir}/1.二值化处理.png", binary)
    
    # 使用形态学操作分离相连的黑色方块（现在是白色区域）
    # 先腐蚀2次，再膨胀，去除小噪点并分离相连区域
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    binary = cv2.erode(binary, kernel, iterations=2)
    # 输出中间图像
    cv2.imwrite(f"{test_out_dir}/2.腐蚀.png", binary)
    
    # 再膨胀
    binary = cv2.dilate(binary, kernel, iterations=1)
    # 输出中间图像
    cv2.imwrite(f"{test_out_dir}/3.膨胀.png", binary)   
    
    # 查找轮廓
    contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    # 遍历所有轮廓
    for contour in contours:
        # 计算轮廓面积，过滤掉太小的噪点
        area = cv2.contourArea(contour)
        if area < 10:
            continue
        
        # 获取轮廓的边界矩形
        x, y, w, h = cv2.boundingRect(contour)
        
        # 用红色矩形框标记黑色方块
        cv2.rectangle(image, (x, y), (x + w, y + h), (0, 0, 255), 2)
    
    # 输出结果
    if output_path:
        cv2.imwrite(output_path, image)
        print(f"结果已保存到: {output_path}")
    else:
        cv2.imshow("检测结果", image)
        cv2.waitKey(0)
        cv2.destroyAllWindows()


if __name__ == "__main__":
    # 获取年月日小时分钟秒
    import datetime
    now = datetime.datetime.now()
    timestamp = now.strftime("%Y%m%d%H%M%S")
    # 测试输出目录
    test_out_dir = "temp_source/test"
    # 确保目录存在
    import os
    os.makedirs(test_out_dir, exist_ok=True)
    
    detect_black_squares(
        "public/img/test_bw_3_5.png",
        f"{test_out_dir}/test_bw_3_5_detected_{timestamp}.png",
        test_out_dir
    )