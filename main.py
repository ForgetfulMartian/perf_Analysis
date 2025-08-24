import dearpygui.dearpygui as dpg
import multiprocessing as mp
import asyncio
import os
import sys

# Add src to the path so we can import our modules
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), 'src')))

from src.acquisition.live_hub_controller import LiveHubController
from src.utils.file_manager import create_session_paths
import pandas as pd

# --- Backend Process ---
def run_backend(to_ui_q, from_ui_q, session_path_q):
    print("[DEBUG] Backend process started.")
    controller = LiveHubController(to_ui_q, from_ui_q, session_path_q)
    
    try:
        asyncio.run(controller.run())
    except asyncio.CancelledError:
        print("[DEBUG] Backend process cancelled.")
    except Exception as e:
        print(f"[ERROR] An error occurred in the backend: {e}")

# --- UI Setup and Loop ---
def run_ui(to_ui_q, from_ui_q, session_path_q):
    print("[DEBUG] UI process started.")
    dpg.create_context()
    dpg.create_viewport(title='Live Hub Dashboard', width=800, height=600)
    
    with dpg.theme() as red_theme:
        with dpg.theme_component(dpg.mvAll):
            dpg.add_theme_color(dpg.mvThemeCol_Text, [255, 0, 0])
    with dpg.theme() as green_theme:
        with dpg.theme_component(dpg.mvAll):
            dpg.add_theme_color(dpg.mvThemeCol_Text, [0, 255, 0])
    with dpg.theme() as yellow_theme:
        with dpg.theme_component(dpg.mvAll):
            dpg.add_theme_color(dpg.mvThemeCol_Text, [255, 255, 0])

    hr_data = []
    
    def connect_device_callback():
        subject_id = dpg.get_value("subject_id_input")
        if subject_id:
            session_path = create_session_paths(subject_id)
            session_path_q.put(session_path)
            from_ui_q.put({'command': 'connect_and_start', 'subject_id': subject_id})
            dpg.disable_item("connect_button")
            dpg.enable_item("stop_button")
            dpg.disable_item("subject_id_input")

    def stop_session_callback():
        from_ui_q.put({'command': 'stop'})
        dpg.enable_item("connect_button")
        dpg.disable_item("stop_button")
        dpg.enable_item("subject_id_input")
        dpg.set_value("hr_series", [[], []])
        hr_data.clear()

    def load_file_callback(sender, app_data):
        file_path = app_data['file_path_name']
        from_ui_q.put({'command': 'load_file', 'file_path': file_path})

    main_window_tag = "live_hub_main_window"
    with dpg.window(label="Live Hub Dashboard", tag=main_window_tag, width=800, height=600):
        with dpg.group(horizontal=True):
            dpg.add_text("Device Status")
            dpg.add_text("Backend: ", tag="backend_status_label")
            dpg.add_text("Stopped", tag="backend_status")
            dpg.bind_item_theme("backend_status", red_theme)
        
        with dpg.group(horizontal=True):
            dpg.add_text("Polar H10: ")
            dpg.add_text("Disconnected", tag="polar_status")
            dpg.bind_item_theme("polar_status", red_theme)

        dpg.add_separator()
        dpg.add_text("Data Collection")
        dpg.add_button(label="Connect to Polar H10", tag="connect_button", callback=connect_device_callback)
        dpg.add_button(label="Stop Session", tag="stop_button", callback=stop_session_callback, enabled=False)
        dpg.add_separator()
        
        dpg.add_input_text(label="Subject ID", tag="subject_id_input", default_value="SUBJ001")
        
        with dpg.file_dialog(directory_selector=False, show=False, callback=load_file_callback, tag="file_dialog_tag"):
            dpg.add_file_extension(".parquet", color=(255, 255, 0, 255))
        dpg.add_button(label="Load Parquet File", callback=lambda: dpg.show_item("file_dialog_tag"))
        
        dpg.add_separator()
        dpg.add_text("Data Visualization")
        with dpg.plot(label="Heart Rate (BPM)", height=250, width=-1):
            dpg.add_plot_legend()
            dpg.add_plot_axis(dpg.mvXAxis, label="Time (s)", tag="x_axis_hr")
            dpg.add_plot_axis(dpg.mvYAxis, label="HR (BPM)", tag="y_axis_hr")
            dpg.set_axis_limits("y_axis_hr", 60, 120)
            dpg.add_line_series([], [], label="HR", parent="y_axis_hr", tag="hr_series")

    def update_ui_loop(sender, app_data, user_data):
        while not to_ui_q.empty():
            data = to_ui_q.get()
            print(f"[DEBUG] UI received: {data}")
            
            if data.get('type') == 'status':
                device = data.get('device')
                status = data.get('status')
                if device == 'polar':
                    if status == 'connected':
                        dpg.set_value("polar_status", "Connected")
                        dpg.bind_item_theme("polar_status", green_theme)
                    elif status == 'scanning':
                        dpg.set_value("polar_status", "Scanning...")
                        dpg.bind_item_theme("polar_status", yellow_theme)
                    else:
                        dpg.set_value("polar_status", "Disconnected")
                        dpg.bind_item_theme("polar_status", red_theme)
                elif data.get('backend'):
                    if data['backend'] == 'connecting':
                        dpg.set_value("backend_status", "Connecting...")
                        dpg.bind_item_theme("backend_status", yellow_theme)
                    elif data['backend'] == 'starting':
                        dpg.set_value("backend_status", "Running")
                        dpg.bind_item_theme("backend_status", green_theme)
                    else:
                        dpg.set_value("backend_status", "Stopped")
                        dpg.bind_item_theme("backend_status", red_theme)
            
            elif data.get('type') == 'hr_data':
                hr_data.clear() # Clear any old data
                hr_data.extend(data['hr_data'])
                
                x_data = list(range(len(hr_data)))
                dpg.set_value("hr_series", [x_data, hr_data])
                dpg.set_axis_limits("x_axis_hr", 0, len(hr_data))
                dpg.fit_axis_data("y_axis_hr")
                print(f"[DEBUG] Plot updated with {len(hr_data)} data points.")
        
        dpg.set_frame_callback(dpg.get_frame_count() + 1, update_ui_loop)
    
    dpg.set_primary_window(main_window_tag, True)
    dpg.setup_dearpygui()
    dpg.show_viewport()
    
    dpg.set_frame_callback(0, update_ui_loop)
    
    dpg.start_dearpygui()
    dpg.destroy_context()
    
    from_ui_q.put({'command': 'exit'})

if __name__ == '__main__':
    mp.set_start_method('spawn', force=True)

    to_ui_q = mp.Queue()
    from_ui_q = mp.Queue()
    session_path_q = mp.Queue()

    backend_process = mp.Process(target=run_backend, args=(to_ui_q, from_ui_q, session_path_q))
    backend_process.start()

    run_ui(to_ui_q, from_ui_q, session_path_q)
    
    backend_process.join()