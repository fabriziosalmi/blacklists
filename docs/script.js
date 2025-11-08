// ============================================
// CYBER DEFENSE - INTERACTIVE FEATURES
// ============================================

document.addEventListener('DOMContentLoaded', () => {
    initMatrixRain();
    initNavigation();
    initCounters();
    initCopyButtons();
    initScrollEffects();
    initBackToTop();
    initTimeUpdates();
});

// ============================================
// MATRIX RAIN EFFECT
// ============================================

function initMatrixRain() {
    const canvas = document.getElementById('matrix');
    const ctx = canvas.getContext('2d');
    
    canvas.width = window.innerWidth;
    canvas.height = window.innerHeight;
    
    const chars = '01アイウエオカキクケコサシスセソタチツテトナニヌネノハヒフヘホマミムメモヤユヨラリルレロワヲン';
    const fontSize = 14;
    const columns = canvas.width / fontSize;
    
    const drops = Array(Math.floor(columns)).fill(1);
    
    function draw() {
        ctx.fillStyle = 'rgba(10, 14, 39, 0.05)';
        ctx.fillRect(0, 0, canvas.width, canvas.height);
        
        ctx.fillStyle = '#00ff88';
        ctx.font = fontSize + 'px monospace';
        
        for (let i = 0; i < drops.length; i++) {
            const text = chars[Math.floor(Math.random() * chars.length)];
            ctx.fillText(text, i * fontSize, drops[i] * fontSize);
            
            if (drops[i] * fontSize > canvas.height && Math.random() > 0.975) {
                drops[i] = 0;
            }
            drops[i]++;
        }
    }
    
    setInterval(draw, 33);
    
    window.addEventListener('resize', () => {
        canvas.width = window.innerWidth;
        canvas.height = window.innerHeight;
    });
}

// ============================================
// NAVIGATION
// ============================================

function initNavigation() {
    const navbar = document.querySelector('.navbar');
    const hamburger = document.querySelector('.hamburger');
    const navLinks = document.querySelector('.nav-links');
    
    // Scroll effect
    window.addEventListener('scroll', () => {
        if (window.scrollY > 100) {
            navbar.style.background = 'rgba(10, 14, 39, 0.95)';
            navbar.style.boxShadow = '0 5px 20px rgba(0, 255, 136, 0.1)';
        } else {
            navbar.style.background = 'rgba(10, 14, 39, 0.8)';
            navbar.style.boxShadow = 'none';
        }
    });
    
    // Mobile menu
    if (hamburger) {
        hamburger.addEventListener('click', () => {
            hamburger.classList.toggle('active');
            navLinks.classList.toggle('active');
        });
    }
    
    // Active link on scroll
    const sections = document.querySelectorAll('section[id]');
    const navItems = document.querySelectorAll('.nav-link');
    
    window.addEventListener('scroll', () => {
        let current = '';
        sections.forEach(section => {
            const sectionTop = section.offsetTop;
            const sectionHeight = section.clientHeight;
            if (scrollY >= sectionTop - 200) {
                current = section.getAttribute('id');
            }
        });
        
        navItems.forEach(item => {
            item.classList.remove('active');
            if (item.getAttribute('href') === `#${current}`) {
                item.classList.add('active');
            }
        });
    });
    
    // Smooth scroll for anchor links
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function (e) {
            e.preventDefault();
            const target = document.querySelector(this.getAttribute('href'));
            if (target) {
                target.scrollIntoView({
                    behavior: 'smooth',
                    block: 'start'
                });
            }
        });
    });
}

// ============================================
// ANIMATED COUNTERS
// ============================================

function initCounters() {
    const counters = document.querySelectorAll('.stat-number[data-target]');
    const speed = 200; // Animation duration in ms
    
    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                const counter = entry.target;
                const target = +counter.getAttribute('data-target');
                const increment = target / speed;
                
                let current = 0;
                const updateCounter = () => {
                    current += increment;
                    if (current < target) {
                        counter.textContent = Math.ceil(current).toLocaleString();
                        setTimeout(updateCounter, 1);
                    } else {
                        counter.textContent = target.toLocaleString();
                    }
                };
                
                updateCounter();
                observer.unobserve(counter);
            }
        });
    }, { threshold: 0.5 });
    
    counters.forEach(counter => observer.observe(counter));
}

// ============================================
// COPY BUTTONS
// ============================================

