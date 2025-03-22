#!/bin/bash

# Fetch the latest blacklist for Squid
wget -O /etc/squid/conf.d/blacklist.txt https://github.com/fabriziosalmi/blacklists/releases/download/latest/blacklist.txt

# Restart squid to apply the changes
service squid restart
