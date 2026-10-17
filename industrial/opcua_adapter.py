"""Bounded OPC UA transactions. No automatic reconnect or write retry."""
import asyncio
import base64
import math
import os
import re
import struct
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit
from asyncua import Client, ua
from asyncua.crypto.security_policies import SecurityPolicyBasic256Sha256
from asyncua.crypto.validator import CertificateValidator, CertificateValidatorOptions

INTEGER_BITS = {'SByte': (8, True), 'Byte': (8, False), 'Int16': (16, True), 'UInt16': (16, False), 'Int32': (32, True), 'UInt32': (32, False), 'Int64': (64, True), 'UInt64': (64, False)}
WRITE_TYPES = set(INTEGER_BITS) | {'Boolean', 'Float', 'Double', 'String', 'DateTime', 'Guid', 'ByteString'}
MAX_ITEMS = 1000

def typed_value(value, name):
    if name not in WRITE_TYPES:
        raise ValueError('不支持的 OPC UA 写入类型')
    if isinstance(value, list):
        if len(value) > MAX_ITEMS or any(isinstance(v, list) for v in value):
            raise ValueError('写入仅支持一维数组，最多 1000 项')
        return [typed_value(v, name) for v in value]
    if name in INTEGER_BITS:
        bits, signed = INTEGER_BITS[name]
        if bits == 64 and isinstance(value, str) and re.fullmatch(r'-?[0-9]+', value):
            value = int(value)
        elif type(value) is not int or abs(value) > 9007199254740991:
            raise ValueError('整数值无效；64 位大整数请使用十进制文本')
        lower, upper = (-(2**(bits-1)), 2**(bits-1)-1) if signed else (0, 2**bits-1)
        if not lower <= value <= upper:
            raise ValueError('整数超出 '+name+' 范围')
    elif name == 'Boolean':
        if type(value) is not bool:
            raise ValueError('Boolean 必须使用开关值')
    elif name in ('Float', 'Double'):
        if type(value) not in (float, int) or not math.isfinite(value):
            raise ValueError('浮点值必须为有限数值')
        value = float(value)
        if name == 'Float':
            try:
                value = struct.unpack('<f', struct.pack('<f', value))[0]
            except (OverflowError, struct.error) as error:
                raise ValueError('数值超出 Float 范围') from error
            if not math.isfinite(value):
                raise ValueError('数值超出 Float 范围')
    elif name == 'String':
        if not isinstance(value, str) or len(value) > 16384:
            raise ValueError('String 需要文本，最多 16384 字符')
    elif name == 'DateTime':
        if not isinstance(value, str):
            raise ValueError('DateTime 需要带时区的日期时间文本')
        value = datetime.fromisoformat(value.replace('Z', '+00:00'))
        if value.tzinfo is None:
            raise ValueError('日期时间必须包含时区')
        value = value.astimezone(timezone.utc)
    elif name == 'Guid':
        value = uuid.UUID(str(value))
    elif name == 'ByteString':
        if not isinstance(value, str) or len(value) > 22000:
            raise ValueError('ByteString 需要 Base64 文本，最多 16 KB')
        value = base64.b64decode(value, validate=True)
        if len(value) > 16384:
            raise ValueError('ByteString 超过 16 KB')
    return value

def encode_value(value, data_type, depth=0):
    if depth > 8:
        raise ValueError('节点值嵌套过深')
    if isinstance(value, (list, tuple)):
        if len(value) > MAX_ITEMS:
            raise ValueError('节点数组超过 1000 项')
        return [encode_value(v, data_type, depth+1) for v in value]
    if value is None:
        return None
    if data_type in ('Int64', 'UInt64'):
        return str(value)  # JS number cannot represent every 64-bit integer.
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).isoformat()
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, bytes):
        return base64.b64encode(value).decode('ascii')
    if type(value) in (bool, int, str):
        return value
    if type(value) is float and math.isfinite(value):
        return value
    raise ValueError('节点值包含尚不支持的类型或非有限数值：'+data_type)

