#!/bin/bash

SERVICE_NAME="forensic-host-api"
PROXY_PATH="/home/owner/Documents/00bfdfea-497d-499d-a5a3-84a711c230e6/repo/host_api_proxy.py"
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"

echo "Creating systemd service..."

sudo cat > "$SERVICE_FILE" << 'UNIT_EOF'
[Unit]
Description=Forensic Host API Proxy
After=network.target docker.service

[Service]
Type=simple
User=root
WorkingDirectory=/home/owner/Documents/00bfdfea-497d-499d-a5a3-84a711c230e6/repo
ExecStart=/usr/bin/python3 /home/owner/Documents/00bfdfea-497d-499d-a5a3-84a711c230e6/repo/host_api_proxy.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
UNIT_EOF

# Reload systemd and enable the service
sudo systemctl daemon-reload
sudo systemctl enable "$SERVICE_NAME"
sudo systemctl start "$SERVICE_NAME"

echo "✅ Persistent service '$SERVICE_NAME' created and started."
echo "   It will now automatically start on boot."
