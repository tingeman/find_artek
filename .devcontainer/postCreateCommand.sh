#!/bin/bash

# cd ./app and remove venv if it exits, then rebuild venv, activate it, and install requirements
# pwd && cd app-main && ls && rm -rf venv && python3 -m venv venv && source venv/bin/activate && pip install --upgrade pip && pip install -r requirements.txt

git config --global user.email "thin@dtu.dk"
git config --global user.name "Thomas Ingeman-Nielsen"
git config --global --add safe.directory /usr/src/project

# Create symbolic links for thumbnail generation scripts
echo "Creating symbolic links for thumbnail generation scripts..."
sudo ln -sf /usr/src/project/scripts/generate_thumbnails_cron.sh /usr/local/bin/generate_thumbnails_cron.sh
sudo ln -sf /usr/src/project/scripts/setup_cron.sh /usr/local/bin/setup_cron.sh
sudo ln -sf /usr/src/project/scripts/docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
echo "Symbolic links created successfully!"

# Make scripts executable (in case they're not)
chmod +x /usr/src/project/scripts/*.sh

echo "DevContainer setup completed!"
echo "Thumbnail generation scripts are now available at:"
echo "  /usr/local/bin/generate_thumbnails_cron.sh [height]"
echo "  ./scripts/generate_thumbnails_cron.sh [height]"
