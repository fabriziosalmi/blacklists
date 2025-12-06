# DevOps Guide

This guide covers deployment, automation, and operational aspects of the Blacklists project.

---

## 🤖 Blacklist Automation

### Daily Generation Workflow

The blacklist is automatically generated **daily at midnight UTC** using GitHub Actions. This schedule balances freshness with cost-effectiveness.

**Workflow Schedule:**
- **00:00 UTC**: Generate and publish blacklist (`release.yml`)
- **01:00 UTC**: Update statistics and README (`daily-stats.yml`)

**Why Daily Instead of Hourly?**

1. **Cost Efficiency**: Reduces GitHub Actions usage by 96% (24 runs/day → 1 run/day)
2. **Sustainability**: Keeps the service free and accessible to everyone
3. **Sufficient Protection**: Most threats remain active for days/weeks
4. **Resource Optimization**: Reduces bandwidth and processing overhead

**Workflow Files:**
- `.github/workflows/release.yml` - Main blacklist generation
- `.github/workflows/daily-stats.yml` - Statistics and README updates

### Manual Triggering

To trigger workflows manually:

```bash
# Using GitHub CLI
gh workflow run release.yml
gh workflow run daily-stats.yml

# Or via GitHub web interface:
# Actions → Select workflow → Run workflow
```

### Monitoring Workflows

Check workflow status:

```bash
# List recent runs
gh run list --workflow=release.yml --limit 10

# View specific run
gh run view <run-id>

# Watch live
gh run watch
```

---

## 📋 Website Deployment Options

