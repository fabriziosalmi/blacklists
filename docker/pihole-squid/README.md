# PiHole-Squid docker image

## How to use

1. Clone the repo and cd to this folder
   
    `git clone https://github.com/fabriziosalmi/blacklists/tree/main --depth 1 && cd docker/pihole-squid`

2. Run `docker-compose up -d` to start both containers

3. Setup blacklist on PiHole via admin console

    Login to the Pi-hole admin console:
    - Go to `Group Management` -> `Adlists`.
    - Add `https://github.com/fabriziosalmi/blacklists/releases/download/latest/blacklist.txt` as a new list.
    
5. Update Gravity Daily

    To update Pi-hole's blocklists daily (which is essentially running `pihole -g` daily):
    
    ```bash
    echo "0 0 * * * root /usr/local/bin/pihole -g" | sudo tee -a /etc/cron.d/pihole
    ```
    
    _This cron job will cause Pi-hole to update its blocklists daily at midnight._
  
7. Setup your clients to use PiHole DNS service (`$IP_PIHOLE:UDP53`) and browers (and automated clients like curl or wget) to use Squid proxy (`$IP_SQUID:TCP3128`) as outgoing proxy
