import os
import time
import tkinter as tk
from tkinter import filedialog, messagebox
import requests
import tqdm
from threading import Thread
from zipfile import ZipFile
import subprocess
import shutil
from git import Repo

# Downloads and updates Retroarch cores and shaders
# Provides paths for retroarch configuration
def find_retroarch_paths():
    retroarch_executable = 'retroarch'
    target_folder = '.config/retroarch'

    def check_paths(base_path):
        results = []

        # Walk through the directory tree
        for root, dirs, files in os.walk(base_path):
            # Check for RetroArch executable
            if retroarch_executable in files:
                retroarch_exec_path = os.path.join(root, retroarch_executable)
                results.append(('RetroArch Executable', retroarch_exec_path))

            # Check if there is a "current" folder and if it contains the .config/retroarch folder
            if 'current' in dirs:
                current_path = os.path.join(root, 'current')
                config_path = os.path.join(current_path, target_folder)
                if os.path.isdir(config_path) and 'retroarch' in root:
                    results.append(('RetroArch .config Folder', config_path))

        return results

    discovered_paths = []

    # User directories
    home_dirs = [os.path.join('/home', d) for d in os.listdir('/home') if os.path.isdir(os.path.join('/home', d))]
    home_dirs.append(os.path.expanduser('~'))

    # Snap directories
    snap_dirs = [
        '/var/lib/snapd/snaps/',
        '/snap',
        lambda user_dir: os.path.join(user_dir, 'snap')
    ]

    # Flatpak directories
    flatpak_dirs = [
        '/var/lib/flatpak',
        os.path.expanduser('~/.local/share/flatpak')
    ]

    # AppImage directories (typically user-defined)
    appimage_dirs = [
        os.path.expanduser('~/Applications')
    ]

    # System-wide directories
    system_dirs = [
        '/usr/local/bin',
        '/usr/bin',
        '/bin'
    ]

    # Check all defined paths
    for check_dir in snap_dirs + flatpak_dirs + appimage_dirs + system_dirs:
        if callable(check_dir):
            for user_dir in home_dirs:
                discovered_paths.extend(check_paths(check_dir(user_dir)))
        elif os.path.isdir(check_dir):
            discovered_paths.extend(check_paths(check_dir))

    return discovered_paths

def generate_configuration(retroarch_path, retroarch_cfg_path, driver, config_folder):
    # Ensure config_folder is an absolute path
    config_folder = os.path.abspath(config_folder)

    core_dir = os.path.join(config_folder, 'cores')
    info_dir = os.path.join(config_folder, 'info')
    savestate_dir = os.path.join(config_folder, 'states')
    screenshot_dir = os.path.join(config_folder, 'screenshots')
    bios_dir = os.path.join(config_folder, 'system')
    shader_dir = os.path.join(config_folder, 'shaders', 'shaders_slang' if driver in ['Vulkan', 'GLCore'] else 'shaders_glsl')
    log_dir = os.path.join(config_folder, 'logs')
    shader_extensions = "('.slangp',)" if driver in ['Vulkan', 'GLCore'] else "('.glsl',)"

    # Extract directory path from retroarch_cfg_path
    shader_results = os.path.dirname(retroarch_cfg_path)

    config = f"""
# Configuration
retroarch_path = '{retroarch_path}'
core_dir = '{core_dir}'
info_dir = '{core_dir}'
shader_dir = '{shader_dir}'
default_shader_dir = '{shader_dir}'
retroarch_cfg_path = '{retroarch_cfg_path}'
log_dir = '{log_dir}'
savestate_dir = '{savestate_dir}'
screenshot_dir = '{screenshot_dir}'
bios_dir = '{bios_dir}'
shader_extensions = {shader_extensions}  # Corrected to be a tuple
shader_results = '{shader_results}'
"""
    return config

def copy_to_clipboard(text):
    root = tk.Tk()
    root.withdraw()
    root.clipboard_clear()
    root.clipboard_append(text)
    root.update()  # Now it stays on the clipboard after the window is closed
    root.destroy()

def download_file(url, dest_dir, update_text):
    try:
        response = requests.get(url, stream=True)
        response.raise_for_status()  # Raise an HTTPError for bad responses
        filename = os.path.join(dest_dir, url.split('/')[-1])
        total_size = int(response.headers.get('content-length', 0))

        # Download file
        with open(filename, 'wb') as file, progress_bar(total_size, filename) as bar:
            for data in response.iter_content(chunk_size=1024):
                file.write(data)
                bar.update(len(data))
                update_text(f"Downloading {url.split('/')[-1]}: {bar.n}/{total_size} bytes\n")

        return filename
    except requests.exceptions.RequestException as e:
        update_text(f"Error downloading {url.split('/')[-1]}: {e}\n")
        return None

def progress_bar(total_size, filename):
    return tqdm.tqdm(total=total_size, unit='B', unit_scale=True, desc=f'Downloading {filename}')