- [GitHub Pages](#github-pages) - Free, simple, recommended
- [Netlify](#netlify) - Free tier, automatic deployments
- [Vercel](#vercel) - Fast, edge network
- [Cloudflare Pages](#cloudflare-pages) - Global CDN
- [Custom Server](#custom-server) - Full control

---

## 🌐 GitHub Pages

### Automatic Deployment (Recommended)

**Step 1: Enable GitHub Pages**
1. Go to repository **Settings**
2. Scroll to **Pages** section
3. Source: **Deploy from a branch**
4. Branch: `main`
5. Folder: `/docs`
6. Click **Save**

**Step 2: Wait for Deployment**
- First deployment takes 1-2 minutes
- Site will be available at: `https://fabriziosalmi.github.io/blacklists/`

**Step 3: Custom Domain (Optional)**
1. Add CNAME file to `/docs`:
   ```bash
   echo "your-domain.com" > docs/CNAME
   ```
2. Configure DNS:
   ```
   Type: CNAME
   Name: www (or @)
   Value: fabriziosalmi.github.io
   ```
3. In GitHub Settings → Pages:
   - Enter custom domain
   - Enable "Enforce HTTPS"

### GitHub Actions Workflow

For more control, use GitHub Actions:

**Create `.github/workflows/deploy.yml`:**

```yaml
name: Deploy to GitHub Pages

on:
  push:
    branches: [ main ]
    paths:
      - 'docs/**'
  workflow_dispatch:

permissions:
  contents: read
  pages: write
  id-token: write

concurrency:
  group: "pages"
  cancel-in-progress: false

jobs:
  deploy:
    environment:
      name: github-pages
      url: ${{ steps.deployment.outputs.page_url }}
    runs-on: ubuntu-latest
    steps:
      - name: Checkout
        uses: actions/checkout@v4
      
      - name: Setup Pages
        uses: actions/configure-pages@v4
      
      - name: Upload artifact
        uses: actions/upload-pages-artifact@v3
        with:
          path: './docs'
      
      - name: Deploy to GitHub Pages
        id: deployment
        uses: actions/deploy-pages@v4
```

**Enable Workflow:**
1. Settings → Pages
2. Source: **GitHub Actions**
3. Commit workflow file
4. Automatic deployment on push

---

## 🔥 Netlify

### Quick Deploy

**Method 1: Drag & Drop**
1. Go to [Netlify Drop](https://app.netlify.com/drop)
2. Drag `/docs` folder
3. Site deployed instantly!

**Method 2: Git Integration**

**Step 1: Connect Repository**
1. [Sign up on Netlify](https://app.netlify.com/signup)
2. Click **Add new site** → **Import an existing project**
3. Connect to GitHub
4. Select `fabriziosalmi/blacklists` repository

**Step 2: Configure Build**
```
Build command: (leave empty)
Publish directory: docs
```

**Step 3: Deploy**
- Click **Deploy site**
- Get URL: `https://random-name.netlify.app`

**Step 4: Custom Domain**
1. Domain settings → Add custom domain
2. Follow DNS instructions
3. Enable HTTPS (automatic)

### Netlify Configuration File

Create `netlify.toml` in project root:

```toml
[build]
  publish = "docs"
  command = ""

[[redirects]]
  from = "/*"
  to = "/index.html"
  status = 200

[build.environment]
  NODE_VERSION = "18"

[[headers]]
  for = "/*"
  [headers.values]
    X-Frame-Options = "DENY"
    X-XSS-Protection = "1; mode=block"
    X-Content-Type-Options = "nosniff"
    Referrer-Policy = "strict-origin-when-cross-origin"

[[headers]]
  for = "/*.css"
  [headers.values]
    Cache-Control = "public, max-age=31536000, immutable"

[[headers]]
  for = "/*.js"
  [headers.values]
    Cache-Control = "public, max-age=31536000, immutable"
```

### Netlify CLI

```bash
# Install CLI
npm install -g netlify-cli

# Login
netlify login

# Deploy
netlify deploy --dir=docs --prod

# Or initialize for automatic deployments
netlify init
```

---

## ▲ Vercel

### Deploy with Vercel

**Step 1: Install Vercel CLI**
```bash
npm install -g vercel
```

**Step 2: Deploy**
```bash
# Navigate to project
cd /path/to/blacklists

# Deploy
vercel --prod

# Follow prompts:
# - Setup and deploy? Yes
# - Which scope? Your account
# - Link to existing project? No
# - Project name? blacklists
# - In which directory is code? ./
# - Override settings? Yes
# - Build command? (leave empty)
# - Output directory? docs
```

**Step 3: Get URL**
```
https://blacklists.vercel.app
```

### Vercel Configuration

Create `vercel.json`:

```json
{
  "version": 2,
  "public": true,
  "cleanUrls": true,
  "trailingSlash": false,
  "outputDirectory": "docs",
  "headers": [
    {
      "source": "/(.*)",
      "headers": [
        {
          "key": "X-Frame-Options",
          "value": "DENY"
        },
        {
          "key": "X-Content-Type-Options",
          "value": "nosniff"
        },
        {
          "key": "X-XSS-Protection",
          "value": "1; mode=block"
        }
      ]
    },
    {
      "source": "/(.*\\.(css|js))",
      "headers": [
        {
          "key": "Cache-Control",
          "value": "public, max-age=31536000, immutable"
        }
      ]
    }
  ]
}
```

### Git Integration

1. Push to GitHub
2. Go to [Vercel Dashboard](https://vercel.com/dashboard)
3. Import Git Repository
4. Configure:
   - Framework Preset: Other
   - Root Directory: `docs`
   - Build Command: (empty)
   - Output Directory: `./`

---

## ☁️ Cloudflare Pages

### Deploy to Cloudflare Pages

**Step 1: Sign Up**
- [Cloudflare Pages](https://pages.cloudflare.com/)

**Step 2: Create Project**
1. Click **Create a project**
2. Connect Git repository
3. Select `fabriziosalmi/blacklists`

**Step 3: Configure Build**
```
Build command: (empty)
Build output directory: docs
Root directory: /
```

**Step 4: Deploy**
- Click **Save and Deploy**
- URL: `https://blacklists.pages.dev`

### Cloudflare Workers (Advanced)

Add edge functions for dynamic features:

**`functions/api/stats.js`:**
```javascript
export async function onRequest(context) {
  // Fetch real-time stats from GitHub API
  const response = await fetch(
    'https://api.github.com/repos/fabriziosalmi/blacklists/releases/latest'
  );
  const data = await response.json();
  
  return new Response(JSON.stringify({
    version: data.tag_name,
    published: data.published_at,
    downloads: data.assets[0]?.download_count || 0
  }), {
    headers: {
      'Content-Type': 'application/json',
      'Cache-Control': 'max-age=300'
    }
  });
}
```

---

## 🖥️ Custom Server

### Apache

**Step 1: Install Apache**
```bash
# Debian/Ubuntu
sudo apt update
sudo apt install apache2

# CentOS/RHEL
sudo yum install httpd
```

**Step 2: Copy Files**
```bash
# Copy website files
sudo cp -r docs/* /var/www/html/

# Set permissions
sudo chown -R www-data:www-data /var/www/html/
sudo chmod -R 755 /var/www/html/
```

**Step 3: Configure Virtual Host**
```bash
sudo nano /etc/apache2/sites-available/blacklists.conf
```

```apache
<VirtualHost *:80>
    ServerName blacklists.yourdomain.com
    DocumentRoot /var/www/html
    
    <Directory /var/www/html>
        Options -Indexes +FollowSymLinks
        AllowOverride All
        Require all granted
    </Directory>
    
    # Compression
    <IfModule mod_deflate.c>
        AddOutputFilterByType DEFLATE text/html text/css text/javascript application/javascript
    </IfModule>
    
    # Caching
    <IfModule mod_expires.c>
        ExpiresActive On
        ExpiresByType text/css "access plus 1 year"
        ExpiresByType application/javascript "access plus 1 year"
        ExpiresByType text/html "access plus 1 hour"
    </IfModule>
    
    # Security headers
    Header always set X-Frame-Options "DENY"
    Header always set X-Content-Type-Options "nosniff"
    Header always set X-XSS-Protection "1; mode=block"
    
    ErrorLog ${APACHE_LOG_DIR}/blacklists-error.log
    CustomLog ${APACHE_LOG_DIR}/blacklists-access.log combined
</VirtualHost>
```

**Step 4: Enable Site**
```bash
# Enable modules
sudo a2enmod rewrite headers expires deflate

# Enable site
sudo a2ensite blacklists

# Test configuration
sudo apache2ctl configtest

# Restart Apache
sudo systemctl restart apache2
```

**Step 5: SSL with Let's Encrypt**
```bash
# Install Certbot
sudo apt install certbot python3-certbot-apache

# Get certificate
sudo certbot --apache -d blacklists.yourdomain.com

# Auto-renewal
sudo certbot renew --dry-run
```

### Nginx

**Step 1: Install Nginx**
```bash
# Debian/Ubuntu
sudo apt install nginx

# CentOS/RHEL
sudo yum install nginx
```

**Step 2: Configure**
```bash
sudo nano /etc/nginx/sites-available/blacklists
```

```nginx
server {
    listen 80;
    server_name blacklists.yourdomain.com;
    root /var/www/blacklists;
    index index.html;
    
    # Security headers
    add_header X-Frame-Options "DENY" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;
    
    # Compression
    gzip on;
    gzip_vary on;
    gzip_types text/css application/javascript text/html;
    gzip_min_length 1000;
    
    # Caching
    location ~* \.(css|js)$ {
        expires 1y;
        add_header Cache-Control "public, immutable";
    }
    
    location ~* \.(html)$ {
        expires 1h;
        add_header Cache-Control "public";
    }
    
    # Main location
    location / {
        try_files $uri $uri/ =404;
    }
    
    # Logs
    access_log /var/log/nginx/blacklists-access.log;
    error_log /var/log/nginx/blacklists-error.log;
}
```

**Step 3: Deploy Files**
```bash
# Create directory
sudo mkdir -p /var/www/blacklists

# Copy files
sudo cp -r docs/* /var/www/blacklists/

# Set permissions
sudo chown -R www-data:www-data /var/www/blacklists/
sudo chmod -R 755 /var/www/blacklists/
```

**Step 4: Enable & Start**
```bash
# Create symlink
sudo ln -s /etc/nginx/sites-available/blacklists /etc/nginx/sites-enabled/

# Test configuration
sudo nginx -t

# Restart Nginx
sudo systemctl restart nginx
```

**Step 5: SSL**
```bash
# Install Certbot
sudo apt install certbot python3-certbot-nginx

# Get certificate
sudo certbot --nginx -d blacklists.yourdomain.com
```

---

## 🔒 Security Best Practices

### HTTPS

**Always use HTTPS for production:**
- GitHub Pages: Automatic
- Netlify/Vercel: Automatic
- Custom server: Use Let's Encrypt

### Security Headers

Ensure these headers are set:

```
X-Frame-Options: DENY
X-Content-Type-Options: nosniff
X-XSS-Protection: 1; mode=block
Referrer-Policy: strict-origin-when-cross-origin
Content-Security-Policy: default-src 'self' https:; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; font-src https://fonts.gstatic.com
```

### Content Security Policy

Add to HTML `<head>`:

```html
<meta http-equiv="Content-Security-Policy" 
      content="default-src 'self' https:; 
               style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; 
               font-src https://fonts.gstatic.com; 
               script-src 'self' 'unsafe-inline';">
```

---

## 📊 Analytics (Optional)

### Plausible Analytics (Privacy-Friendly)

**Add to `<head>` in index.html:**
```html
<script defer data-domain="yourdomain.com" src="https://plausible.io/js/script.js"></script>
```

### Google Analytics

**Add to `<head>`:**
```html
<!-- Google tag (gtag.js) -->
<script async src="https://www.googletagmanager.com/gtag/js?id=G-XXXXXXXXXX"></script>
<script>
  window.dataLayer = window.dataLayer || [];
  function gtag(){dataLayer.push(arguments);}
  gtag('js', new Date());
  gtag('config', 'G-XXXXXXXXXX');
</script>
```

### Cloudflare Web Analytics

**Add before `</body>`:**
```html
<script defer src='https://static.cloudflareinsights.com/beacon.min.js' data-cf-beacon='{"token": "YOUR_TOKEN"}'></script>
```

---

## 🚀 Performance Optimization

### Minification

**Install tools:**
```bash
npm install -g html-minifier clean-css-cli uglify-js
```

**Minify files:**
```bash
# HTML
html-minifier --collapse-whitespace --remove-comments \
  docs/index.html -o docs/index.min.html

# CSS
cleancss -o docs/style.min.css docs/style.css

# JS
uglifyjs docs/script.js -o docs/script.min.js -c -m
```

**Update references in HTML:**
```html
<link rel="stylesheet" href="style.min.css">
<script src="script.min.js"></script>
```

### CDN

Use Cloudflare or similar CDN:
1. Add site to Cloudflare
2. Point DNS to Cloudflare nameservers
3. Enable caching and optimization
4. Configure page rules

---

## 🔄 Continuous Deployment

### Automatic Updates

**GitHub Actions for auto-deploy on push:**

Already covered in [GitHub Pages](#github-actions-workflow) section.

**Webhook for custom server:**

```bash
# Create webhook endpoint
sudo nano /var/www/webhook/deploy.php
```

```php
<?php
$secret = 'YOUR_SECRET_KEY';
$payload = file_get_contents('php://input');
$signature = hash_hmac('sha256', $payload, $secret);

if (hash_equals('sha256=' . $signature, $_SERVER['HTTP_X_HUB_SIGNATURE_256'])) {
    shell_exec('cd /var/www/blacklists && git pull origin main 2>&1');
    echo 'Deployed successfully';
} else {
    http_response_code(403);
    echo 'Invalid signature';
}
```

Configure webhook in GitHub repository settings.

---

## 📝 Deployment Checklist

Before going live:

- [ ] Test all links and buttons
- [ ] Verify responsive design (mobile/tablet/desktop)
- [ ] Check browser compatibility
- [ ] Test copy-to-clipboard functionality
- [ ] Validate HTML/CSS
- [ ] Optimize images (if any added)
- [ ] Enable HTTPS
- [ ] Set up security headers
- [ ] Configure caching
- [ ] Add analytics (optional)
- [ ] Test performance (Lighthouse)
- [ ] Set up monitoring (optional)

---

## 🆘 Troubleshooting

### Site not loading

**Check:**
- DNS propagation (use [DNS Checker](https://dnschecker.org/))
- Server status
- Firewall rules
- File permissions

### Assets not loading (404)

**Check:**
- File paths are relative
- Case sensitivity
- .htaccess or Nginx config

### Performance issues

**Solutions:**
- Enable compression (gzip/brotli)
- Minify CSS/JS
- Use CDN
- Enable caching headers
- Optimize matrix rain (reduce character count)

---

## 📞 Support

Questions about deployment?
- [GitHub Discussions](https://github.com/fabriziosalmi/blacklists/discussions)
- [GitHub Issues](https://github.com/fabriziosalmi/blacklists/issues)

---

**Last Updated:** November 9, 2025
