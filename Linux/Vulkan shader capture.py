import os
import sys
import time
import shutil
import subprocess
import tkinter as tk
import customtkinter as ctk
from zipfile import ZipFile
from datetime import datetime
from pynput.keyboard import Key, Controller
from tkinter import filedialog, messagebox, BooleanVar, Checkbutton
sys.setrecursionlimit(2000) #Surpass Python's default recursion limit


# Configuration waiting to be pasted
retroarch_path = # executable path
core_dir = # core directory
info_dir = # info for core directory
shader_dir = # glsl or slang shader directory
default_shader_dir = shader_dir # to count the number of shaders used
retroarch_cfg_path = # Custom cfg path
log_dir = # directory to store log of actions
savestate_dir = # save state directory
screenshot_dir = # screenshot directory
bios_dir = # bios in system directory
shader_extensions = ('.slangp',)  # Corresponds with the driver selected tuple
shader_results = # file path for finalize_shaders zip file
network_cmd_port = 55355  # Default network command port for RetroArch

selected_core = None
selected_rom = None
selected_bios = None  # To keep track of the selected BIOS file
selected_save_state = None
last_shader = None  # To keep track of the last shader used
crashed_shaders = []
failed_shaders = []
crash_count = 0
pause_flag = False  # Flag to check if the process should be paused
temp_shader_list = []  # Global variable to persist the temporary shader list
shaders_list = []  # Global variable to persist the shader list
keyboard = Controller()  # Initialize the keyboard controller
shader_checkbuttons = {}
initial_run = True  # Global variable to track if it's the initial run


bios_extensions = (
    '.dat', '.A1200', '.wad', '.jar', '.szx', '.gg', '.rom', '.lo', '.boot.rom', '.img', '.pk3', '.xml', '.db', '.FNT',
    '.zim', '.ROM', '.program.rom', '.wav', '.pce', '.SHA', '.data.rom', '.sms', '.min', '.ic1', '.sfc', '.A600', '.bmp',
    '.zip', '.A500', '.bin', '.x1t', '.x1', '.4.rom'
)

def adjust_text_to_fit(label):
    """ Adjust text size or wrap text to fit within the label's width. """
    text = label.cget("text")
    font = label.cget("font")
    max_width = label.winfo_width()

    wrapped_text = wrap_text_to_fit(text, font, max_width)
    label.configure(text=wrapped_text)

def apply_shader(process, shader, index, total_shaders):
    global initial_run
    try:
        if initial_run:
            time.sleep(1.30)
            take_screenshot(shader)
            time.sleep(2.20)
            rename_last_screenshot(shader, initial=True)
            initial_run = False  # Set initial_run to False after the first run

        command = f"SET_SHADER {shader}\n"
        process.stdin.write(command.encode())
        process.stdin.flush()
        remaining_shaders = total_shaders - index + 1
        print(f"{remaining_shaders} shaders remaining. Applying shader: {shader}")
        update_status(f"{remaining_shaders} shaders remaining...", color="green", font=("Nimbus Mono PS", 25, 'normal'))
        for i in range(3):
            time.sleep(2)
            if check_shader_log(shader):
                shader_name = os.path.basename(shader)
                return True
        shader_name = os.path.basename(shader)
        update_status(f"Shader failed to load: {shader_name}", color="red", font=("Nimbus Mono PS", 25, 'normal'))
        return False
    except Exception as e:
        print(f"Failed to apply shader: {shader}, Error: {e}")
        return False

def create_temp_shader_list():
    global temp_shader_list
    temp_shader_list = []
    for shader, var in shader_checkboxes.items():
        if var.get():
            temp_shader_list.append(os.path.join(shader_dir, shader))
    return temp_shader_list

def cycle_shaders(process, slot_number, crashed_shaders):
    global pause_flag, last_shader, failed_shaders
    global shaders_list  # Use global variable to persist the shader list

    shaders_count = len(shaders_list)
    if shaders_count == 0:
        finalize_process(shaders_list, crashed_shaders)
        return

    progress_step = 100 / shaders_count
    current_progress = 0
    for index, shader in enumerate(shaders_list, start=1):
        while pause_flag:
            time.sleep(1.5)
        last_shader = shader
        if not apply_shader(process, shader, index, shaders_count):
            failed_shaders.append(shader)
            handle_crash(slot_number, shader, crashed_shaders)
            return  # Exit the function to handle crash and restart
        take_screenshot(shader)

        # Check RetroArch status before reloading save state
        for _ in range(3):
            time.sleep(3)  # Check status three times within 10 seconds
            status = get_status()
            if status and "PLAYING" in status:
                break
        else:
            failed_shaders.append(shader)
            handle_crash(slot_number, shader, crashed_shaders)
            return  # Exit the function to handle crash and restart

        time.sleep(3)  # Wait 3 seconds before reloading the save state
        reload_save_state(process, slot_number)
        current_progress += progress_step

        # Check if all shaders have been applied
        if index == shaders_count:
            finalize_process(shaders_list, crashed_shaders)
            return