function initCopyButtons() {
    const copyButtons = document.querySelectorAll('.copy-btn');
    
    copyButtons.forEach(button => {
        button.addEventListener('click', () => {
            const targetId = button.getAttribute('data-target');
            const input = document.getElementById(targetId);
            
            if (input) {
                // Copy to clipboard
                input.select();
                input.setSelectionRange(0, 99999); // For mobile
                navigator.clipboard.writeText(input.value).then(() => {
                    // Visual feedback
                    const originalText = button.innerHTML;
                    button.innerHTML = '<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M5 13l4 4L19 7" stroke="currentColor" stroke-width="2"/></svg> COPIED!';
                    button.style.background = 'linear-gradient(135deg, #00ff88, #00d4ff)';
                    
                    setTimeout(() => {
                        button.innerHTML = originalText;
                        button.style.background = '';
                    }, 2000);
                }).catch(err => {
                    console.error('Failed to copy:', err);
                    alert('Failed to copy URL');
                });
            }
        });
    });
}

// ============================================
// SCROLL EFFECTS
// ============================================

function initScrollEffects() {
    // Intersection Observer for fade-in animations
    const observerOptions = {
        threshold: 0.1,
        rootMargin: '0px 0px -100px 0px'
    };
    
    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.classList.add('fade-in');
                observer.unobserve(entry.target);
            }
        });
    }, observerOptions);
    
    // Observe all cards and sections
    const elements = document.querySelectorAll('.feature-card, .stat-card, .download-card, .community-card');
    elements.forEach(el => observer.observe(el));
    
    // Parallax effect for threat orbs
    window.addEventListener('scroll', () => {
        const scrolled = window.pageYOffset;
        const orbs = document.querySelectorAll('.threat-orb');
        orbs.forEach((orb, index) => {
            const speed = 0.5 + (index * 0.1);
            orb.style.transform = `translateY(${scrolled * speed}px)`;
        });
    });
}

// ============================================
// BACK TO TOP BUTTON
// ============================================

function initBackToTop() {
    const backToTop = document.getElementById('backToTop');
    
    window.addEventListener('scroll', () => {
        if (window.scrollY > 500) {
            backToTop.classList.add('visible');
        } else {
            backToTop.classList.remove('visible');
        }
    });
    
    backToTop.addEventListener('click', () => {
        window.scrollTo({
            top: 0,
            behavior: 'smooth'
        });
    });
}

// ============================================
// TIME UPDATES
// ============================================

function initTimeUpdates() {
    function updateTimes() {
        const now = new Date();
        const lastUpdate = new Date(now.getTime() - Math.random() * 10 * 60000); // Random 0-10 min ago
        const nextUpdate = new Date(now.getTime() + (60 - now.getMinutes() % 60) * 60000);
        
        const lastUpdateEl = document.getElementById('last-update');
        const nextUpdateEl = document.getElementById('next-update');
        
        if (lastUpdateEl) {
            const minutesAgo = Math.floor((now - lastUpdate) / 60000);
            lastUpdateEl.textContent = minutesAgo < 1 ? 'just now' : `${minutesAgo} minute${minutesAgo > 1 ? 's' : ''} ago`;
        }
        
        if (nextUpdateEl) {
            const minutesUntil = Math.floor((nextUpdate - now) / 60000);
            nextUpdateEl.textContent = `in ${minutesUntil} minute${minutesUntil !== 1 ? 's' : ''}`;
        }
    }
    
    updateTimes();
    setInterval(updateTimes, 60000); // Update every minute
}

// ============================================
// EASTER EGG - KONAMI CODE
// ============================================

(function() {
    const konamiCode = ['ArrowUp', 'ArrowUp', 'ArrowDown', 'ArrowDown', 'ArrowLeft', 'ArrowRight', 'ArrowLeft', 'ArrowRight', 'b', 'a'];
    let konamiIndex = 0;
    
    document.addEventListener('keydown', (e) => {
        if (e.key === konamiCode[konamiIndex]) {
            konamiIndex++;
            if (konamiIndex === konamiCode.length) {
                activateEasterEgg();
                konamiIndex = 0;
            }
        } else {
            konamiIndex = 0;
        }
    });
    
    function activateEasterEgg() {
        // Change theme colors temporarily
        document.documentElement.style.setProperty('--neon-green', '#ff0055');
        document.documentElement.style.setProperty('--neon-blue', '#8800ff');
        document.documentElement.style.setProperty('--neon-pink', '#00ff88');
        
        // Show message
        const message = document.createElement('div');
        message.style.cssText = `
            position: fixed;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            background: linear-gradient(135deg, #ff0055, #8800ff);
            padding: 2rem 3rem;
            border-radius: 20px;
            font-family: var(--font-primary);
            font-size: 2rem;
            color: white;
            z-index: 9999;
            box-shadow: 0 20px 60px rgba(255, 0, 85, 0.5);
            animation: fadeIn 0.5s ease-out;
        `;
        message.textContent = '🎮 CYBER MODE ACTIVATED!';
        document.body.appendChild(message);
        
        setTimeout(() => {
            message.style.animation = 'fadeOut 0.5s ease-out';
            setTimeout(() => {
                message.remove();
                // Restore original colors
                document.documentElement.style.setProperty('--neon-green', '#00ff88');
                document.documentElement.style.setProperty('--neon-blue', '#00d4ff');
                document.documentElement.style.setProperty('--neon-pink', '#ff0055');
            }, 500);
        }, 3000);
    }
})();

