# Use the official Ubuntu 24.04 LTS base image
FROM ubuntu:24.04

# Set environment variables to avoid prompts during package installation
ENV DEBIAN_FRONTEND=noninteractive

# Install necessary packages
RUN apt-get update && \
    apt-get install -y \
    libxcb-xinerama0 libxcb-icccm4 libxcb-image0 libxcb-keysyms1 libxcb-render-util0 \
    libxcb-xfixes0 libxcb-shape0 libxcb-randr0 libxcb-xkb1 libxkbcommon-x11-0 \
    vulkan-tools libvulkan1 mesa-vulkan-drivers \
    build-essential libgtk-3-dev libjpeg-dev libtiff-dev libsdl2-dev libnotify-dev \
    freeglut3-dev libsm-dev libgtk2.0-dev pkg-config psmisc \
    wmctrl git python3-dev python3-tk python3-pip python3-venv dconf-cli p7zip-full unzip wget fontconfig xorg curl \
    gnupg2 software-properties-common libfuse2 xfce4 xfce4-goodies xrdp dbus-x11 netcat-traditional \
    python3-tk libx11-6 libxext6 libxrender1 libxrandr2 libxcursor1 libxfixes3 libpango-1.0-0 libcairo2 && \
    curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | apt-key add - && \
    curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list | \
    tee /etc/apt/sources.list.d/nvidia-container-toolkit.list && \
    apt-get install -y nvidia-container-toolkit && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# Create a virtual environment
ENV VIRTUAL_ENV=/opt/venv
RUN python3 -m venv $VIRTUAL_ENV
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

# Install Python packages in the virtual environment
RUN $VIRTUAL_ENV/bin/pip install --no-cache-dir pynput customtkinter

# Download and install Press Start 2P font
RUN wget https://github.com/google/fonts/raw/main/ofl/pressstart2p/PressStart2P-Regular.ttf -O /usr/local/share/fonts/PressStart2P-Regular.ttf && \
    fc-cache -f -v

# Create a user and set up home directory
ARG USERNAME=ralt
RUN useradd -ms /bin/bash $USERNAME

# Download and set up RetroArch
RUN mkdir -p /home/ralt/Downloads && \
    cd /home/ralt/Downloads && \
    wget -v https://buildbot.libretro.com/stable/1.19.1/linux/x86_64/RetroArch.7z && \
    7z x RetroArch.7z && \
    rm RetroArch.7z

# Download and extract RetroArch cores
RUN mkdir -p /home/ralt/Downloads/RetroArch_cores && \
    wget -v -O /home/ralt/Downloads/RetroArch_cores.7z https://buildbot.libretro.com/stable/1.19.1/linux/x86_64/RetroArch_cores.7z && \
    7z x -y /home/ralt/Downloads/RetroArch_cores.7z -o/home/ralt/Downloads/RetroArch_cores && \
    rm /home/ralt/Downloads/RetroArch_cores.7z

# Download and extract libretro-core-info via git
RUN git clone --branch v1.19.0 https://github.com/libretro/libretro-core-info.git /home/ralt/Downloads/libretro-core-info

# Download and extract shaders
RUN wget -v -O /home/ralt/Downloads/shaders_slang.zip https://buildbot.libretro.com/assets/frontend/shaders_slang.zip && \
    wget -v -O /home/ralt/Downloads/shaders_glsl.zip https://buildbot.libretro.com/assets/frontend/shaders_glsl.zip && \
    unzip -o /home/ralt/Downloads/shaders_slang.zip -d /home/ralt/Downloads/shaders_slang && \
    unzip -o /home/ralt/Downloads/shaders_glsl.zip -d /home/ralt/Downloads/shaders_glsl && \
    rm /home/ralt/Downloads/shaders_slang.zip /home/ralt/Downloads/shaders_glsl.zip

# Copy the retroarch.cfg file
COPY ./retroarch.cfg /home/ralt/Downloads/retroarch.cfg

# Set permissions
RUN chown -R $USERNAME:$USERNAME /home/ralt/Downloads

# Clone Dolphin emulator
RUN cd /opt && git clone https://github.com/libretro/dolphin

# Copy and adjust your Python application
COPY ./RetroGLCore.py /opt/retroarch/

# Change ownership of the app directory to the new user
RUN chown -R $USERNAME:$USERNAME /home/$USERNAME /opt/retroarch

# Set screen resolution and configure XFCE with 2 workspaces
RUN echo "export DISPLAY=\$DISPLAY" >> /home/$USERNAME/.bashrc && \
    echo "xrandr --output VGA1 --mode 1920x1080" >> /home/$USERNAME/.bashrc && \
    echo "xfconf-query -c xfwm4 -p /general/workspace_count -s 2" >> /home/$USERNAME/.bashrc

# Switch to the created user
USER $USERNAME

# Set up Dolphin, then start the Python application
CMD ["sh", "-c", "dbus-launch --exit-with-session startxfce4 & cd /opt/dolphin && mkdir -p /home/ralt/Downloads/RetroArch-Linux-x86_64/RetroArch-Linux-x86_64.AppImage.home/system/dolphin-emu && cp -r Data/Sys /home/ralt/Downloads/RetroArch-Linux-x86_64/RetroArch-Linux-x86_64.AppImage.home/system/dolphin-emu && . /opt/venv/bin/activate && python3 /opt/retroarch/RetroGLCore.py"]
