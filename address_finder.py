import asyncio
from bleak import BleakScanner

async def find_polar():
    print("Scanning for Polar H10...")
    devices = await BleakScanner.discover(timeout=5.0)
    for d in devices:
        if d.name and "Polar H10" in d.name:
            print(f"Found Polar H10: {d.name} ({d.address})")
            return d.address
    raise RuntimeError("No Polar H10 found nearby!")

if __name__ == "__main__":
    asyncio.run(find_polar())
