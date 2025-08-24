import asyncio
import time
import struct
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from datetime import datetime
from bleak import BleakClient, BleakScanner, BleakError
import os

HR_CHARACTERISTIC_UUID = "00002a37-0000-1000-8000-00805f9b34fb"

class LiveHubController:
    def __init__(self, to_ui_q, from_ui_q, session_path_q):
        self.to_ui_q = to_ui_q
        self.from_ui_q = from_ui_q
        self.session_path_q = session_path_q

        self.client = None
        self.connected_address = None
        self.notification_queue = asyncio.Queue()
        self.session_active = False
        self.session_path = None
        self.data_log = []
        
        self.command_handler = {
            'connect_and_start': self.connect_and_start_session,
            'stop': self.stop_session,
            'exit': self.exit_handler,
            'load_file': self.load_file_and_send_to_ui
        }
        
    async def _find_polar_h10(self, device_name="Polar H10"):
        print(f"[DEBUG] Scanning for {device_name}...")
        devices = await BleakScanner.discover()
        for d in devices:
            if d.name and device_name in d.name:
                print(f"[DEBUG] Found {device_name} at address: {d.address}")
                return d.address
        print(f"[DEBUG] Could not find {device_name}.")
        return None

    def _parse_hr_data(self, data):
        flags = data[0]
        hr_bpm = data[1]
        
        rr_intervals = []
        if (flags & 0x10):
            rr_data_bytes = data[2:]
            rr_intervals_raw = struct.unpack('<' + 'H' * (len(rr_data_bytes) // 2), rr_data_bytes)
            rr_intervals = [int(interval / 1.024) for interval in rr_intervals_raw]
        return {"hr_bpm": hr_bpm, "rr_intervals_ms": rr_intervals}

    def _notification_handler(self, sender, data):
        asyncio.ensure_future(self.notification_queue.put(data))

    async def run(self):
        while True:
            try:
                if not self.from_ui_q.empty():
                    command = self.from_ui_q.get_nowait()
                    print(f"[DEBUG] Backend received command: {command}")
                    await self.command_handler.get(command['command'])(command)

                if self.client and self.client.is_connected:
                    data = await asyncio.wait_for(self.notification_queue.get(), timeout=0.1)
                    self._process_data(data)
                else:
                    await asyncio.sleep(0.1)
            except asyncio.CancelledError:
                print("[DEBUG] Controller task cancelled.")
                break
            except asyncio.TimeoutError:
                pass
            except Exception as e:
                print(f"[ERROR] An error occurred in the main loop: {e}")
                await self.disconnect_device()
                break

    async def connect_and_start_session(self, command):
        if self.client and self.client.is_connected and self.session_active:
            print("[WARNING] Already connected and session active.")
            return

        self.to_ui_q.put({'type': 'status', 'device': 'polar', 'status': 'scanning'})
        
        if not self.client or not self.client.is_connected:
            self.connected_address = await self._find_polar_h10()
            if not self.connected_address:
                self.to_ui_q.put({'type': 'status', 'device': 'polar', 'status': 'disconnected'})
                return
            
            try:
                self.client = BleakClient(self.connected_address)
                await self.client.connect()
                
                heart_rate_char = self.client.services.get_characteristic(HR_CHARACTERISTIC_UUID)
                if not heart_rate_char:
                    raise BleakError(f"Characteristic not found. Is the Polar H10 on your chest?")
                
                await self.client.start_notify(heart_rate_char, self._notification_handler)
                self.to_ui_q.put({'type': 'status', 'device': 'polar', 'status': 'connected'})
                print(f"[DEBUG] Successfully connected to {self.connected_address}")
            except Exception as e:
                print(f"[ERROR] Connection failed: {e}")
                self.to_ui_q.put({'type': 'status', 'device': 'polar', 'status': 'disconnected'})
                await self.disconnect_device()
                return

        self.session_active = True
        self.session_path = self.session_path_q.get()
        self.data_log = []
        self.to_ui_q.put({'type': 'status', 'backend': 'starting'})
        print(f"[DEBUG] Session started for subject {command['subject_id']}. Logging data.")


    async def stop_session(self, command=None):
        if not self.session_active:
            return
            
        self.session_active = False
        self.to_ui_q.put({'type': 'status', 'backend': 'stopped'})
        print("[DEBUG] Session stopped.")
        
        if self.data_log and self.session_path:
            print(f"[DEBUG] Saving {len(self.data_log)} data points...")
            df = pd.DataFrame(self.data_log)
            file_path = os.path.join(self.session_path, 'raw', 'polar_h10_raw.parquet')
            pq.write_table(pa.Table.from_pandas(df), file_path)
            print(f"[DEBUG] Data saved to {file_path}")
            self.data_log = []
            self.session_path = None
        
        await self.disconnect_device()

    async def disconnect_device(self, command=None):
        if self.client and self.client.is_connected:
            await self.client.stop_notify(HR_CHARACTERISTIC_UUID)
            await self.client.disconnect()
        self.client = None
        self.connected_address = None
        self.to_ui_q.put({'type': 'status', 'device': 'polar', 'status': 'disconnected'})
        print("[DEBUG] Disconnected from device.")

    async def exit_handler(self, command=None):
        await self.stop_session()
        await self.disconnect_device()

    async def load_file_and_send_to_ui(self, command):
        file_path = command['file_path']
        print(f"[DEBUG] Received request to load file: {file_path}")
        
        try:
            df = pd.read_parquet(file_path)
            hr_data = df['hr_bpm'].tolist()
            
            self.to_ui_q.put({
                'type': 'hr_data_loaded',
                'hr_data': hr_data,
                'message': f"Loaded {len(hr_data)} data points from {os.path.basename(file_path)}"
            })
            print(f"[DEBUG] Successfully loaded and sent {len(hr_data)} data points to UI.")
        except Exception as e:
            print(f"[ERROR] Failed to load Parquet file: {e}")
            self.to_ui_q.put({
                'type': 'status', 
                'device': 'polar',
                'status': 'error',
                'message': f"Error loading file: {e}"
            })
            
    def _process_data(self, data):
        # This method is no longer for real-time plotting but for data logging during a session.
        # It sends data to the UI but doesn't handle the plot.
        t_sys = time.perf_counter()
        t_utc = datetime.utcnow()
        parsed_data = self._parse_hr_data(data)
        
        if self.session_active:
            self.data_log.append({
                "t_sys": t_sys,
                "t_utc": t_utc.isoformat(),
                "hr_bpm": parsed_data["hr_bpm"],
                "rr_ms_list": parsed_data["rr_intervals_ms"],
                "raw_hex": data.hex()
            })
            print(f"[LOG] Logged HR: {parsed_data['hr_bpm']} (Session Active)")