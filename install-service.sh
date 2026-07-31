# Edit the service file to set the correct path
mkdir -p ~/.config/systemd/user/
cp lily58-manager.service ~/.config/systemd/user/

# Enable and start the service
systemctl --user daemon-reload
systemctl --user enable lily58-manager.service
systemctl --user start lily58-manager.service