def extract_7z(file_path, dest_dir, update_text):
    if not file_path:
        return
    temp_extract_dir = os.path.join(dest_dir, "temp_extract")
    os.makedirs(temp_extract_dir, exist_ok=True)
    try:
        update_text(f"Extracting archive {os.path.basename(file_path)}...\n")
        subprocess.run(['7z', 'x', file_path, f'-o{temp_extract_dir}'], check=True)
        # Move files while preserving directory structure
        extracted_core_dir = os.path.join(temp_extract_dir, "RetroArch-Linux-x86_64", "RetroArch-Linux-x86_64.AppImage.home", ".config", "retroarch", "cores")
        if os.path.isdir(extracted_core_dir):
            for root, _, files in os.walk(extracted_core_dir):
                for file in files:
                    full_path = os.path.join(root, file)
                    rel_path = os.path.relpath(full_path, extracted_core_dir)
                    dest_file_path = os.path.join(dest_dir, rel_path)
                    os.makedirs(os.path.dirname(dest_file_path), exist_ok=True)
                    os.replace(full_path, dest_file_path)
                    time.sleep(0.01)  # Add delay for each file operation
            shutil.rmtree(extracted_core_dir)  # Remove the extracted core directory
        update_text(f"{os.path.basename(file_path)} extracted to {dest_dir}.\n")
    except subprocess.CalledProcessError as e:
        update_text(f"Error extracting {file_path}: {e}\n")
    finally:
        shutil.rmtree(temp_extract_dir)  # Clean up temporary extract directory
        os.remove(file_path)  # Ensure the .7z file is deleted

def extract_zip(file_path, dest_dir, update_text):
    if not file_path:
        return
    temp_extract_dir = os.path.join(dest_dir, "temp_extract")
    os.makedirs(temp_extract_dir, exist_ok=True)
    try:
        update_text(f"Extracting archive {os.path.basename(file_path)}...\n")
        with ZipFile(file_path, 'r') as archive:
            archive.extractall(temp_extract_dir)
            # Move files while preserving directory structure
            for root, _, files in os.walk(temp_extract_dir):
                for file in files:
                    full_path = os.path.join(root, file)
                    rel_path = os.path.relpath(full_path, temp_extract_dir)
                    dest_file_path = os.path.join(dest_dir, rel_path)
                    os.makedirs(os.path.dirname(dest_file_path), exist_ok=True)
                    os.replace(full_path, dest_file_path)
                    time.sleep(0.01)  # Add delay after each file operation
        update_text(f"{os.path.basename(file_path)} extracted to {dest_dir}.\n")
    except Exception as e:
        update_text(f"Error extracting {file_path}: {e}\n")
    finally:
        shutil.rmtree(temp_extract_dir)  # Clean up temporary extract directory
        os.remove(file_path)  # Ensure the .zip file is deleted

def clone_libretro_core_info(dest_dir, update_text):
    repo_url = "https://github.com/libretro/libretro-core-info.git"
    repo_path = os.path.join(dest_dir, "libretro-core-info")
    if os.path.exists(repo_path):
        shutil.rmtree(repo_path)  # Remove existing directory if it exists
    update_text("Cloning libretro-core-info repository...\n")
    try:
        Repo.clone_from(repo_url, repo_path)
        # Move files to dest_dir while preserving directory structure
        for root, dirs, files in os.walk(repo_path):
            for file in files:
                full_path = os.path.join(root, file)
                rel_path = os.path.relpath(full_path, repo_path)
                dest_file_path = os.path.join(dest_dir, rel_path)
                os.makedirs(os.path.dirname(dest_file_path), exist_ok=True)
                shutil.move(full_path, dest_file_path)
        shutil.rmtree(repo_path)  # Clean up cloned repository
        # Delete the .git folder if it exists
        git_dir = os.path.join(dest_dir, ".git")
        if os.path.exists(git_dir):
            shutil.rmtree(git_dir)
        update_text("libretro-core-info repository cloned and files copied to core_dir.\n")
    except Exception as e:
        update_text(f"Error cloning libretro-core-info repository: {e}\n")

def download_files(core_dir, shaders_slang_dir, shaders_glsl_dir, update_text):
    urls = [
        ("https://buildbot.libretro.com/stable/1.19.1/linux/x86_64/RetroArch_cores.7z", core_dir, extract_7z),
        ("https://buildbot.libretro.com/assets/frontend/shaders_slang.zip", shaders_slang_dir, extract_zip),
        ("https://buildbot.libretro.com/assets/frontend/shaders_glsl.zip", shaders_glsl_dir, extract_zip)
    ]

    downloaded_files = []
    for url, dest_dir, extract_func in urls:
        update_text(f"Downloading {url.split('/')[-1]}...\n")
        downloaded_file = download_file(url, dest_dir, update_text)
        if downloaded_file:
            downloaded_files.append((downloaded_file, dest_dir, extract_func))
            update_text(f"{url.split('/')[-1]} downloaded.\n")
        else:
            update_text(f"Failed to download {url.split('/')[-1]}\n")

    for file_path, dest_dir, extract_func in downloaded_files:
        extract_func(file_path, dest_dir, update_text)

    # Clone libretro-core-info repository
    clone_libretro_core_info(core_dir, update_text)

    update_text("Everything is Done\n")

