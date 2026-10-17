"""One bounded OPC UA data-change subscription, used inside an existing session."""
import asyncio
from collections import deque
from datetime import datetime, timezone
import math
import time


def validate(p):
    for key, default, low, high in [('waitTimeoutMs',10000,100,600000),('publishingIntervalMs',100,20,10000)]:
        value=p.get(key,default)
        if type(value) is not int or not low<=value<=high:raise ValueError(key+' 参数范围无效')
    if p.get('triggerMode','level') not in ('level','rising','falling'):raise ValueError('OPC UA 触发方式无效')
    if p.get('onTimeout','error') not in ('error','continue'):raise ValueError('OPC UA 超时处理无效')
    comparison=p.get('comparison','eq')
    if comparison not in ('eq','ne','gt','gte','lt','lte','is_true','is_false'):raise ValueError('OPC UA 信号条件无效')
    if comparison not in ('is_true','is_false'):
        value=p.get('expectedValue',0)
        if type(value) not in (int,float) or not math.isfinite(value) or abs(value)>1e15:raise ValueError('OPC UA 比较值必须为有限数值')


def condition(data,p):
    code=data.StatusCode
    if not code.is_good():raise ValueError('订阅节点数据质量不合格：'+code.name)
    if code.value&0x80:raise ValueError('OPC UA 服务端通知队列溢出，不能可靠判断边沿')
    variant=data.Value
    if variant is None or variant.is_array:raise ValueError('OPC UA 等待仅支持数值或开关标量')
    value=variant.Value
    comparison=p.get('comparison','eq')
    if comparison in ('is_true','is_false'):
        if type(value) is not bool:raise ValueError('开关条件需要 Boolean 节点')
        return value if comparison=='is_true' else not value, value
    if type(value) not in (int,float) or not math.isfinite(value) or abs(value)>9007199254740991:
        raise ValueError('数值条件需要安全数值范围内的标量；不转换文本或大整数')
    expected=p.get('expectedValue',0)
    return {'eq':lambda:value==expected,'ne':lambda:value!=expected,'gt':lambda:value>expected,'gte':lambda:value>=expected,'lt':lambda:value<expected,'lte':lambda:value<=expected}[comparison](),value


class Handler:
    def __init__(self):
        self.queue=asyncio.Queue(maxsize=100)
        self.fault=None

    def offer(self,value):
        if self.queue.full():self.fault=ValueError('OPC UA 客户端通知队列溢出，停止等待')
        else:self.queue.put_nowait(value)

    def datachange_notification(self,node,value,data):
        self.offer((time.monotonic(),data.monitored_item.Value))

    def status_change_notification(self,status):
        if not status.Status.is_good():
            self.fault=ValueError('OPC UA 订阅状态异常：'+status.Status.name)
            self.offer(None)


async def wait_for_value(client,node,p,deadline):
    validate(p)
    handler=Handler()
    subscription=None
    first=None
    previous=None
    mode=p.get('triggerMode','level')
    rows=deque(maxlen=100)
    count=0
    result=dict(triggered=False,passed=False,timedOut=False,notificationCount=0,items=[],detailsTruncated=False)
    try:
        remaining=deadline-time.monotonic()
        if remaining<=0:raise ValueError('等待时限内未能建立 OPC UA 订阅')
        async with asyncio.timeout(min(remaining,p.get('timeoutMs',3000)/1000)):
            subscription=await client.create_subscription(p.get('publishingIntervalMs',100),handler)
            await subscription.subscribe_data_change(node,queuesize=100,sampling_interval=p.get('publishingIntervalMs',100))
        try:
            async with asyncio.timeout_at(deadline):
                while True:
                    if handler.fault:raise handler.fault
                    try:notification=await asyncio.wait_for(handler.queue.get(),.2)
                    except TimeoutError:
                        await client.check_connection()
                        continue
                    if handler.fault:raise handler.fault
                    if notification is None:continue
                    received,data=notification
                    if time.monotonic()>=deadline or received>=deadline:raise TimeoutError()
                    current,value=condition(data,p)
                    count+=1
                    if count==1:first=value
                    rows.append(dict(index=count,value=value,condition=current,sourceTimestamp=data.SourceTimestamp.isoformat() if data.SourceTimestamp else None))
                    matched=current if mode=='level' else previous is False and current if mode=='rising' else previous is True and not current
                    previous=current
                    result.update(value=value,firstValue=first,condition=current,dataType=data.Value.VariantType.name,status=data.StatusCode.name,quality='good')
                    if matched:
                        result.update(triggered=True,passed=True)
                        break
        except TimeoutError:
            if not count:raise ValueError('OPC UA 订阅未收到有效初始数据，不能作为条件超时继续') from None
            if p.get('onTimeout','error')=='error':raise ValueError('等待 OPC UA 信号超时') from None
            # Confirm the session and quality before calling this a condition timeout.
            # A late read is never used as a trigger or substituted for notification data.
            condition(await node.read_data_value(raise_on_bad_status=False),p)
            result['timedOut']=True
            result['timeoutConnectionVerified']=True
        result.update(notificationCount=count,items=list(rows),detailsTruncated=count>100,triggerMode=mode,
                      requestedPublishingIntervalMs=p.get('publishingIntervalMs',100),timestamp=datetime.now(timezone.utc).isoformat())
        return result
    finally:
        if subscription is not None:
            try:await asyncio.wait_for(subscription.delete(),p.get('timeoutMs',3000)/1000)
            except Exception:pass  # The owner always disconnects the complete session afterwards.
