# Documentation

Navigate quickly:
- [Generating the blacklist](#generating-the-blacklist)
- [Downloading the blacklist](#downloading-the-blacklist)
- [Implementing the blacklist](#implementing-the-blacklist)
- [Integrate your whitelist](#integrate-your-whitelist)
- [Blacklist mirror](#docker)

## Generating the blacklist 

I utilize the capabilities of ChangeDetection ([selfhosted](https://changedetection.io/)) to monitor and merge updates from curated [blacklists](https://github.com/fabriziosalmi/blacklists/blob/main/blacklists.fqdn.urls). GitHub Actions automate the download of these blacklists every hour, consolidating them into a single file.

Furthermore, I conduct regular [reviews](https://github.com/fabriziosalmi/blacklists/blob/main/docs/blacklists_reviews.md) to scrutinize the source blacklists, ensuring the accuracy and relevance of the information through whitelist updates.

## Downloads
- Pi-Hole, AdGuard, uBlock Origin, Squid: **[blacklist.txt](https://github.com/fabriziosalmi/blacklists/releases/download/latest/blacklist.txt)** 
- Unbound: **[unbound_blacklist.txt](https://github.com/fabriziosalmi/blacklists/releases/download/latest/unbound_blacklist.txt)** 
- Bind (rpz): **[rpz_blacklist.txt](https://github.com/fabriziosalmi/blacklists/releases/download/latest/rpz_blacklist.txt)** 
```
https://get.domainsblacklists.com/blacklist.txt
```

## Implementing the Blacklist

Guides for various platforms:

### [PiHole](https://pi-hole.net/)
1. Navigate to **Adlists**
2. Click **Add new adlist** and input:
```
https://github.com/fabriziosalmi/blacklists/releases/download/latest/blacklist.txt
```
3. Go to **Tools > Update Gravity** and select the **Update** button.

### [AdGuard Home](https://adguard.com/it/adguard-home/overview.html)
1. Navigate to **Filters**
2. Select **Add Blacklist** 
3. Input the following URL and save:
```
https://get.domainsblacklists.com/blacklist.txt
```

### [Squid](http://www.squid-cache.org/)

#### Squid configuration for blacklist

1. **Download and copy the blacklist to the squid folder**
```
wget -O blacklist.txt https://github.com/fabriziosalmi/blacklists/releases/download/latest/blacklist.txt
cp blacklist.txt /etc/squid/conf.d/blacklist.txt
```
2. **/etc/squid/squid.conf additional configuration**
```
acl blacklist dstdomain /etc/squid/conf.d/blacklist.txt     # <= blacklist location
http_access deny blacklist                                  # <= deny acl
```
3. **Restart squid**
4. **Setup a cronjob to automatically update the blacklist**

#### Squid configuration for block direct ip requests

If you're using Squid as an outgoing proxy and want to block direct IP requests (both HTTP and HTTPS) while only allowing client requests with host headers, you can achieve this by adding specific access control lists (ACLs) and http_access rules in your Squid configuration.

Here are the steps to configure Squid to achieve this:

1. **Edit the Squid Configuration File**:

Open the Squid configuration file (`squid.conf`) in a text editor:

```bash
sudo nano /etc/squid/squid.conf
```

2. **Define ACLs for Requests with Host Headers**:

Define an ACL for requests that have host headers:

```bash
acl with_host_header dstdomain . # Matches requests with a domain name
acl ip_request dstdom_regex ^\d+\.\d+\.\d+\.\d+$ # Matches requests with IP addresses
```

3. **Block Direct IP Requests**:

Now, allow requests with host headers while denying those with direct IP addresses:

```bash
http_access deny ip_request
http_access allow with_host_header
```

4. **Other Required Access Controls**:

You'll probably have other `http_access` lines in your configuration for various rules. Make sure that the order of these rules does not conflict with the rules you just added. In Squid, the first matching rule wins, so more specific rules should come before more general ones.

5. **Save and Restart Squid**:

After making these changes, save the configuration file and restart Squid to apply the changes:

```bash
sudo systemctl restart squid
```

With these changes, Squid will deny requests made directly to IP addresses and will only allow requests with host headers. Ensure you test the configuration after applying the changes to make sure it works as intended and to identify if there are any other conflicting rules.


---
### How to implement the RPZ Blacklist with [BIND9](https://www.isc.org/bind/)

1. **Download the RPZ blacklist**: 
   
   Navigate to the repository and download the [latest RPZ release](https://github.com/fabriziosalmi/blacklists/releases/download/latest/rpz_blacklist.txt) 

2. **Configure BIND9**:

   Edit your BIND configuration (often `named.conf` or `named.conf.local`):

   ```bash
   nano /etc/bind/named.conf.local
   ```

   Add the following lines:

   ```bash
   zone "rpz.blacklist" {
       type master;
       file "/path/to/your/rpz_blacklist.txt";
   };

   options {
       response-policy { zone "rpz.blacklist"; };
   };
   ```

   Ensure you replace `/path/to/your/` with the actual path to the `rpz_blacklist.txt` file.

4. **Reload BIND**:

   ```bash
   sudo systemctl reload bind9
   ```

   This will load the new RPZ blacklist, and BIND will start blocking the domains listed in it.



--- 


### Linux, Windows, OSX and any device with a browser able to install the [uBlock Origin](https://github.com/gorhill/uBlock#ublock-origin) extension

1. Open the browser and go to the uBlock Origin dashboard by clicking on the extension icon > settings icon
2. Go to the end of the page and in the Import form paste this url
```
https://get.domainsblacklists.com/blacklist.txt
```
3. Click on the Apply Changes button in the top of the page
4. You will find the blacklist in the Custom list at the end of the page, before the Import form
5. You can force blacklist refresh from the same page when needed

## Integrate your Whitelist

For public domain whitelisting, [submit your whitelist](https://req.domainsblacklists.com). For private whitelisting, use the provided script along with a `whitelist.txt` file.

## Docker

Use our [Docker image](https://hub.docker.com/repository/docker/fabriziosalmi/blacklists/) to deploy your own blacklist mirror:

```bash
docker pull fabriziosalmi/blacklists:latest
docker run -p 80:80 fabriziosalmi/blacklists
```

Access the blacklist at `http://$DOCKER_IP/blacklist.txt`. Restart the container to refresh the blacklist.