// ============================================
// PERFORMANCE OPTIMIZATION
// ============================================

// Lazy load images (if you add any in the future)
if ('loading' in HTMLImageElement.prototype) {
    const images = document.querySelectorAll('img[loading="lazy"]');
    images.forEach(img => {
        img.src = img.dataset.src;
    });
} else {
    // Fallback for browsers that don't support lazy loading
    const script = document.createElement('script');
    script.src = 'https://cdnjs.cloudflare.com/ajax/libs/lazysizes/5.3.2/lazysizes.min.js';
    document.body.appendChild(script);
}

// Preconnect to external resources
const preconnect = document.createElement('link');
preconnect.rel = 'preconnect';
preconnect.href = 'https://fonts.googleapis.com';
document.head.appendChild(preconnect);

// ============================================
// ANALYTICS (placeholder for future use)
// ============================================

function trackEvent(category, action, label) {
    // Placeholder for analytics tracking
    console.log(`Event: ${category} - ${action} - ${label}`);
    // You can integrate Google Analytics, Plausible, etc. here
}

// Track download button clicks
document.querySelectorAll('.copy-btn').forEach(btn => {
    btn.addEventListener('click', () => {
        const format = btn.closest('.download-card').querySelector('h3').textContent;
        trackEvent('Downloads', 'Copy URL', format);
    });
});

// Track CTA button clicks
document.querySelectorAll('.btn').forEach(btn => {
    btn.addEventListener('click', () => {
        trackEvent('CTA', 'Click', btn.textContent.trim());
    });
});

// ============================================
// ACCESSIBILITY IMPROVEMENTS
// ============================================

// Keyboard navigation for cards
document.querySelectorAll('.feature-card, .download-card, .community-card').forEach(card => {
    card.setAttribute('tabindex', '0');
    card.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') {
            const link = card.querySelector('a');
            if (link) link.click();
        }
    });
});

// Focus management
const focusableElements = document.querySelectorAll('a, button, input, [tabindex]:not([tabindex="-1"])');
let focusedElementBeforeModal;

// Announce page changes to screen readers
function announceToScreenReader(message) {
    const announcement = document.createElement('div');
    announcement.setAttribute('role', 'status');
    announcement.setAttribute('aria-live', 'polite');
    announcement.style.position = 'absolute';
    announcement.style.left = '-10000px';
    announcement.textContent = message;
    document.body.appendChild(announcement);
    setTimeout(() => announcement.remove(), 1000);
}

// Announce when sections come into view
const sectionObserver = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
        if (entry.isIntersecting) {
            const sectionName = entry.target.querySelector('.section-title')?.textContent || 'Section';
            announceToScreenReader(`Entering ${sectionName} section`);
        }
    });
}, { threshold: 0.5 });

document.querySelectorAll('section[id]').forEach(section => {
    sectionObserver.observe(section);
});

// ============================================
// CONSOLE MESSAGE
// ============================================

console.log(
    '%c🛡️ blacklists %c- Cyber Defense for Everyone',
    'color: #00ff88; font-size: 20px; font-weight: bold; text-shadow: 0 0 10px #00ff88;',
    'color: #00d4ff; font-size: 16px;'
);

console.log(
    '%c⚡ Interested in contributing? Check out: https://github.com/fabriziosalmi/blacklists',
    'color: #a0aec0; font-size: 12px;'
);

console.log(
    '%c🎮 Try the Konami Code: ↑ ↑ ↓ ↓ ← → ← → B A',
    'color: #ff0055; font-size: 12px; font-style: italic;'
);