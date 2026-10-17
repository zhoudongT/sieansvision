# SIEANS 检测扩展示例 1.0.0

两个可独立加载的 Python 算子：

- 图像亮度检测：OpenCV 灰度均值/标准差与上下限判定。使用项目已有 cv2 / numpy。
- 点云质心偏差：采样点算术平均坐标及到目标的距离，沿用输入点云单位。只使用 Python 标准库。

复制本目录制作新插件时修改清单中的 id、name、version 和算子。主程序无需改动，工具箱和表单从清单生成。入口需要定义 run(ctx)，结果必须符合 outputs 字段表。

完整开发、安装和测试说明见项目 docs/operator-plugins.md。源码按本目录 MIT LICENSE 提供；OpenCV/Numpy 分别遵循其原有许可证。