def validate(operation, params):
    if operation not in ('opcua_read', 'opcua_write', 'opcua_browse', 'opcua_wait'):
        raise ValueError('未知 OPC UA 操作')
    endpoint = params.get('endpoint', '')
    if not isinstance(endpoint, str) or len(endpoint) > 500 or any(c.isspace() for c in endpoint):
        raise ValueError('OPC UA 端点地址无效')
    url = urlsplit(endpoint)
    if url.scheme != 'opc.tcp' or not url.hostname or not url.port or url.username or url.password or url.query or url.fragment:
        raise ValueError('端点须为 opc.tcp://主机:端口/路径，认证请使用独立字段')
    timeout = params.get('timeoutMs', 3000)
    if type(timeout) is not int or not 100 <= timeout <= 10000:
        raise ValueError('通信超时必须为 100–10000 ms')
    node_text = params.get('nodeId', 'i=85' if operation == 'opcua_browse' else '')
    if not isinstance(node_text, str) or len(node_text) > 500:
        raise ValueError('节点地址无效')
    try:
        node_id = ua.NodeId.from_string(node_text)
    except Exception as error:
        raise ValueError('节点地址格式无效，例如 ns=2;s=SIEANS.Count') from error
    uri = params.get('namespaceUri', '')
    if not isinstance(uri, str) or len(uri) > 500:
        raise ValueError('命名空间 URI 无效')
    policy = params.get('security', 'None')
    if policy not in ('None', 'Basic256Sha256'):
        raise ValueError('不支持的安全策略')
    if params.get('password') is not None:
        raise ValueError('密码不能保存在工程参数，请配置密码环境变量名')
    if policy == 'None' and (params.get('username') or params.get('passwordEnv')):
        raise ValueError('用户名认证需要 Basic256Sha256 加密连接')
    if policy != 'None':
        for key in ('clientCertificate', 'privateKey', 'serverCertificate'):
            if not isinstance(params.get(key), str) or not Path(params[key]).is_file():
                raise ValueError('服务器上的证书或密钥文件不存在：'+key)
        app_uri = params.get('applicationUri', 'urn:sieans:vision:client')
        if not isinstance(app_uri, str) or not app_uri or len(app_uri) > 500:
            raise ValueError('客户端应用 URI 无效')
    username = params.get('username', '')
    if not isinstance(username, str) or len(username) > 256:
        raise ValueError('用户名无效')
    secret = None
    if username:
        env = params.get('passwordEnv', '')
        if not isinstance(env, str) or not re.fullmatch(r'SIEANS_OPCUA_[A-Za-z0-9_]{1,100}', env) or not os.environ.get(env):
            raise ValueError('密码环境变量需以 SIEANS_OPCUA_ 开头，且已在服务器配置非空值')
        secret = os.environ[env]
    if type(params.get('requireGood', True)) is not bool:
        raise ValueError('数据质量检查必须使用开关值')
    limit = params.get('browseLimit', 100)
    if type(limit) is not int or not 1 <= limit <= 500:
        raise ValueError('浏览上限必须为 1–500')
    typed = typed_value(params.get('value'), params.get('dataType', 'Double')) if operation == 'opcua_write' else None
    return endpoint, timeout, node_id, secret, typed

async def browse(client, node_id, limit):
    description = ua.BrowseDescription(NodeId=node_id, BrowseDirection=ua.BrowseDirection.Forward,
        ReferenceTypeId=ua.NodeId(ua.ObjectIds.HierarchicalReferences), IncludeSubtypes=True,
        NodeClassMask=0, ResultMask=ua.BrowseResultMask.All)
    params = ua.BrowseParameters(RequestedMaxReferencesPerNode=limit, NodesToBrowse=[description])
    response = (await client.uaclient.browse(params))[0]
    refs = []
    continuation = None
    try:
        while True:
            response.StatusCode.check()
            refs.extend(response.References or [])
            continuation = response.ContinuationPoint
            if not continuation or len(refs) >= limit:
                break
            response = (await client.uaclient.browse_next(ua.BrowseNextParameters(ReleaseContinuationPoints=False, ContinuationPoints=[continuation])))[0]
        namespaces = await client.get_namespace_array()
        items = [{'nodeId':r.NodeId.to_string(), 'displayName':r.DisplayName.Text or r.BrowseName.Name,
                  'browseName':r.BrowseName.Name, 'nodeClass':r.NodeClass.name,
                  'namespaceUri':namespaces[r.NodeId.NamespaceIndex] if r.NodeId.NamespaceIndex < len(namespaces) else '',
                  'remote':bool(getattr(r.NodeId,'ServerIndex',0) or getattr(r.NodeId,'NamespaceUri',None))} for r in refs[:limit]]
        return {'items':items, 'count':len(items), 'truncated':bool(continuation) or len(refs)>limit}
    finally:
        if continuation:
            await client.uaclient.browse_next(ua.BrowseNextParameters(ReleaseContinuationPoints=True, ContinuationPoints=[continuation]))

