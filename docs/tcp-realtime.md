# CommManager 真 TCP（wave155–wave156）

与既有 **LocalBus 软路径**并存：设计态 Soft 收发/自动应答不变；选 **TCP 真套接字** 时走真实 bind/listen/connect。

## wave156 加深
- **分帧**：LF / CRLF / raw / **Len4**（4 字节大端长度前缀 + UTF-8 body）软选项
- **Keep-Alive**：`SO_KEEPALIVE`；Client **断线重连**（reconnectMs / reconnectMax）
- **Session pool**：loopback 服务端可入池复用（`pooled_loopback_session`）
- **Transcript filter**：方向 TX|RX|SYS|ERR + 包含文本
- **Persist**：`project.commManager.tcpReal` 持久化 host/port/framing/keepAlive
- TCP 页包在 `QScrollArea(commTcpScroll)`，小分辨率可滚动

冒烟：`python3 scripts/smoke-wave156-tcp-camera-adapt-e2e.py`

## 能力

| 项 | 说明 |
|---|---|
| 传输路径 | Soft / LocalBus（默认）或 TCP |
| Server | 可配置 `host:port` listen（`port=0` 临时端口） |
| Client | connect + 发送；可 oneshot 或长连接 |
| 分帧 | LF / CRLF / raw / **Len4**（wave156） |
| 自动应答 | Server 收到一帧后回 `ack`（默认 `OK`） |
| 抄本 | UI「真套接字抄本」记录 LISTEN/ACCEPT/TX/RX |
| Keep-Alive / 重连 | SO_KEEPALIVE；Client reconnect（wave156） |
| Session pool | loopback 服务端可复用（wave156） |
| `${}` | 发送载荷支持 `expand_payload`（flow.* / 短名） |

实现：`desktop/tcp_realtime.py`；UI：`desktop/comm_manager.py` TCP 测试页「实时 TCP」组。
环回模拟器 `tcp_device_sim.py`（:19880）仍可用；真 TCP 默认演示口 **:19955**（可改）。

## 验证

```bash
python3 scripts/smoke-wave155-real-tcp-e2e.py
```

环回 listen→connect→send→recv→ack，**无外部 PLC**。现场设备验收仍待下一阶段。

勿动调试口 `:18280` 与未跟踪 `os`。App 默认 `:19777`。
