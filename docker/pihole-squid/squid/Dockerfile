# Use the latest version of Ubuntu as a base
FROM ubuntu:latest

# Set environment variables for non-interactive apt installations
ENV DEBIAN_FRONTEND=non-interactive

# Update system packages, install necessary tools, and clean up
RUN apt-get update && \
    apt-get install -y \
    cron \
    squid \
    wget && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Setup Squid
COPY squid.conf /etc/squid/squid.conf

# Script to update blacklists
COPY update_blacklist.sh /usr/local/bin/update_blacklist.sh
RUN chmod +x /usr/local/bin/update_blacklist.sh

# Add to cron for daily updates
RUN (echo "0 0 * * * /usr/local/bin/update_blacklist.sh") | crontab -

EXPOSE 3128
