#!/bin/bash
# HouseHunters Deployment Script
# Run this from /opt/househunters/app after cloning the repo

set -e

echo "=== HouseHunters Deployment Script ==="

# Update system
echo "Updating system packages..."
apt update && apt upgrade -y

# Install required packages
echo "Installing required packages..."
apt install -y python3 python3-pip python3-venv nginx certbot python3-certbot-nginx

# Navigate to app directory
cd /opt/househunters/app

# Create virtual environment
echo "Creating Python virtual environment..."
python3 -m venv venv
source venv/bin/activate

# Install Python dependencies
echo "Installing Python dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

# Create data directory
mkdir -p /opt/househunters/app/data

# Set up systemd service
echo "Setting up systemd service..."
cp /opt/househunters/app/deploy/househunters.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable househunters
systemctl start househunters

echo ""
echo "=== Deployment complete! ==="
echo ""
echo "Next steps:"
echo "1. cp deploy/nginx.conf /etc/nginx/sites-available/househunters"
echo "2. ln -s /etc/nginx/sites-available/househunters /etc/nginx/sites-enabled/"
echo "3. nginx -t && systemctl reload nginx"
echo "4. certbot --nginx -d search.househunters.online"
echo ""
echo "Check service status: systemctl status househunters"
echo "View logs: journalctl -u househunters -f"
