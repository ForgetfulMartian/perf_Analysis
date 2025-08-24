import dearpygui.dearpygui as dpg
import pandas as pd
import os
import numpy as np
import ast

def run_csv_visualiser():
    """Runs the Dear PyGui application for viewing CSV files."""
    dpg.create_context()
    dpg.create_viewport(title='CSV Heart Metrics Visualiser', width=900, height=1000)

    # --- Themes for visualization ---
    with dpg.theme() as default_theme:
        with dpg.theme_component(dpg.mvAll):
            dpg.add_theme_color(dpg.mvThemeCol_PlotLines, (0, 150, 255, 255))
            dpg.add_theme_style(dpg.mvPlotStyleVar_PlotPadding, 20, 20)
            dpg.add_theme_style(dpg.mvPlotStyleVar_PlotBorderSize, 0)
            dpg.add_theme_style(dpg.mvPlotStyleVar_LegendPadding, 20, 20)
    
    # --- Data storage for plotting ---
    hr_data_to_plot = []
    rr_data_to_plot = []
    
    def calculate_hrv_metrics(rr_intervals):
        """Calculates basic time-domain HRV metrics."""
        if len(rr_intervals) < 2:
            return {'rmssd': np.nan}
        rr_diffs = np.diff(rr_intervals)
        rmssd = np.sqrt(np.mean(rr_diffs**2))
        return {'rmssd': rmssd}

    def filter_rr_intervals(rr_intervals, min_ms=300, max_ms=2000):
        """Removes physiologically impossible RR intervals."""
        return [rr for rr in rr_intervals if min_ms < rr < max_ms]

    # --- Callbacks ---
    def file_selected_callback(sender, app_data):
        file_path = app_data['file_path_name']
        print(f"[DEBUG] Selected file: {file_path}")
        
        if not file_path or not os.path.exists(file_path):
            print("[ERROR] Invalid file path selected.")
            dpg.set_value("status_text", "Error: Invalid file selected.")
            return

        try:
            # Tell pandas to read the file with the default python engine which is more forgiving
            df = pd.read_csv(file_path, engine='python')
            
            if 'hr_bpm' not in df.columns or 'rr_ms_list' not in df.columns:
                print("[ERROR] Required columns not found in the CSV file.")
                dpg.set_value("status_text", "Error: 'hr_bpm' or 'rr_ms_list' column not found.")
                return

            # Now, safely evaluate the string representation of the lists
            df['rr_ms_list'] = df['rr_ms_list'].apply(ast.literal_eval)

            # --- Update HR plot data ---
            current_hr_data = df['hr_bpm'].tolist()
            hr_data_to_plot.clear()
            hr_data_to_plot.extend(current_hr_data)

            x_data_hr = list(range(len(hr_data_to_plot)))
            dpg.set_value("hr_series_plot", [x_data_hr, hr_data_to_plot])
            
            if hr_data_to_plot:
                dpg.set_axis_limits("x_axis_hr_plot", 0, len(hr_data_to_plot))
                dpg.fit_axis_data("y_axis_hr_plot")

            # --- Update RR plot data ---
            rr_intervals_flat = [interval for sublist in df['rr_ms_list'].tolist() for interval in sublist]
            
            # Filter the RR data for accurate RMSSD calculation
            filtered_rr_intervals = filter_rr_intervals(rr_intervals_flat)
            
            rr_data_to_plot.clear()
            rr_data_to_plot.extend(rr_intervals_flat)

            x_data_rr = list(range(len(rr_data_to_plot)))
            dpg.set_value("rr_series_plot", [x_data_rr, rr_data_to_plot])

            if rr_data_to_plot:
                dpg.set_axis_limits("x_axis_rr_plot", 0, len(rr_data_to_plot))
                dpg.fit_axis_data("y_axis_rr_plot")
            
            # --- Calculate and display metrics ---
            if filtered_rr_intervals:
                metrics = calculate_hrv_metrics(filtered_rr_intervals)
                dpg.set_value("rmssd_metric", f"RMSSD: {metrics['rmssd']:.2f} ms")
            else:
                dpg.set_value("rmssd_metric", "RMSSD: Not enough valid data.")
            
            dpg.set_value("avg_hr_metric", f"Average HR: {np.mean(current_hr_data):.2f} BPM")
            dpg.set_value("status_text", f"Successfully loaded {len(hr_data_to_plot)} HR data points from: {os.path.basename(file_path)}")
            print(f"[DEBUG] Plot and metrics updated with {len(hr_data_to_plot)} data points.")

        except Exception as e:
            print(f"[ERROR] Failed to load or process CSV file: {e}")
            dpg.set_value("status_text", f"Error loading file: {e}")

    # --- File Dialog setup ---
    with dpg.file_dialog(
        directory_selector=False, 
        show=False, 
        callback=file_selected_callback, 
        tag="file_dialog_tag",
        width=700, height=400
    ):
        dpg.add_file_extension(".csv", color=(255, 255, 0, 255))
        dpg.add_file_extension(".*")

    # --- Main Window Layout ---
    main_window_tag = "csv_viewer_main_window"
    with dpg.window(label="CSV Heart Metrics Visualiser", tag=main_window_tag, width=900, height=1000):
        dpg.add_text("Select a CSV file to visualize Heart Metrics.")
        dpg.add_button(label="Browse for CSV File", callback=lambda: dpg.show_item("file_dialog_tag"))
        
        dpg.add_separator()

        with dpg.plot(label="Heart Rate (BPM) Over Time", height=300, width=-1):
            dpg.add_plot_legend()
            dpg.add_plot_axis(dpg.mvXAxis, label="Sample Index", tag="x_axis_hr_plot")
            dpg.add_plot_axis(dpg.mvYAxis, label="HR (BPM)", tag="y_axis_hr_plot")
            dpg.set_axis_limits("y_axis_hr_plot", 60, 180)
            dpg.add_line_series([], [], label="Heart Rate", parent="y_axis_hr_plot", tag="hr_series_plot")
        
        dpg.add_separator()
        
        with dpg.plot(label="RR Intervals (ms) Over Time", height=300, width=-1):
            dpg.add_plot_legend()
            dpg.add_plot_axis(dpg.mvXAxis, label="Sample Index", tag="x_axis_rr_plot")
            dpg.add_plot_axis(dpg.mvYAxis, label="RR Interval (ms)", tag="y_axis_rr_plot")
            dpg.add_line_series([], [], label="RR Interval", parent="y_axis_rr_plot", tag="rr_series_plot")
        
        dpg.add_separator()
        
        dpg.add_text("Heart Metrics", color=(255, 255, 0, 255))
        with dpg.group(horizontal=True):
            dpg.add_text("Average HR: N/A", tag="avg_hr_metric")
            dpg.add_text("  |  ")
            dpg.add_text("RMSSD: N/A", tag="rmssd_metric")
        
        dpg.add_separator()
        dpg.add_text("Status: Ready", tag="status_text", color=(0, 200, 0, 255))
    
    dpg.set_primary_window(main_window_tag, True)
    dpg.setup_dearpygui()
    dpg.show_viewport()
    dpg.start_dearpygui()
    dpg.destroy_context()

if __name__ == '__main__':
    run_csv_visualiser()