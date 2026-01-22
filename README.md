# HouseHunters

A property search tool that queries Zillow listings with advanced filtering, mortgage calculations, and export capabilities.

## Features

- **For Sale & For Rent** search support
- **Filters**: Property type, beds, baths, price, year built
- **Mortgage Calculator**: Down payment, APR, loan term, taxes, insurance
- **Sortable Results Table** with customizable columns
- **Export**: JSON and CSV formats
- **Auto-detect** search type from Zillow URL

## Local Development

### Prerequisites

- Python 3.10+
- pip

### Setup

```bash
cd app

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run the server
uvicorn main:app --reload --port 5122
```

Visit http://localhost:5122

## Deployment (Ubuntu/Debian Server)

### 1. DNS Setup

Point your domain to your server IP. For example, in Porkbun:

| Type | Host | Answer |
|------|------|--------|
| A | search | YOUR_SERVER_IP |

### 2. Clone Repository

```bash
ssh root@YOUR_SERVER_IP

# Install git if needed
apt update && apt install -y git

# Clone the repo
git clone https://github.com/YOUR_USERNAME/househunters.git /opt/househunters
cd /opt/househunters/app
```

### 3. Run Setup Script

```bash
chmod +x deploy/setup.sh
./deploy/setup.sh
```

This will:
- Install Python, nginx, certbot
- Create virtual environment
- Install dependencies
- Set up systemd service

### 4. Configure Nginx

```bash
# Copy nginx config
cp deploy/nginx.conf /etc/nginx/sites-available/househunters

# Enable site
ln -s /etc/nginx/sites-available/househunters /etc/nginx/sites-enabled/

# Remove default site (optional)
rm -f /etc/nginx/sites-enabled/default

# Test and reload
nginx -t && systemctl reload nginx
```

### 5. Get SSL Certificate

```bash
certbot --nginx -d search.househunters.online
```

### 6. Verify

Visit https://search.househunters.online

## Useful Commands

```bash
# Check service status
systemctl status househunters

# View logs
journalctl -u househunters -f

# Restart service
systemctl restart househunters

# Update from GitHub
cd /opt/househunters && git pull && systemctl restart househunters
```

## Project Structure

```
househunters/
├── app/
│   ├── main.py              # FastAPI backend
│   ├── zillow.py            # Zillow API wrapper
│   ├── requirements.txt     # Python dependencies
│   ├── static/
│   │   ├── css/style.css    # Styling
│   │   └── js/app.js        # Frontend logic
│   ├── templates/
│   │   └── index.html       # Main page
│   ├── data/                # Saved searches
│   └── deploy/
│       ├── setup.sh         # Server setup script
│       ├── nginx.conf       # Nginx configuration
│       └── househunters.service  # Systemd service
└── README.md
```

## License

MIT
