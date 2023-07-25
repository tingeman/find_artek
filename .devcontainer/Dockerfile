FROM python:3.10

# Set the working directory
RUN mkdir -p /usr/src/app/find_artek
WORKDIR /usr/src/app/find_artek


##################### LOCALE #####################

# Add these lines after the LABEL directive to set the locale
RUN apt-get update && apt-get install -y locales && \
    sed -i -e 's/# en_US.UTF-8 UTF-8/en_US.UTF-8 UTF-8/' /etc/locale.gen && \
    sed -i -e 's/# da_DK.UTF-8 UTF-8/da_DK.UTF-8 UTF-8/' /etc/locale.gen && \
    locale-gen

ENV LANG en_US.UTF-8
ENV LANGUAGE en_US.UTF-8
ENV LC_ALL da_DK.UTF-8


##################### LOCALE #####################

# Update package list and install necessary packages
RUN apt-get update && \
    apt-get install -y gdal-bin libgdal-dev libsqlite3-mod-spatialite

# Install Python virtual environment
RUN apt-get update && apt-get install -y python3-venv

# Install LDAP libraries
RUN apt-get update && apt-get install -y libsasl2-dev python-dev-is-python3 libldap2-dev libssl-dev

# Install tree
RUN apt-get update && apt-get install -y tree

# Activate virtual environment
ENV VIRTUAL_ENV=/usr/src/app/find_artek/venv
ENV PATH="$VIRTUAL_ENV/bin:$PATH"


RUN python3 -m venv $VIRTUAL_ENV
RUN /bin/bash -c "source $VIRTUAL_ENV/bin/activate"


