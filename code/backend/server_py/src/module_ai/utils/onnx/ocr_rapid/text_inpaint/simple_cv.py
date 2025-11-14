from cv2 import UMat
import numpy as np
import cv2 as cv


# 给出图片和遮罩boxs数组，将图片中boxs对应区域进行填充
def mask_from_boxs(img, boxs):
    inpaintMask = np.zeros(img.shape[:2], np.uint8)
    for box in boxs:
        p1, p2, p3, p4 = box
        # np 数组内 四边形内数值置为255
        x0 = int(min( p1[0], p4[0] ))
        y0 = int(min( p1[1], p2[1] ))
        x1 = int(max( p2[0], p3[0] ))
        y1 = int(max( p3[1], p4[1] ))
        inpaintMask[y0:y1, x0:x1] = 255
    return inpaintMask


def simple_inpaint(img, boxs) -> UMat:
    inpaintMask = mask_from_boxs(img, boxs)
    res = cv.inpaint(
        src=img, inpaintMask=inpaintMask, inpaintRadius=3, flags=cv.INPAINT_NS
    )
    return res





if __name__ == "__main__":
    # test
    def main():
        img = cv.imread("test.png")
        boxs = [[0, 0, 100, 100]]
        inpaintMask = mask_from_boxs(img, boxs)
        res = simple_inpaint(img, boxs)
        cv.imshow("Inpaint Output using NS Technique", res)
    main()
    cv.waitKey(0)
    cv.destroyAllWindows()