async def run_async(operation, params):
    endpoint, timeout, node_id, secret, typed = validate(operation, params)
    waiting=operation=='opcua_wait'
    if waiting:
        from opcua_wait import validate as validate_wait
        validate_wait(params)
    started = time.perf_counter()
    wait_deadline=time.monotonic()+params.get('waitTimeoutMs',10000)/1000 if waiting else None
    client = Client(endpoint, timeout=timeout/1000, auto_reconnect=False)
    client.application_uri = params.get('applicationUri', 'urn:sieans:vision:client')
    write_sent = False
    result = {'protocol':'opc-ua', 'action':operation.removeprefix('opcua_')}
    try:
        async with asyncio.timeout((params.get('waitTimeoutMs',10000)+timeout*2)/1000 if waiting else timeout/1000):
            if params.get('security', 'None') == 'Basic256Sha256':
                await client.set_security(SecurityPolicyBasic256Sha256, params['clientCertificate'], params['privateKey'],
                    server_certificate=params['serverCertificate'], mode=ua.MessageSecurityMode.SignAndEncrypt)
                client.certificate_validator = CertificateValidator(CertificateValidatorOptions.TIME_RANGE | CertificateValidatorOptions.URI | CertificateValidatorOptions.PEER_SERVER).validate
            if secret is not None:
                client.set_user(params['username'])
                client.set_password(secret)
            await asyncio.wait_for(client.connect(),timeout/1000)
            if params.get('namespaceUri'):
                node_id.NamespaceIndex = await client.get_namespace_index(params['namespaceUri'])
            node = client.get_node(node_id)
            result['nodeId'] = node_id.to_string()
            if operation == 'opcua_wait':
                from opcua_wait import wait_for_value
                result.update(await wait_for_value(client,node,params,wait_deadline))
            elif operation == 'opcua_browse':
                result.update(await browse(client, node_id, params.get('browseLimit',100)))
            elif operation == 'opcua_read':
                data = await node.read_data_value(raise_on_bad_status=False)
                code = data.StatusCode
                result.update(status=code.name, statusCode=code.value, quality='good' if code.is_good() else 'bad' if code.is_bad() else 'uncertain',
                    sourceTimestamp=data.SourceTimestamp.isoformat() if data.SourceTimestamp else None,
                    serverTimestamp=data.ServerTimestamp.isoformat() if data.ServerTimestamp else None)
                if params.get('requireGood', True) and not code.is_good():
                    raise ValueError('节点数据质量不合格：'+code.name)
                variant = data.Value
                name = variant.VariantType.name if variant else 'Null'
                value = encode_value(variant.Value, name) if variant else None
                result.update(dataType=name, value=value, isArray=bool(variant and variant.is_array), dimensions=variant.Dimensions if variant else None)
                result['items'] = [{'index':i,'value':v} for i,v in enumerate(value)] if isinstance(value,list) else [{'value':value}]
            else:
                name = params.get('dataType','Double')
                value = ua.DataValue(ua.Variant(typed, getattr(ua.VariantType, name), is_array=isinstance(typed,list)))
                write_sent = True
                await node.write_value(value)
                result.update(dataType=name, value=encode_value(typed,name), acknowledged=True, status='Good', quality='good',
                    note='服务端已确认写入；不代表物理动作完成，流程停止或失败不会撤销设备写入。')
                if name == 'Float':
                    result['requestedValue'] = params['value']
    except Exception as error:
        if isinstance(error, TimeoutError):
            message = 'OPC UA 操作超时'
        elif isinstance(error, (ValueError, ua.UaStatusCodeError)):
            message = str(error)
        else:
            message = 'OPC UA 连接或协议错误：'+type(error).__name__
        if write_sent:
            message += '；写请求可能已到达设备，未自动重试，请读取设备状态确认'
        raise ValueError(message) from error
    finally:
        try:
            await asyncio.wait_for(client.disconnect(), timeout=.5)
        except Exception:
            client.disconnect_socket()
    result['timestamp'] = datetime.now(timezone.utc).isoformat()
    return {'operation':operation, 'result':result, 'elapsedMs':round((time.perf_counter()-started)*1000,1)}

def run(operation, params):
    return asyncio.run(run_async(operation, params))