def get_screen_resolution():
    """ Get the screen resolution of the current desktop. """
    try:
        result = subprocess.run(['xdpyinfo'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        for line in result.stdout.splitlines():
            if 'dimensions:' in line:
                return line.split()[1]
    except Exception as e:
        print(f"Failed to get screen resolution: {e}")
    return "Unknown"

def find_files(directory, extensions):
    """ Recursively find files with specified extensions in a directory. """
    files = []
    for root, _, filenames in os.walk(directory):
        for file in filenames:
            if file.endswith(extensions):
                files.append(os.path.join(root, file))
    return files

def find_shaders(directory, extensions):
    shaders = []
    for root, _, files in os.walk(directory):
        for file in files:
            if file.endswith(extensions):
                shaders.append(os.path.join(root, file))
    return shaders

def take_screenshot(shader_name):
    """ Send a network command to RetroArch to take a screenshot. """
    try:
        subprocess.run(
            f'echo -n "SCREENSHOT" | nc -u -w1 127.0.0.1 {network_cmd_port}',
            shell=True,
            check=True
        )
        print("Screenshot taken.")
        time.sleep(0.30)
        rename_last_screenshot(shader_name)
        time.sleep(1.23)
    except subprocess.CalledProcessError as e:
        print(f"Failed to take screenshot: {e}")

def rename_last_screenshot(shader_name, initial=False):
    try:
        files = sorted([os.path.join(screenshot_dir, f) for f in os.listdir(screenshot_dir)], key=os.path.getmtime)
        if files:
            last_screenshot = files[-1]
            shader_folder = os.path.basename(os.path.dirname(shader_name))
            base_name = os.path.splitext(os.path.basename(shader_name))[0]
            if initial or base_name == "stock":
                new_name = os.path.join(screenshot_dir, f"0 - stock.png")
            else:
                new_name = os.path.join(screenshot_dir, f"{shader_folder}-{base_name}.png")
            os.rename(last_screenshot, new_name)
            time.sleep(0.12)
            print(f"Renamed screenshot to {new_name}.")
            time.sleep(1.23)
    except Exception as e:
        print(f"Failed to rename screenshot: {e}")

def reload_save_state(process, slot_number):
    """ Reload the save state in RetroArch. """
    try:
        command_load_state = f"LOAD_STATE_SLOT {slot_number}\n"
        print(f"Reloading save state with command: {command_load_state}")
        process.stdin.write(command_load_state.encode())
        time.sleep(2)
        process.stdin.flush()
    except Exception as e:
        print(f"Failed to reload save state: {e}")

def modify_retroarch_cfg():
    """ Modify the RetroArch configuration file to enable necessary settings. """
    with open(retroarch_cfg_path, 'r') as file:
        lines = file.readlines()

    with open(retroarch_cfg_path, 'w') as file:
        for line in lines:
            if line.startswith('stdin_cmd_enable'):
                file.write('stdin_cmd_enable = "true"\n')
            elif line.startswith('network_cmd_enable'):
                file.write('network_cmd_enable = "true"\n')
            elif line.startswith('notification_show_screenshot_duration'):
                file.write('notification_show_screenshot_duration = "1"\n')
            elif line.startswith('video_driver'):
                file.write('video_driver = "vulkan"\n')
            elif line.startswith('video_shader_enable'):
                file.write('video_shader_enable = "true"\n')
            elif line.startswith('video_shared_context'):
                file.write('video_shared_context = "true"\n')
            elif line.startswith('video_fullscreen'):
                file.write('video_fullscreen = "true"\n')
            elif line.startswith('log_verbosity'):
                file.write('log_verbosity = "true"\n')
            elif line.startswith('log_to_file'):
                file.write('log_to_file = "true"\n')
            elif line.startswith('core_info_savestate_bypass'):
                file.write('core_info_savestate_bypass = "true"\n')
            elif line.startswith('log_to_file_timestamp'):
                file.write('log_to_file_timestamp = "true"\n')
            elif line.startswith('pause_nonactive'):
                file.write('pause_nonactive = "false"\n')
            elif line.startswith('audio_enable'):
                file.write('audio_enable = "false"\n')
            elif line.startswith('log_dir'):
                file.write(f'log_dir = "{log_dir}"\n')
            elif line.startswith('system_directory'):
                file.write(f'system_directory = "{bios_dir}"\n')
            elif line.startswith('screenshot_directory'):
                file.write(f'screenshot_directory = "{screenshot_dir}"\n')
            elif line.startswith('video_scale_integer'):
                file.write('video_scale_integer = "true"\n')
            else:
                file.write(line)

def get_core_display_name(core_path):
    """ Get the display name of the core from its .info file. """
    info_path = os.path.join(info_dir, os.path.basename(core_path).replace('.so', '.info'))
    if os.path.exists(info_path):
        with open(info_path, 'r') as info_file:
            for line in info_file:
                if line.startswith('display_name'):
                    return line.split('=')[1].strip().strip('"')
    return os.path.basename(core_path)

def get_core_corename(core_path):
    """ Get the core name from its .info file. """
    info_path = os.path.join(info_dir, os.path.basename(core_path).replace('.so', '.info'))
    if os.path.exists(info_path):
        with open(info_path, 'r') as info_file:
            for line in info_file:
                if line.startswith('corename'):
                    return line.split('=')[1].strip().strip('"')
    return None

def load_core():
    global selected_core
    core = filedialog.askopenfilename(title="Select Core", filetypes=[("Core Files", "*.so")], initialdir=core_dir)
    if core:
        selected_core = core
        core_label.configure(text=f"Selected Core: {get_core_display_name(core)}", text_color="red", font=('Nimbus Mono PS', 25, 'bold'))
        adjust_text_to_fit(core_label)

def load_rom():
    global selected_rom
    rom = filedialog.askopenfilename(title="Select ROM File")
    if rom:
        selected_rom = rom
        rom_label.configure(text=f"Selected ROM: {os.path.basename(rom)}", text_color="red", font=('Nimbus Mono PS', 25, 'bold'))
        adjust_text_to_fit(rom_label)

def load_bios():
    global selected_bios
    bios = filedialog.askopenfilename(title="Select BIOS File", filetypes=[("BIOS Files", bios_extensions)], initialdir=bios_dir)
    if bios:
        selected_bios = bios
        bios_label.configure(text=f"Selected BIOS: {os.path.basename(bios)}", text_color="red", font=('Nimbus Mono PS', 25, 'bold'))
        adjust_text_to_fit(bios_label)

def load_save_state():
    global selected_save_state
    save_state = filedialog.askopenfilename(title="Select Save State File", filetypes=[("Save State Files", "*.state*")])
    if save_state:
        selected_save_state = save_state
        save_state_label.configure(text=f"Selected Save State: {os.path.basename(save_state)}", text_color="red", font=('Nimbus Mono PS', 25, 'bold'))
        adjust_text_to_fit(save_state_label)

def check_shader_log(shader):
    """ Check the log file to see if the shader loaded successfully. """
    log_path = os.path.join(log_dir, "retroarch.log")
    shader_loaded = False
    time.sleep(2)  # Initial delay before starting to read the log
    for _ in range(3):  # Check log every 3 seconds up to 3 times
        with open(log_path, 'r') as log_file:
            lines = log_file.readlines()
            for line in lines:
                if f'[INFO] [Shaders]: Applying shader: "{shader}"' in line:
                    shader_loaded = True
                    break
                elif f'[ERROR] Command "{shader}" failed.' in line:
                    failed_shaders.append(shader)
                    return False
        if shader_loaded:
            return True
        time.sleep(3)  # Wait 3 seconds before next check
    failed_shaders.append(shader)
    return False

def handle_crash(slot_number, last_shader, crashed_shaders, retry=False):
    global crash_count, initial_run
    crash_count += 1
    update_status("C R A S H E D! R E S T A R T I N G !!", color="yellow", font=("Nimbus Mono PS", 25, 'bold italic'))

    if last_shader and not retry:
        crashed_shaders.append(last_shader)
        delete_last_screenshot(last_shader)
    elif retry and last_shader:
        crashed_shaders.append(last_shader)
        last_shader = None  # Ensure the last shader is skipped on the next run

    run_killall()
    initial_run = False  # Ensure initial_run is False during restarts

    # Move to the left workspace when handling a crash
    move_to_workspace("left")

    start_retroarch(slot_number, last_shader, crashed_shaders, not retry)

def run_killall():
    """Run the killall command to terminate all RetroArch instances."""
    try:
        subprocess.run(["killall", "retroarch"], check=True)
        time.sleep(2)  # Wait for 2 seconds to ensure all instances are terminated
    except subprocess.CalledProcessError:
        print("RetroArch was not running or couldn't be killed.")
    except Exception as e:
        print(f"An error occurred while trying to kill RetroArch: {e}")

def delete_last_screenshot(shader_name):
    """ Delete the last screenshot taken if RetroArch crashes. """
    try:
        shader_folder = os.path.basename(os.path.dirname(shader_name))
        base_name = os.path.splitext(os.path.basename(shader_name))[0]
        screenshot_name = f"{shader_folder}-{base_name}.png"
        screenshot_path = os.path.join(screenshot_dir, screenshot_name)
        if os.path.exists(screenshot_path) and base_name != "stock":
            os.remove(screenshot_path)
            print(f"Deleted corrupted screenshot: {screenshot_path}")
    except Exception as e:
        print(f"Failed to delete screenshot: {e}")

def finalize_process(shaders, crashed_shaders):
    """ Finalize the process by creating a report of crashed shaders and zipping the results. """
    # Move to the left workspace when finalizing the process
    move_to_workspace(0)

    run_killall()  # Ensure RetroArch is closed before finalizing

    shader_amount = len(shaders_list)  # Count total shaders in shaders_list
    crash_report_path = os.path.join(shader_results, "shader_results.txt")
    screen_resolution = get_screen_resolution()  # Get screen resolution
    shader_count = sum(
        [len(find_shaders(os.path.join(shader_dir, shader), shader_extensions)) for shader in create_temp_shader_list()]
    )
    with open(crash_report_path, 'w') as file:
        file.write(f"Video_driver = vulkan\n")
        file.write(f"Screen resolution: {screen_resolution}\n")
        corename = get_core_corename(selected_core)
        file.write(f"Core name: {corename}\n")
        rom_name = os.path.basename(selected_rom)
        file.write(f"ROM name: {rom_name}\n")
        file.write(f"Number of shaders available: {shader_count}\n")
        file.write(f"Failed shaders: {len(set(failed_shaders))}\n")  # Remove duplicates

        unique_failed_shaders = set(failed_shaders)  # Use a set to remove duplicates
        for shader in unique_failed_shaders:
            shader_name = os.path.basename(shader)
            file.write(f"- {shader_name}\n")

        file.write(f"Number of crashes: {crash_count}\n")
        file.write("Shader(s) that possibly caused the crash:\n")
        for shader in crashed_shaders:
            shader_name = os.path.basename(shader)
            file.write(f"- {shader_name}\n")

    current_time = datetime.now().strftime("%Y%m%d_%H%M%S")
    zip_filename = os.path.join(shader_results, f"Shader_results_{current_time}.zip")
    with ZipFile(zip_filename, 'w') as zipf:
        for foldername, subfolders, filenames in os.walk(screenshot_dir):
            for filename in filenames:
                file_path = os.path.join(foldername, filename)
                zipf.write(file_path, os.path.relpath(file_path, screenshot_dir))
        zipf.write(crash_report_path, os.path.basename(crash_report_path))
    time.sleep(2)  # Ensure the zip file is written correctly
    update_status(f"Process completed: Downloading to your device.. ", color="red", font=("Nimbus Mono PS", 26, 'normal'))
    quit_retroarch()
    messagebox.showinfo("Process Complete", "The process has completed successfully.")

    # Delete screenshots and shader result file
    for file in os.listdir(screenshot_dir):
        file_path = os.path.join(screenshot_dir, file)
        try:
            if os.path.isfile(file_path):
                os.unlink(file_path)
        except Exception as e:
            print(f"Error deleting file {file_path}: {e}")

    try:
        os.remove(crash_report_path)
    except Exception as e:
        print(f"Error deleting file {crash_report_path}: {e}")

    # Restart the setup GUI state
    enable_buttons()
    restart_process()

def get_status():
    """ Get the status of RetroArch to detect if it has crashed. """
    try:
        result = subprocess.run(
            f'echo -n "GET_STATUS" | nc -u -w1 127.0.0.1 {network_cmd_port}',
            shell=True,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        response = result.stdout.decode().strip()
        print(f"RetroArch status: {response}")
        return response
    except subprocess.CalledProcessError as e:
        print(f"Failed to get status: {e}")
        return None

def pause_process():
    """ Pause the shader testing process. """
    global pause_flag
    pause_flag = not pause_flag  # Toggle the pause flag
    if pause_flag:
        print("Process paused.")
        pause_button.configure(text="Unpause")
        keyboard.press('p')
        keyboard.release('p')
    else:
        print("Process resumed.")
        pause_button.configure(text="Pause")
        keyboard.press('p')
        keyboard.release('p')

def restart_process():
    """ Restart the shader testing process. """
    global pause_flag, crashed_shaders, failed_shaders, crash_count, selected_core, selected_rom, selected_bios, selected_save_state

    pause_flag = False
    crashed_shaders = []
    failed_shaders = []
    crash_count = 0
    selected_core = None
    selected_rom = None
    selected_bios = None
    selected_save_state = None

    # Enable the "Start" button and other options again
    start_button.configure(state=tk.NORMAL)
    core_listbox.configure(state=tk.NORMAL)
    core_listbox.selection_clear(0, tk.END)  # Clear selection in the core list
    rom_button.configure(state=tk.NORMAL)
    bios_button.configure(state=tk.NORMAL)
    save_state_button.configure(state=tk.NORMAL)

    core_label.configure(text="No core selected", text_color="white")
    rom_label.configure(text="No ROM selected", text_color="white")
    bios_label.configure(text="No BIOS selected", text_color="white")
    save_state_label.configure(text="No Save State selected", text_color="white")

    # Clear shader selections
    for var in shader_checkboxes.values():
        var.set(False)

    # Clear status text
    status_text.configure(state=tk.NORMAL)
    status_text.delete('1.0', tk.END)
    status_text.configure(state=tk.DISABLED)

    # Move to the right workspace when restarting the process
    move_to_workspace(1)

def move_to_workspace(workspace):
    """Switch workspace using wmctrl."""
    try:
        subprocess.run(["wmctrl", "-s", str(workspace)], check=True)
    except subprocess.CalledProcessError as e:
        print(f"Failed to switch workspace: {e}")

def close_application():
    global root
    root.destroy()
    print("Libretro Shader has closed.")

def quit_retroarch():
    """ Quit RetroArch and stop the script. """
    try:
        subprocess.run(
            f'echo -n "QUIT" | nc -u -w1 127.0.0.1 {network_cmd_port}',
            shell=True,
            check=True
        )
        print("RetroArch quit successfully.")
    except subprocess.CalledProcessError as e:
        print(f"Failed to quit RetroArch: {e}")

def start_retroarch(slot_number=None, last_shader=None, crashed_shaders=None, retry=False):
    global selected_core, selected_rom, selected_bios, selected_save_state
    global shaders_list, initial_run

    # Ensure all previous RetroArch instances are terminated
    run_killall()

    if not selected_core or not selected_rom or not selected_save_state:
        messagebox.showerror("Error", "Please select a core, ROM, and save state.")
        return

    update_status("#Loading libretro CORE-ROM", color="white", font=('Nimbus Mono PS', 25, 'normal'))

    modify_retroarch_cfg()

    # Copy the BIOS file to the designated directory if selected
    if selected_bios:
        update_status("#Copying BIOS file", color="white", font=('Nimbus Mono PS', 25, 'normal'))
        try:
            shutil.copy2(selected_bios, bios_dir)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to copy BIOS file: {e}")
            return

    # Copy the save state to the designated directory if selected
    if selected_save_state:
        update_status("#Copying Save State", color="white", font=('Nimbus Mono PS', 25, 'normal'))
        corename = get_core_corename(selected_core)
        if corename:
            destination_dir = os.path.join(savestate_dir, corename)
            os.makedirs(destination_dir, exist_ok=True)
            destination_path = os.path.join(destination_dir, os.path.basename(selected_save_state))
            shutil.copy2(selected_save_state, destination_path)
            # Determine slot number based on file extension
            if selected_save_state.endswith('.state'):
                slot_number = 0
            else:
                slot_number = int(os.path.splitext(os.path.basename(selected_save_state))[1][-1])
            print(f"Save state copied to {destination_path}, slot number: {slot_number}")
        else:
            messagebox.showerror("Error", "Failed to get corename from core info file.")
            return

    command = f'{retroarch_path} -L "{selected_core}" -c "{retroarch_cfg_path}" "{selected_rom}" --verbose'
    print(f"Starting RetroArch with command: {command}")
    try:
        process = subprocess.Popen(command, shell=True, env=os.environ, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE)

        # Move to the right workspace immediately after sending the command to start RetroArch
        move_to_workspace(1)

        # Wait for 30 seconds to ensure RetroArch has started
        time.sleep(30)

        # Load the save state if selected
        if selected_save_state:
            command_load_state = f"LOAD_STATE_SLOT {slot_number}\n"
            print(f"Loading save state with command: {command_load_state}")
            process.stdin.write(command_load_state.encode())
            process.stdin.flush()

        # Initialize Shader List
        if select_all_var.get():
            shaders_list = find_shaders(shader_dir, shader_extensions)
        else:
            temp_shader_list = create_temp_shader_list()
            shaders_list = []
            for shader_subdir in temp_shader_list:
                shaders_list.extend(find_shaders(shader_subdir, shader_extensions))

        if len(shaders_list) == 0:
            finalize_process(shaders_list, crashed_shaders)
            return

        # Adjust Shader List
        if last_shader:
            start_index = shaders_list.index(last_shader) + 1 if retry else shaders_list.index(last_shader)
            shaders_list = shaders_list[start_index:]

        initial_run = True  # Set initial_run to True for the first shader application
        update_status("Starting shader cycle")
        print("Starting shader cycle")
        cycle_shaders(process, slot_number, crashed_shaders or [])
    except Exception as e:
        print(f"Exception occurred: {e}")
        messagebox.showerror("Error", f"Failed to start RetroArch: {e}")

class ScrollableFrame(ctk.CTkScrollableFrame):
    def __init__(self, master, *args, **kwargs):
        super().__init__(master, *args, **kwargs)

        # Bind mouse wheel for scrolling
        self.bind("<MouseWheel>", self._on_mousewheel)
        self.bind("<Button-4>", lambda e: self._on_mousewheel(e, -1))
        self.bind("<Button-5>", lambda e: self._on_mousewheel(e, 1))

    def _on_mousewheel(self, event, delta=None):
        if delta is None:
            delta = int(-1 * (event.delta / 120))
        self._parent_canvas.yview_scroll(delta, "units")

def setup_gui():
    global root
    global start_button, pause_button, restart_button, close_button
    global core_listbox, rom_button, bios_button, save_state_button
    global core_label, rom_label, bios_label, save_state_label, status_text, shader_checkboxes
    global select_all_var

    root = ctk.CTk()
    root.title("Libretro Loader")
    root.configure(fg_color="black")
    root.wm_attributes("-topmost", 1)
    root.attributes('-fullscreen', True)

    main_frame = ctk.CTkFrame(root, fg_color="grey")
    main_frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=10)

    left_top_frame = ctk.CTkFrame(main_frame, fg_color="grey")
    left_top_frame.grid(row=0, column=0, sticky="nsew", padx=15, pady=10)
    left_top_frame.grid_rowconfigure(0, weight=1)
    left_top_frame.grid_columnconfigure(0, weight=1)

    right_top_frame = ScrollableFrame(main_frame, fg_color="grey")
    right_top_frame.grid(row=0, column=1, sticky="nsew", padx=15, pady=10)

    left_bottom_frame = ctk.CTkFrame(main_frame, fg_color="black")
    left_bottom_frame.grid(row=1, column=0, sticky="nsew", padx=15, pady=10)

    right_bottom_frame = ctk.CTkFrame(main_frame, fg_color="grey")
    right_bottom_frame.grid(row=1, column=1, sticky="nsew", padx=15, pady=10)

    main_frame.columnconfigure(0, weight=1)
    main_frame.columnconfigure(1, weight=1)
    main_frame.rowconfigure(0, weight=1)
    main_frame.rowconfigure(1, weight=1)

    select_all_var = tk.BooleanVar(value=False)

    # Scrollable core list
    core_listbox = tk.Listbox(left_top_frame, bg="black", fg="white")
    core_listbox.grid(row=0, column=0, sticky="nsew")

    core_scrollbar = ctk.CTkScrollbar(left_top_frame, orientation="vertical", command=core_listbox.yview)
    core_scrollbar.grid(row=0, column=1, sticky="ns")

    core_listbox.configure(yscrollcommand=core_scrollbar.set)

    core_paths = find_files(core_dir, ('.so',))
    core_display_dict = {core: get_core_display_name(core) for core in core_paths}
    sorted_cores = sorted(core_display_dict.items(), key=lambda item: item[1].lower())

    display_to_core = {}

    for core, display_name in sorted_cores:
        core_listbox.insert(tk.END, display_name)
        display_to_core[display_name] = core

    def on_core_select(event):
        global selected_core
        selected_core_index = core_listbox.curselection()
        if selected_core_index:
            selected_core_text = core_listbox.get(selected_core_index)
            selected_core = display_to_core[selected_core_text]
            core_label.configure(text=f"Selected Core: {selected_core_text}", text_color="red")
            adjust_text_to_fit(core_label)

    core_listbox.bind("<<ListboxSelect>>", on_core_select)

    # Shader checkboxes
    shader_checkboxes = {}
    shader_dirs = [d for d in os.listdir(shader_dir) if os.path.isdir(os.path.join(shader_dir, d))]

    def format_time(seconds):
        mins, secs = divmod(seconds, 60)
        hours, mins = divmod(mins, 60)
        return f"{hours} hours, {mins} mins, {secs} secs" if hours else f"{mins} mins, {secs} secs"

    def on_select_all():
        total_shaders = sum(len(find_shaders(os.path.join(shader_dir, d), shader_extensions)) for d in shader_dirs)
        time_estimate = format_time(total_shaders * 45)
        select_all_checkbox.configure(text=f"SELECT ALL ({total_shaders}) (Max Estimation Time: {time_estimate})")
        for var in shader_checkboxes.values():
            var.set(select_all_var.get())
        create_temp_shader_list()  # Create temp shader list based on selection

    total_shaders = sum(len(find_shaders(os.path.join(shader_dir, d), shader_extensions)) for d in shader_dirs)
    time_estimate = format_time(total_shaders * 45)
    select_all_checkbox = ctk.CTkCheckBox(right_top_frame,
                                          text=f"SELECT ALL ({total_shaders}) (Max Estimation Time: {time_estimate})",
                                          variable=select_all_var, command=on_select_all, fg_color="black",
                                          text_color="red")
    select_all_checkbox.pack(pady=5)

    for shader_subdir in shader_dirs:
        shader_path = os.path.join(shader_dir, shader_subdir)
        shaders = find_shaders(shader_path, shader_extensions)
        time_estimate = format_time(len(shaders) * 45)
        checkbox_var = tk.BooleanVar(value=False)
        shader_checkboxes[shader_subdir] = checkbox_var
        checkbox = ctk.CTkCheckBox(right_top_frame,
                                   text=f"{shader_subdir} ({len(shaders)}) (Max Estimation Time: {time_estimate})",
                                   variable=checkbox_var,
                                   fg_color="black", text_color="black")
        checkbox.pack(pady=5)
        # Store the reference to the Checkbutton widget
        shader_checkbuttons[shader_subdir] = checkbox

    core_label = ctk.CTkLabel(left_bottom_frame, text="No Core selected", fg_color="black", text_color="white")
    core_label.pack(pady=5)

    rom_button = ctk.CTkButton(left_bottom_frame, text="Select ROM", command=load_rom, fg_color="blue",
                               text_color="white")
    rom_button.pack(pady=5)

    rom_label = ctk.CTkLabel(left_bottom_frame, text="No ROM selected", fg_color="black", text_color="white")
    rom_label.pack(pady=5)

    bios_button = ctk.CTkButton(left_bottom_frame, text="Select BIOS", command=load_bios, fg_color="blue",
                                text_color="white")
    bios_button.pack(pady=5)

    bios_label = ctk.CTkLabel(left_bottom_frame, text="No BIOS selected", fg_color="black", text_color="white")
    bios_label.pack(pady=5)

    save_state_button = ctk.CTkButton(left_bottom_frame, text="Select Save State", command=load_save_state,
                                      fg_color="blue", text_color="white")
    save_state_button.pack(pady=5)

    save_state_label = ctk.CTkLabel(left_bottom_frame, text="No Save State selected", fg_color="black",
                                    text_color="white")
    save_state_label.pack(pady=5)

    start_button = ctk.CTkButton(left_bottom_frame, text="B E G I N", command=confirm_start, fg_color="blue",
                                 text_color="white")
    start_button.pack(pady=10)

    pause_button = ctk.CTkButton(left_bottom_frame, text="P A U S E", command=pause_process, fg_color="blue",
                                 text_color="white", state=tk.NORMAL)
    pause_button.pack(pady=10)
    restart_button = ctk.CTkButton(left_bottom_frame, text="R E S T A R T", command=restart_process, fg_color="blue",
                                   text_color="white", state=tk.NORMAL)
    restart_button.pack(pady=10)
    close_button = ctk.CTkButton(left_bottom_frame, text="C L O S E", command=close_application, fg_color="red",
                                   text_color="white")
    close_button.pack(pady=10)

    status_text = tk.Text(right_bottom_frame, bg="black", fg="white", state=tk.DISABLED, wrap=tk.WORD)
    status_text.pack(fill=tk.BOTH, expand=True)

    # Update fonts based on screen resolution
    update_fonts()

    # Fix mouse wheel scrolling issue
    def on_mousewheel(event):
        right_top_frame._on_mousewheel(event)

    right_top_frame.bind_all("<MouseWheel>", on_mousewheel)

    root.mainloop()

def confirm_start():
    if not selected_core or not selected_rom or not selected_save_state:
        missing_items = []
        if not selected_core:
            missing_items.append("CORE")
        if not selected_rom:
            missing_items.append("ROM")
        if not selected_save_state:
            missing_items.append("SAVE STATE")
        messagebox.showerror("Error", f"Please select a {', '.join(missing_items)}.")
        return

    selected_shader_names = [shader for shader, var in shader_checkboxes.items() if var.get()]
    if not selected_shader_names:
        messagebox.showerror("Error", "Please select at least one shader.")
        return

    def format_time(seconds):
        mins, secs = divmod(seconds, 60)
        hours, mins = divmod(mins, 60)
        return f"{hours} hours, {mins} mins, {secs} secs" if hours else f"{mins} mins, {secs} secs"

    shader_count = sum(
        [len(find_shaders(os.path.join(shader_dir, shader), shader_extensions)) for shader in selected_shader_names])
    total_time = shader_count * 45
    time_estimate = format_time(total_time)

    confirm_window = tk.Toplevel()
    confirm_window.title("Confirm Selection")
    confirm_window.configure(bg="black")
    confirm_window.wm_attributes("-topmost", 1)
    confirm_window.attributes('-fullscreen', True)

    ctk.CTkLabel(confirm_window, text="CORE:", fg_color="black", text_color="white", font=('Nimbus Mono PS', 28)).pack(
        pady=5)
    ctk.CTkLabel(confirm_window, text=get_core_display_name(selected_core), fg_color="black", text_color="red",
                 font=('Nimbus Mono PS', 28, 'bold')).pack(pady=5)

    ctk.CTkLabel(confirm_window, text="ROM:", fg_color="black", text_color="white", font=('Nimbus Mono PS', 28)).pack(
        pady=5)
    ctk.CTkLabel(confirm_window, text=os.path.basename(selected_rom), fg_color="black", text_color="red",
                 font=('Nimbus Mono PS', 28, 'bold')).pack(pady=5)

    ctk.CTkLabel(confirm_window, text="BIOS:", fg_color="black", text_color="white", font=('Nimbus Mono PS', 28)).pack(
        pady=5)
    ctk.CTkLabel(confirm_window, text=os.path.basename(selected_bios) if selected_bios else "Not selected",
                 fg_color="black", text_color="red", font=('Nimbus Mono PS', 28, 'bold')).pack(pady=5)

    ctk.CTkLabel(confirm_window, text="SAVE STATE:", fg_color="black", text_color="white",
                 font=('Nimbus Mono PS', 28)).pack(pady=5)
    ctk.CTkLabel(confirm_window, text=os.path.basename(selected_save_state), fg_color="black", text_color="red",
                 font=('Nimbus Mono PS', 28, 'bold')).pack(pady=5)

    ctk.CTkLabel(confirm_window, text="SELECTED SHADERS:", fg_color="black", text_color="white",
                 font=('Nimbus Mono PS', 28)).pack(pady=5)
    ctk.CTkLabel(confirm_window, text=", ".join(selected_shader_names), fg_color="black", text_color="red",
                 font=('Nimbus Mono PS', 28, 'bold')).pack(pady=5)

    ctk.CTkLabel(confirm_window, text=f"TOTAL SHADERS: {shader_count}", fg_color="black", text_color="red",
                 font=('Nimbus Mono PS', 28)).pack(pady=5)

    ctk.CTkLabel(confirm_window, text=f"Max Estimation Time: {time_estimate}", fg_color="black", text_color="red",
                 font=('Nimbus Mono PS', 28)).pack(pady=5)

    ctk.CTkButton(confirm_window, text="S T A R T",
                  command=lambda: [confirm_window.destroy(), enable_buttons(), start_retroarch()],
                  fg_color="white", text_color="black", font=('Nimbus Mono PS', 28, 'bold')).pack(pady=10)
    ctk.CTkButton(confirm_window, text="R E S E L E C T", command=confirm_window.destroy,
                  fg_color="white", text_color="black", font=('Nimbus Mono PS', 28, 'bold')).pack(pady=10)

def enable_buttons():
    """ Enable pause and restart buttons, and disable start and selection options. """
    start_button.configure(state=tk.DISABLED)
    core_listbox.configure(state=tk.DISABLED)
    rom_button.configure(state=tk.DISABLED)
    bios_button.configure(state=tk.DISABLED)
    save_state_button.configure(state=tk.DISABLED)
    pause_button.configure(state=tk.NORMAL)
    restart_button.configure(state=tk.NORMAL)
    close_button.configure(state=tk.NORMAL)
    for checkbox in shader_checkbuttons.values():
        checkbox.configure(state=tk.NORMAL)

def wrap_text_to_fit(text, font, max_width):
    """ Wrap text to fit within the specified width. """
    wrapped_text = ""
    words = text.split()
    current_line = ""
    for word in words:
        test_line = current_line + " " + word if current_line else word
        if get_text_width(test_line, font) <= max_width:
            current_line = test_line
        else:
            wrapped_text += current_line + "\n"
            current_line = word
    wrapped_text += current_line
    return wrapped_text

def get_text_width(text, font):
    """ Calculate the width of the text with the specified font. """
    temp_label = tk.Label(text=text, font=font)
    temp_label.pack()
    width = temp_label.winfo_width()
    temp_label.destroy()
    return width

def calculate_font_size(base_size=10):
    """ Calculate font size based on screen resolution. """
    screen_width, screen_height = map(int, get_screen_resolution().split('x'))
    base_resolution = (1920, 1080)  # Reference resolution
    width_ratio = screen_width / base_resolution[0]
    height_ratio = screen_height / base_resolution[1]
    return int(base_size * min(width_ratio, height_ratio))

def update_fonts():
    """ Update fonts for all widgets based on screen resolution. """
    font_size = calculate_font_size()
    adjusted_font = ('Nimbus Mono PS', font_size)
    core_listbox.configure(font=adjusted_font)
    core_label.configure(font=adjusted_font)
    rom_label.configure(font=adjusted_font)
    bios_label.configure(font=adjusted_font)
    save_state_label.configure(font=adjusted_font)
    status_text.configure(font=adjusted_font)
    start_button.configure(font=adjusted_font)
    pause_button.configure(font=adjusted_font)
    restart_button.configure(font=adjusted_font)
    close_button.configure(font=adjusted_font)
    rom_button.configure(font=adjusted_font)
    bios_button.configure(font=adjusted_font)
    save_state_button.configure(font=adjusted_font)
    for checkbox in shader_checkbuttons.values():
        checkbox.configure(font=adjusted_font)

def update_status(message, color="white", font=("Nimbus Mono PS", 25, 'normal')):
    """ Update the status text in the UI. """
    status_text.configure(state=tk.NORMAL)
    status_text.insert(tk.END, message + "\n")
    status_text.tag_add("step", "end-2c linestart", "end-2c lineend")
    status_text.tag_config("step", foreground=color, font=font)
    status_text.configure(state=tk.DISABLED)
    status_text.see(tk.END)
    status_text.update()  # Ensure the update is shown immediately

if __name__ == "__main__":
    setup_gui()
