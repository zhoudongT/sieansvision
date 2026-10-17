"""Configurable grayscale sampling quality, not a scene-independent focus score."""
import base64
import cv2
import numpy as np


def run(ctx):
    p = ctx['params']
    image = cv2.imdecode(np.frombuffer(base64.b64decode(ctx['image'].split(',', 1)[-1]), np.uint8), cv2.IMREAD_GRAYSCALE)
    if image is None:
        raise ValueError('无法解码输入图像')
    height, width = image.shape
    x, y = p['roiX'], p['roiY']
    w, h = p['roiWidth'] or width-x, p['roiHeight'] or height-y
    if x < 0 or y < 0 or w < 3 or h < 3 or x+w > width or y+h > height:
        raise ValueError('检测区域必须位于图像内且至少为 3×3 像素')
    if p['darkThreshold'] >= p['brightThreshold']:
        raise ValueError('过暗灰度阈值必须低于过曝灰度阈值')
    crop = image[y:y+h, x:x+w]
    # Exclude the outer ring so derivative boundary extrapolation cannot dominate the score.
    sharpness = float(cv2.Laplacian(crop, cv2.CV_64F, ksize=1)[1:-1, 1:-1].var())
    dark = float(np.count_nonzero(crop <= p['darkThreshold'])*100/crop.size)
    bright = float(np.count_nonzero(crop >= p['brightThreshold'])*100/crop.size)
    focus_ok, dark_ok, bright_ok = sharpness >= p['minimumSharpness'], dark <= p['maximumDarkPercent'], bright <= p['maximumBrightPercent']
    return dict(result=dict(sharpness=sharpness, meanIntensity=float(crop.mean()), darkPercent=dark,
                            brightPercent=bright, pixelCount=int(crop.size), focusPassed=focus_ok,
                            darkPassed=dark_ok, brightPassed=bright_ok, passed=focus_ok and dark_ok and bright_ok,
                            items=[dict(check='清晰度', measured=sharpness, limit=p['minimumSharpness'], rule='大于等于', passed=focus_ok),
                                   dict(check='过暗比例 (%)', measured=dark, limit=p['maximumDarkPercent'], rule='小于等于', passed=dark_ok),
                                   dict(check='过曝比例 (%)', measured=bright, limit=p['maximumBrightPercent'], rule='小于等于', passed=bright_ok)]))
