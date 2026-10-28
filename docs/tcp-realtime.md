# CommManager 真 TCP（wave155）

与既有 **LocalBus 软路径**并存：设计态 Soft 收发/自动应答不变；选 **TCP 真套接字** 时走真实 bind/listen/connect。

## 能力

| 项 | 说明 |
|---|---|
| 传输路径 | Soft / LocalBus（默认）或 TCP |
| Server | 可配置 `host:port` listen（`port=0` 临时端口） |
| Client | connect + 发送；可 oneshot 或长连接 |
| 分帧 | 默认 LF（`\n`）；可选 CRLF |
| 自动应答 | Server 收到一帧后回 `ack`（默认 `OK`） |
| 抄本 | UI「真套接字抄本」记录 LISTEN/ACCEPT/TX/RX |
| `${}` | 发送载荷支持 `expand_payload`（flow.* / 短名） |

实现：`desktop/tcp_realtime.py`；UI：`desktop/comm_manager.py` TCP 测试页「实时 TCP」组。
环回模拟器 `tcp_device_sim.py`（:19880）仍可用；真 TCP 默认演示口 **:19955**（可改）。

## 验证

```bash
python3 scripts/smoke-wave155-real-tcp-e2e.py
```

环回 listen→connect→send→recv→ack，**无外部 PLC**。现场设备验收仍待下一阶段。

勿动调试口 `:18280` 与未跟踪 `os`。App 默认 `:19777`。
