function copyToClipboard() {
    const el = document.getElementById('blacklist-url');
    el.style.display = 'block';  // temporarily display the input
    el.select();
    document.execCommand('copy');
    el.style.display = 'none';  // hide the input again

    // Show a confirmation text
    document.getElementById('confirmation-text').textContent = "URL Copied!";
}
