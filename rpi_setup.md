# Raspberry Pi Setup Guide for BikeBridge

## 1. Running as a Background Service (Systemd)

To ensure `bike_emulator.py` runs automatically when the Raspberry Pi boots and stays running, use **Systemd**.

### Step 1: Create the Service File

Create a file named `bikebridge.service` in `/etc/systemd/system/`:

```bash
sudo nano /etc/systemd/system/bikebridge.service
```

Paste the following content.
**Note on Virtual Environments:** In systemd, we don't `source activate`. Instead, we point `ExecStart` directly to the python executable *inside* the venv.

```ini
[Unit]
Description=BikeBridge Emulator Service
After=network.target bluetooth.target
Requires=bluetooth.target

[Service]
User=pi
Group=pi

# Your project directory
WorkingDirectory=/home/pi/projects/bike

# Point directly to the python binary inside your venv
# This automatically uses the libraries installed in that venv
ExecStart=/home/pi/projects/bike/venv/bin/python /home/pi/projects/bike/bike_emulator.py

# Restart automatically if it crashes
Restart=always
RestartSec=5

# Ensure python logs are output immediately
Environment=PYTHONUNBUFFERED=1
# If you need specific environment variables, add them here
# Environment=PATH=/home/pi/projects/bike/venv/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin

[Install]
WantedBy=multi-user.target
```

### Step 2: Enable and Start the Service

Reload systemd to recognize the new file:
```bash
sudo systemctl daemon-reload
```

Enable the service to start on boot:
```bash
sudo systemctl enable bikebridge
```

Start the service immediately:
```bash
sudo systemctl start bikebridge
```

Check the status to ensure it's running:
```bash
sudo systemctl status bikebridge
```

View logs:
```bash
sudo journalctl -u bikebridge -f
```

---

## 2. Integrating with Apache (httpd)

You asked if you can start it with `httpd` (Apache). 
`bike_emulator.py` runs its own built-in web server (Flask) on port **5000**. `httpd` typically runs on port **80**.

Because `bike_emulator.py` needs to run a continuous loop for Bluetooth, it cannot be run as a standard CGI script by Apache. However, you can use Apache as a **Reverse Proxy**. This allows you to access the interface at `http://your-rpi-ip/` instead of `http://your-rpi-ip:5000/`.

### Step 1: Enable Proxy Modules
```bash
sudo a2enmod proxy
sudo a2enmod proxy_http
sudo systemctl restart apache2
```

### Step 2: Configure Virtual Host
Edit your site configuration (e.g., `/etc/apache2/sites-available/000-default.conf`):

```apache
<VirtualHost *:80>
    ServerAdmin webmaster@localhost
    DocumentRoot /var/www/html

    # Proxy configuration for BikeBridge
    ProxyPreserveHost On
    ProxyPass / http://127.0.0.1:5000/
    ProxyPassReverse / http://127.0.0.1:5000/

    ErrorLog ${APACHE_LOG_DIR}/error.log
    CustomLog ${APACHE_LOG_DIR}/access.log combined
</VirtualHost>
```

### Step 3: Restart Apache
```bash
sudo systemctl restart apache2
```

Now you can access the bike controls by visiting the Pi's IP address directly, while `systemd` keeps the actual python process running in the background.
