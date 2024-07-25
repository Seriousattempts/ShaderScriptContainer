# ShaderScriptContainer
Obtain a folder of shader screenshots from retroarch by using your rom, save state and a container

*Windows 10*
Prerequisites
- RetroArch
- ROM
- Save State
- Bios* (If the core requires it)
- Initial internet connection

*1*. Download the following:
- VcXsrv Windows X Server: https://github.com/marchaesen/vcxsrv
- Docker Desktop: https://www.docker.com/products/docker-desktop/
*Maybe WSL2 (I already had it downloaded, so not sure if needed)
- Install both
*2*. Download the retroarch.dockerfile and any of the 3 Retro Python files:
- RetroGL = GL Driver
- RetroGL = GLCore Driver
- RetroVulkan = Vulkan Driver
*3*. Start Docker
*4*. Build the retroarch.dockerfile
- Go to the where the files are downloaded, make sure the python driver your downloaded and retroarch.dockerfile are in the same folder
- Note if you want to change the resolution of the shader screenshots, go to line 81, change 1920x1080 to your desired resolution
- Open command promt. You can either cd "insert folder path here" without quotes after opening command promt or type cmd in the address bar of file explorer to open command promt within that folder
- type: "docker build -t my-windows-image -f retroarch.dockerfile ." without quotes
- When completed, your docker image will be saved as my-windows-image.
- Type ipconfig to obtain your IP, it will be your IPv4 Address
- Do not close the command prompt
*5*. Launch container with your IP
- In the search bar, we will launch the installed VcXsrv by typing XLaunch
- Select any display setting | Start no client | check the "Disable access control" checkbox, select finished.
- Back to the previous command prompt, you will now launch the my-windows-image while it's connect to one of your folders that has your ROM, Save State and bios (if necessary).
- You will type "set DISPLAY=iphere:0.0
docker run -it --rm --privileged -e DISPLAY=%DISPLAY% -v /tmp/.X11-unix:/tmp/.X11-unix -v "C:\This\IS\The\Path\To\Your\Current\FolderShared:/app/data" ubuntu-desktop"
Change iphere in set DISPLAY to your IP from ipconfig, and change C:\This\IS\The\Path\To\Your\Current\Folder to the path of your ROM/Save State and BIOS
6. GUI asking you to select a core, rom, save state and shaders should load
- Follow that, and profit?

*Increase Speed/Descrease Speed*
You can increase/decrease the speed of how the shaders are captured in the python file you downloaded. May be good to do depending on the device used to do this
- Open the Python file in your preferred IDE or within Python.
- CTRL + F, type time.sleep(20). That should be within the function def start_retroarch, it should have time.sleep(20).
- Increase/decrease the number based on your own discretion.
- After adjusting CTRL + F, type * 45). Increase or decrease that number for all 3 locations withint hat file to get a proper max estimated time when running the shader program