def main():
    paths = find_retroarch_paths()
    if not paths:
        print("RetroArch paths not found.")
        return

    root = tk.Tk()
    root.title("RetroArch Configuration Generator")

    tk.Label(root, text="Select RetroArch Executable Path:").pack()
    retroarch_path_var = tk.StringVar()
    retroarch_path_var.set(next((path for desc, path in paths if desc == 'RetroArch Executable'), ''))
    tk.Entry(root, textvariable=retroarch_path_var, width=50).pack()

    tk.Label(root, text="Select retroarch.cfg Path:").pack()
    retroarch_cfg_path_var = tk.StringVar()
    tk.Entry(root, textvariable=retroarch_cfg_path_var, width=50).pack()
    tk.Button(root, text="Browse", command=lambda: retroarch_cfg_path_var.set(filedialog.askopenfilename())).pack()

    tk.Label(root, text="Select Graphics Driver:").pack()
    driver_var = tk.StringVar(value="Vulkan")
    tk.Radiobutton(root, text="Vulkan", variable=driver_var, value="Vulkan").pack()
    tk.Radiobutton(root, text="GL", variable=driver_var, value="GL").pack()
    tk.Radiobutton(root, text="GLCore", variable=driver_var, value="GLCore").pack()

    config_folder_var = tk.StringVar()
    config_folder_var.set(next((path for desc, path in paths if desc == 'RetroArch .config Folder'), ''))

    result_text = tk.Text(root, height=15, width=80)
    result_text.pack()

    def update_result_text(message):
        result_text.insert(tk.END, message)
        result_text.see(tk.END)
        root.update_idletasks()

    def generate_and_show():
        if not retroarch_cfg_path_var.get().strip():
            messagebox.showerror("Error", "Please select a retroarch.cfg path before generating the configuration.")
            return
        result_text.delete(1.0, tk.END)  # Clear the text box before showing configuration
        config = generate_configuration(retroarch_path_var.get(), retroarch_cfg_path_var.get(), driver_var.get(), config_folder_var.get())
        result_text.insert(tk.END, config)

    def copy_generated_config():
        config = result_text.get(1.0, tk.END)
        copy_to_clipboard(config)
        messagebox.showinfo("Success", "Configuration copied to clipboard!")

    def download_resources():
        result_text.delete(1.0, tk.END)  # Clear the text box before showing download updates
        core_dir = os.path.join(config_folder_var.get(), 'cores')
        shaders_slang_dir = os.path.join(config_folder_var.get(), 'shaders', 'shaders_slang')
        shaders_glsl_dir = os.path.join(config_folder_var.get(), 'shaders', 'shaders_glsl')
        log_dir = os.path.join(config_folder_var.get(), 'logs')
        savestate_dir = os.path.join(config_folder_var.get(), 'states')
        screenshot_dir = os.path.join(config_folder_var.get(), 'screenshots')
        bios_dir = os.path.join(config_folder_var.get(), 'system')

        for dir_path in [core_dir, shaders_slang_dir, shaders_glsl_dir, log_dir, savestate_dir, screenshot_dir, bios_dir]:
            os.makedirs(dir_path, exist_ok=True)

        # Disable buttons and inputs during download
        for widget in root.winfo_children():
            widget.config(state=tk.DISABLED)

        def download_thread():
            download_files(core_dir, shaders_slang_dir, shaders_glsl_dir, update_result_text)
            # Re-enable buttons and inputs after download
            for widget in root.winfo_children():
                widget.config(state=tk.NORMAL)
            # Update the download button text and disable it
            download_button.config(text="Latest Cores/Shaders Downloaded", state=tk.DISABLED)
            # Ensure the generate button is only enabled if retroarch.cfg path is set
            update_generate_button_state()

        Thread(target=download_thread).start()

    def update_generate_button_state(*args):
        if retroarch_cfg_path_var.get().strip():
            generate_button.config(state=tk.NORMAL)
        else:
            generate_button.config(state=tk.DISABLED)

    generate_button = tk.Button(root, text="Generate Configuration", command=generate_and_show)
    generate_button.pack()
    generate_button.config(state=tk.DISABLED)

    tk.Button(root, text="Copy Configuration", command=copy_generated_config).pack()
    download_button = tk.Button(root, text="Download Resources", command=download_resources)
    download_button.pack()

    retroarch_cfg_path_var.trace_add("write", update_generate_button_state)

    root.mainloop()

if __name__ == "__main__":
    main()
