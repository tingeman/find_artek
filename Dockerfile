FROM python:3.12-slim

# Default arguments for user creation
ARG USERNAME=dockeruser
ARG USER_UID=30000
ARG USER_GID=$USER_UID

# Create the plotly user with UID 30000
RUN adduser --disabled-password --home /home/$USERNAME --uid $USER_UID $USERNAME

# Set the default user
USER root

# Install packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    unixodbc \
    locales \
    wget \
    gnupg2 \
    iputils-ping \
    tree \
    gosu \
    sudo \
    bash \
    nano \
    mariadb-client \
    libmariadb-dev \
    pkg-config \
    gdal-bin libgdal-dev \
    build-essential \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Configure and generate the en_US.UTF-8 locale
RUN sed -i -e 's/# en_US.UTF-8 UTF-8/en_US.UTF-8 UTF-8/' /etc/locale.gen && \
    dpkg-reconfigure --frontend=noninteractive locales && \
    update-locale LC_ALL=en_US.UTF-8

ENV LC_ALL=en_US.UTF-8
ENV LANG=en_US.UTF-8
ENV LANGUAGE=en_US.UTF-8

# Allow the non-root user to use sudo without password
RUN echo "$USERNAME ALL=(ALL) NOPASSWD:ALL" >> /etc/sudoers

# Create project directories and set permissions
RUN mkdir -p /app \
    && chown $USER_UID:$USER_GID /app \
    && chmod -R 755 /app 

# Switch to the non-root user
USER $USERNAME
    
# Set the working directory to the project directory
WORKDIR /app

# We have to use a virtual environment in this particular case
# installing gunicorn and django using pip directly did not work

# Create a virtual environment
RUN python -m venv venv

# Copy requirements file and install
COPY --chown=$USERNAME:$USERNAME ./app-main/requirements.txt .

# Install the dependencies
RUN set -ex && \
    . /app/venv/bin/activate && \
    python -m pip install --no-cache-dir -r /app/requirements.txt

# Add the virtual environment to PATH
ENV PATH="/app/venv/bin:$PATH"

# Copy the project files
COPY --chown=$USERNAME:$USERNAME ./app-main /app

#EXPOSE 8099
# Start Gunicorn to serve the Django app
CMD ["gunicorn", "--bind", "0.0.0.0:8099", "find_artek.wsgi:application"]