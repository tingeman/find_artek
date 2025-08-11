#!/bin/bash

# Configure git for this container
git config --global user.email "thin@dtu.dk"
git config --global user.name "Thomas Ingeman-Nielsen"
git config --global --add safe.directory /workspace

# Create symbolic links for thumbnail generation scripts
echo "Creating symbolic links for thumbnail generation scripts..."
sudo ln -sf /workspace/scripts/generate_thumbnails_cron.sh /usr/local/bin/generate_thumbnails_cron.sh
sudo ln -sf /workspace/scripts/setup_cron.sh /usr/local/bin/setup_cron.sh
sudo ln -sf /workspace/scripts/docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
echo "Symbolic links created successfully!"

# Make scripts executable (in case they're not)
chmod +x /workspace/scripts/*.sh

# Set up Django environment to use the mounted code
echo "Setting up Django environment..."
echo "Django will run from: /workspace/app-main"
echo "Virtual environment available at: /usr/src/venv/bin/python"

# Optional: Install any new requirements if requirements.txt changed
# Uncomment the lines below if you want automatic requirements installation
# cd /workspace/app-main
# if [ -f requirements.txt ]; then
#     echo "Installing/updating Python requirements..."
#     /usr/src/venv/bin/pip install -r requirements.txt
# fi

echo "DevContainer setup completed!"
echo "To run Django development server:"
echo "  cd /workspace/app-main"
echo "  python manage.py runserver 0.0.0.0:8099 --settings find_artek.development_settings"
echo "Thumbnail generation scripts are now available at:"
echo "  /usr/local/bin/generate_thumbnails_cron.sh [height]"
echo "  ./scripts/generate_thumbnails_cron.sh [height]"
