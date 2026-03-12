import asyncio
import websockets
import json

async def test():
    uri = "ws://127.0.0.1:18795/"
    try:
        async with websockets.connect(uri) as websocket:
            print("Connected")
            challenge_msg = await websocket.recv()
            print(f"Received: {challenge_msg}")
            challenge = json.loads(challenge_msg)
            if challenge.get("event") != "connect.challenge":
                print(f"Failed: Expected connect.challenge, got {challenge}")
                return
            
            nonc = challenge["payload"]["nonce"]
            print(f"Nonce: {nonc}")

            print("Sending connect req...")
            await websocket.send(json.dumps({
                "type": "req",
                "id": "test-1",
                "method": "connect",
                "params": {}
            }))
            
            resp_msg = await websocket.recv()
            print(f"Received: {resp_msg}")
            resp = json.loads(resp_msg)
            if resp.get("ok"):
                print("Handshake Success!")
            else:
                print("Handshake Failed")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(test())
