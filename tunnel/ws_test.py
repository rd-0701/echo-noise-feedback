"""WebSocket 端到端验证（公网 URL）。"""
import asyncio
import json
import sys
import websockets

URL = "wss://band-coaching-charles-national.trycloudflare.com/ws?token=fk8_gViRMN_H12ctG_mGRQ2JY0gMng1w"


async def main():
    print(f"Connecting to {URL} ...")
    try:
        async with websockets.connect(URL, open_timeout=20) as ws:
            print("[OK] WS connected")
            # 等 3 秒看是否有推送消息
            received = []
            try:
                for _ in range(3):
                    msg = await asyncio.wait_for(ws.recv(), timeout=2.0)
                    received.append(msg)
            except asyncio.TimeoutError:
                pass
            if received:
                print(f"[OK] Received {len(received)} messages:")
                for m in received[:3]:
                    preview = m if len(m) <= 200 else m[:200] + "..."
                    print(f"  - {preview}")
            else:
                print("[WARN] No pushed messages in 6s (acceptable if quiet)")
            # 发送 ping
            await ws.send(json.dumps({"cmd": "ping"}))
            try:
                pong = await asyncio.wait_for(ws.recv(), timeout=3.0)
                print(f"[OK] Ping -> {pong}")
            except asyncio.TimeoutError:
                print("[FAIL] No pong received")
    except Exception as e:
        print(f"[FAIL] {type(e).__name__}: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
