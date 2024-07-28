# ShaderScriptContainer
Obtain a folder of shader screenshots from retroarch by using your rom, save state and a container

## **Windows 10**

Prerequisites
- ROM
- Save State *(From RetroArch)*
- BIOS *(If the core requires it)*
- Initial internet connection *(To build the docker image)*

### *1*. **Download the following:**
- VcXsrv Windows X Server: https://github.com/marchaesen/vcxsrv
- Docker Desktop: https://www.docker.com/products/docker-desktop/
- Install both
### *2*. **Download the Windows 10 folder and extract it's zip file:**
- GL Driver = `RetroGL & RetroGLDocker`
- GLCore Driver = `RetroGL & RetroGLCoreDocker`
- Vulkan Driver = `RetroVulkan & RetroVulkanDocker`
### *3*. **Start Docker**
- Launch docker, if it's your first time, follow the steps on the screen.
### *4*. **Build the downloaded dockerfile**
- Go to the where the files are downloaded, make sure the python driver, it's docker file, and retroarch.cfg are in the same folder
- Open command promt. You can either cd "insert folder path here" without quotes after opening command promt or type cmd in the address bar of file explorer to open command promt within that folder
- type: `"docker build -t my-windows-image -f filenameofdockerfile.dockerfile ."` without quotes. Change filenameofdockerfile to the filename of that file
- When completed, your docker image will be saved as my-windows-image.
- Type ipconfig to obtain your IP, it will be your IPv4 Address
- Do not close the command prompt
### *5*. **Launch container with your IP**
- In Windows search bar, we will launch the installed VcXsrv by typing `XLaunch`
- Select any display setting (Multi Window) | Start no client | check the "Disable access control" checkbox, select finished.
- Back to the previous command prompt, you will now launch the my-windows-image while it's connect to one of your folders that has your ROM, Save State and bios (if necessary).
- You will type
`"set DISPLAY=iphere:0.0"`

`"docker run -it --rm --privileged --name retroarch-shaders -e DISPLAY=host.docker.internal:0.0 -v /tmp/.X11-unix:/tmp/.X11-unix -v "C:\This\IS\The\Path\To\Your\Current\FolderShared:/app/data" my-windows-image"` without quotes.
Change iphere in set DISPLAY to your IP from ipconfig, and change C:\This\IS\The\Path\To\Your\Current\FolderShared to the path of your ROM/Save State and BIOS
- The XLaunch should open a screen, showing a 4 quadrant gui. You may have to enlarge XLAunch depending on the display setting you selected.
### 6. GUI asking you to select a core, rom, save state and shaders should load
- Follow that, and profit?

### **Increase Speed/Descrease Speed**

You can increase/decrease the speed of how the shaders are captured in the python file you downloaded. May be good to do depending on the device used to do this
- Open the Python file in your preferred IDE.
- CTRL + F, type time.sleep(20). That should be within the function def start_retroarch, it should have time.sleep(20). This is based on your computer speed, as some has note with bezels can crash https://forums.libretro.com/t/mega-bezel-reflection-shader-feedback-and-updates/25512/1491
- Increase/decrease the number based on your own discretion.
- After adjusting CTRL + F, type "* 35" without quotes. Increase or decrease that number for all 4 locations within that file to get a proper max estimated time when running the shader program that corresponds with how you adjusted the time.sleep(20) for the start_retroarch function.
