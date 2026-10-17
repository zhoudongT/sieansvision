"""OpenCV brightness statistics example; no proprietary camera dependency."""
import base64
import cv2
import numpy as np


def run(ctx):
    image = cv2.imdecode(np.frombuffer(base64.b64decode(ctx['image'].split(',', 1)[-1]), dtype=np.uint8), cv2.IMREAD_GRAYSCALE)
    if image is None:
        raise ValueError('无法解码输入图像')
    p = ctx['params']
    if p['minimumMean'] > p['maximumMean']:
        raise ValueError('最低平均亮度不能大于最高平均亮度')
    mean, deviation = cv2.meanStdDev(image)
    brightness = float(mean[0, 0])
    return dict(result=dict(meanIntensity=brightness, intensityDeviation=float(deviation[0, 0]),
                            pixelCount=int(image.size), passed=p['minimumMean'] <= brightness <= p['maximumMean']))
