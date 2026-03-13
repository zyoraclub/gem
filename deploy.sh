#!/bin/bash

# GEM Scraper Deployment Script for Ubuntu (DigitalOcean)
# Domain: gem.zyora.cloud
# Run as: bash deploy.sh

set -e

echo "🚀 GEM Scraper Deployment - gem.zyora.cloud"

# Update system
apt update && apt upgrade -y

# Install Docker
if ! command -v docker &> /dev/null; then
    echo "📦 Installing Docker..."
    curl -fsSL https://get.docker.com | sh
    systemctl enable docker
    systemctl start docker
fi

# Install Docker Compose
if ! command -v docker-compose &> /dev/null; then
    echo "📦 Installing Docker Compose..."
    apt install -y docker-compose
fi

# Create ssl directory (for future HTTPS)
mkdir -p /opt/gem/ssl

cd /opt/gem

echo "✅ Setup complete"
echo ""
echo "📋 Deploy steps:"
echo "1. Upload code: scp -r gem/ root@YOUR_IP:/opt/"
echo "2. Copy client_secrets.json to /opt/gem/backend/"
echo "3. Run: cd /opt/gem && docker-compose up -d --build"
echo ""
echo "🌐 Access: http://gem.zyora.cloud"
echo ""
echo "🔧 Commands:"
echo "   Start:   docker-compose up -d"
echo "   Stop:    docker-compose down"
echo "   Logs:    docker-compose logs -f"
echo "   Rebuild: docker-compose up -d --build"
