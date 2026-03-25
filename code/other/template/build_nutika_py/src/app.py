from module_cv.img_read import detect_black_squares


def main():
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
        "public/img/test_bw_3_51.png",
        f"{test_out_dir}/test_bw_3_5_detected_{timestamp}.png",
        test_out_dir
    )


if __name__ == "__main__":
    main()
