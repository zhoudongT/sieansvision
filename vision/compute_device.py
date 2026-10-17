"""Explicit CPU/CUDA selection shared by inference and training."""
import re

def device_info():
    import torch
    items=[dict(id='cpu',name='CPU',available=True)]
    reason='当前 PyTorch 为 CPU 版本' if torch.version.cuda is None else '未检测到可用 CUDA 显卡或驱动'
    if torch.cuda.is_available():
        try:
            for index in range(torch.cuda.device_count()):
                p=torch.cuda.get_device_properties(index)
                items.append(dict(id=f'cuda:{index}',name=p.name,available=True,memoryMB=round(p.total_memory/1024**2),capability=f'{p.major}.{p.minor}'))
            reason='CUDA 可用'
        except Exception as exc:reason='CUDA 初始化失败：'+str(exc)
    return dict(torchVersion=torch.__version__,cudaVersion=torch.version.cuda,devices=items,cudaAvailable=len(items)>1,reason=reason)

def select_device(value='cpu',backend='pt'):
    if not isinstance(value,str) or not (value in ('cpu','auto') or re.fullmatch(r'cuda:\d{1,2}',value)):
        raise ValueError('计算设备请选择 cpu、auto 或 cuda:显卡编号')
    info=device_info();available={item['id']:item for item in info['devices']}
    requested=value;reason='按配置选择 CPU' if value=='cpu' else '按配置选择 CUDA 显卡'
    if value=='auto':
        value=next((key for key in available if key!='cpu'),'cpu')
        reason='自动选择可用 CUDA 显卡' if value!='cpu' else '自动使用 CPU：'+info['reason']
    if value not in available:raise ValueError('指定的 GPU 不可用：'+requested+'；'+info['reason'])
    if backend=='onnx' and value!='cpu':
        try:
            import onnxruntime
            supported='CUDAExecutionProvider' in onnxruntime.get_available_providers()
        except ImportError:supported=False
        if not supported:
            if requested!='auto':raise ValueError('当前 ONNX 环境没有 CUDAExecutionProvider，请安装兼容的 onnxruntime-gpu 或选择 CPU')
            value='cpu';reason='自动使用 CPU：当前 ONNX 环境没有 CUDAExecutionProvider'
    return dict(device=value,requestedDevice=requested,deviceName=available[value]['name'],deviceReason=reason)

def predict(model,image,selection,**options):
    import torch
    try:
        result=model.predict(image,device=selection['device'],**options)[0]
    except torch.cuda.OutOfMemoryError as exc:
        torch.cuda.empty_cache()
        raise ValueError('GPU 显存不足，请减小图像尺寸、批量或目标上限；未切换到 CPU') from exc
    actual=str(model.predictor.model.device)
    if selection['device'].startswith('cuda'):
        session=getattr(model.predictor.model,'session',None)
        if actual!=selection['device'] or session is not None and 'CUDAExecutionProvider' not in session.get_providers():
            raise ValueError('推理引擎没有在指定 GPU 上运行，请检查 CUDA/ONNX 驱动依赖')
    elif actual!='cpu':raise ValueError('推理引擎实际设备与 CPU 配置不一致')
    return result
