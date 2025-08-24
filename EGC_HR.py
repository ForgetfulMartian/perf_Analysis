import asyncio
import struct
import time
import numpy as np
import pandas as pd
from scipy.signal import find_peaks
from bleak import BleakClient, BleakScanner

# UUIDs
ECG_UUID = "FB005C04-02E7-F387-1CAD-8ACD2D8DF0C8"
HR_UUID  = "00002A37-0000-1000-8000-00805f9b34fb"

# Buffers
ecg_data = []       
polar_hr_data = []  
computed_hr_data = []  

# ECG processing parameters
ECG_FS = 130  # Hz sampling rate
WINDOW_SEC = 10  # compute HR from last 10s of ECG

async def find_polar():
    """Scan and return the address of the first Polar H10 found."""
    print("🔍 Scanning for Polar H10...")
    devices = await BleakScanner.discover(timeout=5.0)
    for d in devices:
        if d.name and "Polar H10" in d.name:
            print(f"✅ Found Polar H10: {d.name} ({d.address})")
            return d.address
    raise RuntimeError("No Polar H10 found nearby!")

def ecg_handler(sender, data: bytearray):
    """Handle incoming ECG packets."""
    timestamp = time.time()
    for i in range(3, len(data), 2):
        sample = struct.unpack_from("<h", data, i)[0]
        ecg_data.append((timestamp, sample))

def hr_handler(sender, data: bytearray):
    """Handle incoming HR packets (standard BLE HR characteristic)."""
    timestamp = time.time()
    flags = data[0]
    hr_format = flags & 0x01  
    if hr_format == 0:
        hr = data[1]
    else:
        hr = struct.unpack_from("<H", data, 1)[0]
    polar_hr_data.append((timestamp, hr))

def compute_hr_from_ecg():
    """Compute HR from ECG using simple R-peak detection."""
    if len(ecg_data) < ECG_FS * WINDOW_SEC:
        return None
    recent = ecg_data[-ECG_FS*WINDOW_SEC:]
    signal = np.array([s for _, s in recent])
    threshold = np.mean(signal) + 0.5*np.std(signal)
    peaks, _ = find_peaks(signal, distance=ECG_FS//2, height=threshold)
    if len(peaks) < 2:
        return None
    rr_intervals = np.diff(peaks) / ECG_FS
    hr = 60.0 / np.mean(rr_intervals)
    timestamp = recent[-1][0]
    computed_hr_data.append((timestamp, hr))
    return hr

async def run_client():
    # Auto-discover Polar H10
    address = await find_polar()
    async with BleakClient(address) as client:
        print("🔗 Connected to Polar H10")

        await client.start_notify(ECG_UUID, ecg_handler)
        await client.start_notify(HR_UUID, hr_handler)

        print("📡 Streaming... Press Ctrl+C to stop.")
        try:
            while True:
                hr_ecg = compute_hr_from_ecg()
                if hr_ecg:
                    print(f"Computed HR (from ECG): {hr_ecg:.1f} bpm")
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            print("\nStopping stream...")

        await client.stop_notify(ECG_UUID)
        await client.stop_notify(HR_UUID)

def save_data():
    """Save all collected data to CSVs."""
    df_ecg = pd.DataFrame(ecg_data, columns=["timestamp", "ecg_uV"])
    df_hr = pd.DataFrame(polar_hr_data, columns=["timestamp", "polar_hr_bpm"])
    df_computed = pd.DataFrame(computed_hr_data, columns=["timestamp", "ecg_hr_bpm"])

    df_ecg.to_csv("polar_ecg.csv", index=False)
    df_hr.to_csv("polar_hr.csv", index=False)
    df_computed.to_csv("polar_ecg_hr.csv", index=False)

    # Merge HR streams for comparison
    if not df_hr.empty and not df_computed.empty:
        df_hr_combined = pd.merge_asof(
            df_hr.sort_values("timestamp"),
            df_computed.sort_values("timestamp"),
            on="timestamp",
            direction="nearest",
            tolerance=1
        )
        df_hr_combined.to_csv("polar_hr_comparison.csv", index=False)
        print("Saved combined HR -> polar_hr_comparison.csv")

    print("Saved:")
    print("- Raw ECG -> polar_ecg.csv")
    print("- Polar HR -> polar_hr.csv")
    print("- Computed HR -> polar_ecg_hr.csv")

if __name__ == "__main__":
    try:
        asyncio.run(run_client())
    finally:
        save_data()
