# Base image: python 3.12.16-slim-bookworm, pinned by digest (provisional, until the host
# baseline T0 confirms the Python version production runs). A release build (build_image.sh)
# builds without --build-arg, so this default is what releases use. It must equal
# FA_PYTHON_IMAGE in compose.pins.env: change both together.
#
# Stages:
#   build    compiles the Python packages (mysqlclient needs gcc and libmariadb-dev) into
#            the venv /app/venv. Compilers and -dev packages stay in this stage.
#   runtime  the production image without CMD/HEALTHCHECK: run-time libraries, user
#            dockeruser (uid/gid 30000), the venv, the app, the entrypoint and cron scripts.
#   dev      runtime + compilers, -dev packages and admin tools; CMD /bin/bash.
#            Used by docker-compose.develop.yml (target: dev) and .devcontainer.
#   prod     runtime + HEALTHCHECK + the gunicorn CMD. Must stay the LAST stage: a plain
#            `docker build .` (build_image.sh) builds the last stage, so a release never
#            contains the dev tools.
ARG PYTHON_IMAGE=python:3.12.16-slim-bookworm@sha256:935c3c5b12357a7e10caa9c1e6ca5692344d97cf229832ef584be2cec9fc03df


# ---- build: compile the venv ---------------------------------------------------------------
FROM ${PYTHON_IMAGE} AS build

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    pkg-config \
    libmariadb-dev \
    && rm -rf /var/lib/apt/lists/*

# The venv is created at its final path (/app/venv): venvs are not relocatable.
COPY ./app-main/requirements.txt /tmp/requirements.txt
RUN set -ex && \
    python -m venv /app/venv && \
    /app/venv/bin/python -m pip install --no-cache-dir -r /tmp/requirements.txt


# ---- runtime: what the app needs at run time -----------------------------------------------
FROM ${PYTHON_IMAGE} AS runtime

# Default arguments for user creation
ARG USERNAME=dockeruser
ARG USER_UID=30000
ARG USER_GID=$USER_UID

# Create the app user with UID 30000
RUN adduser --disabled-password --home /home/$USERNAME --uid $USER_UID $USERNAME

USER root

# Run-time packages only:
#   libmariadb3   client library for mysqlclient
#   gdal-bin      GDAL (with GEOS and PROJ) for django.contrib.gis
#   poppler-utils pdftoppm/pdfinfo for pdf2image (thumbnails)
#   cron, sudo    thumbnail cron job (the entrypoint starts the cron daemon through sudo)
#   curl          HEALTHCHECK
#   locales       en_US.UTF-8
RUN apt-get update && apt-get install -y --no-install-recommends \
    libmariadb3 \
    gdal-bin \
    poppler-utils \
    cron \
    sudo \
    curl \
    locales \
    && rm -rf /var/lib/apt/lists/*

# Configure and generate the en_US.UTF-8 locale
RUN sed -i -e 's/# en_US.UTF-8 UTF-8/en_US.UTF-8 UTF-8/' /etc/locale.gen && \
    dpkg-reconfigure --frontend=noninteractive locales && \
    update-locale LC_ALL=en_US.UTF-8

ENV LC_ALL=en_US.UTF-8
ENV LANG=en_US.UTF-8
ENV LANGUAGE=en_US.UTF-8

# Copy and set up the entrypoint script
COPY --chown=root:root ./scripts/docker-entrypoint.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

# Thumbnail cron job, as monitoring_db: the job file in /etc/cron.d (owner root, mode 0644,
# runs as dockeruser) and the script it runs. Active only when the entrypoint starts the cron
# daemon (ENABLE_CRON=true). The job loads the container env from /proc/1/environ and writes
# to PID 1's stdout/stderr (docker logs); see the two files.
COPY --chown=root:root ./docker/cron/find_artek_thumbnails /etc/cron.d/find_artek_thumbnails
COPY --chown=root:root ./scripts/generate_thumbnails_cron.sh /usr/local/bin/
RUN chmod 0644 /etc/cron.d/find_artek_thumbnails     && chmod 0755 /usr/local/bin/generate_thumbnails_cron.sh

# Allow the non-root user to use sudo without password (cron is started through sudo, as in
# monitoring_db; dropping sudo is a cross-repo item, FA-R24)
RUN echo "$USERNAME ALL=(ALL) NOPASSWD:ALL" >> /etc/sudoers

# Create project directories and set permissions
RUN mkdir -p /app \
    && chown $USER_UID:$USER_GID /app \
    && chmod -R 755 /app

# The venv compiled in the build stage, owned by the app user (as before)
COPY --from=build --chown=$USER_UID:$USER_GID /app/venv /app/venv

# Switch to the non-root user
USER $USERNAME

# Set the working directory to the project directory
WORKDIR /app

# Add the virtual environment to PATH
ENV PATH="/app/venv/bin:$PATH"

# Set environment variable for Django project location
ENV DJANGO_PROJECT_DIR="/app"

# Copy the project files
COPY --chown=$USERNAME:$USERNAME ./app-main /app

# Set the entrypoint
ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]


# ---- dev: runtime + compilers, -dev packages and admin tools -------------------------------
FROM runtime AS dev
USER root
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    pkg-config \
    libmariadb-dev \
    libgdal-dev \
    mariadb-client \
    unixodbc \
    wget \
    gnupg2 \
    iputils-ping \
    tree \
    gosu \
    nano \
    net-tools \
    mc \
    && rm -rf /var/lib/apt/lists/*
USER dockeruser
CMD ["/bin/bash"]


# ---- prod: the release image. Must be the LAST stage (see the top of this file). -----------
FROM runtime AS prod
# gunicorn sees paths without the /find prefix (nginx strips it); 127.0.0.1 is in
# ALLOWED_HOSTS. The front page needs the database, so healthy means app + DB answer.
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD ["curl", "-fsS", "-o", "/dev/null", "http://127.0.0.1:8099/publications/frontpage/"]
# Start Gunicorn to serve the Django app
CMD ["gunicorn", "--bind", "0.0.0.0:8099", "find_artek.wsgi:application", "--log-level", "debug", "--access-logfile", "-", "--error-logfile", "-"]
