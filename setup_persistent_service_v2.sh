#!/bin/bash

SERVICE_NAME="forensic-host-api"
PROXY_PATH="/home/owner/Documents/00bfdfea-497d-499d-a5a3-84a711c230e6/repo/host_api_proxy.py"
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"

echo "=== STEP 1: Creating systemd service file (using sudo tee) ==="
sudo tee "$SERVICE_FILE" > /dev/null << 'UNIT_EOF'
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

if [ -f "$SERVICE_FILE" ]; then
    echo "✅ Service file created at $SERVICE_FILE"
else
    echo "❌ ERROR: Failed to create service file. Check sudo permissions."
    exit 1
fi

echo ""
echo "=== STEP 2: Reload, Enable, and Start the Service ==="
sudo systemctl daemon-reload
sudo systemctl enable "$SERVICE_NAME"
sudo systemctl start "$SERVICE_NAME"

echo ""
echo "=== STEP 3: Verify the Service is Running ==="
sleep 3
if sudo systemctl is-active --quiet "$SERVICE_NAME"; then
    echo "✅ Service '$SERVICE_NAME' is ACTIVE and running."
    echo "   It will now automatically start on boot."
else
    echo "❌ Service failed to start. Checking logs..."
    sudo systemctl status "$SERVICE_NAME" --no-pager | tail -n 20
fi
