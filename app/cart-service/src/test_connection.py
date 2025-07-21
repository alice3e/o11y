import httpx
import asyncio

async def test():
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get('http://order-service:8002/')
            print(f"Status code: {response.status_code}")
            print(f"Response: {response.text}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(test()) 