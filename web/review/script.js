document.addEventListener('DOMContentLoaded', (event) => {
    const form = document.getElementById('blacklist-form');
    form.addEventListener('submit', function(e) {
        e.preventDefault();
        const domain = document.getElementById('domain').value;
        checkBlacklists(domain);
    });
});

// Replace with your own list of URLs containing blacklists
const blacklists = [
'https://raw.githubusercontent.com/fabriziosalmi/blacklists/main/custom/streaming.txt',
'https://logroid.github.io/adaway-hosts/hosts.txt',
'https://o0.pages.dev/Pro/domains.txt',
'https://o0.pages.dev/mini/domains.txt',
'https://raw.githubusercontent.com/DandelionSprout/adfilt/master/Alternate%20versions%20Anti-Malware%20List/AntiMalwareHosts.txt',
'https://raw.githubusercontent.com/PolishFiltersTeam/KADhosts/master/KADhosts.txt',
'https://raw.githubusercontent.com/RPiList/specials/master/Blocklisten/Phishing-Angriffe',
'https://raw.githubusercontent.com/RPiList/specials/master/Blocklisten/easylist',
'https://raw.githubusercontent.com/RPiList/specials/master/Blocklisten/malware',
'https://raw.githubusercontent.com/RooneyMcNibNug/pihole-stuff/master/SNAFU.txt',
'https://raw.githubusercontent.com/ShadowWhisperer/BlockLists/master/Lists/Ads',
'https://raw.githubusercontent.com/ShadowWhisperer/BlockLists/master/Lists/Malware',
'https://raw.githubusercontent.com/ShadowWhisperer/BlockLists/master/Lists/Scam',
'https://raw.githubusercontent.com/ShadowWhisperer/BlockLists/master/Lists/Tracking',
'https://raw.githubusercontent.com/StevenBlack/hosts/master/data/KADhosts/hosts',
'https://raw.githubusercontent.com/StevenBlack/hosts/master/data/StevenBlack/hosts',
'https://raw.githubusercontent.com/StevenBlack/hosts/master/hosts',
'https://raw.githubusercontent.com/Th3M3/blocklists/master/malware.list',
'https://raw.githubusercontent.com/azet12/KADhosts/master/KADhosts.txt',
'https://raw.githubusercontent.com/badmojr/1Hosts/master/Lite/domains.txt',
'https://raw.githubusercontent.com/badmojr/1Hosts/master/Pro/domains.txt',
'https://raw.githubusercontent.com/badmojr/1Hosts/master/mini/domains.txt',
'https://raw.githubusercontent.com/bigdargon/hostsVN/master/filters/adservers-all.txt',
'https://raw.githubusercontent.com/bigdargon/hostsVN/master/filters/adservers.txt',
'https://raw.githubusercontent.com/bigdargon/hostsVN/master/hosts',
'https://raw.githubusercontent.com/bigdargon/hostsVN/master/option/domain.txt',
'https://raw.githubusercontent.com/bigdargon/hostsVN/master/option/hosts-iOS',
'https://raw.githubusercontent.com/bigdargon/hostsVN/master/source/hosts.txt',
'https://raw.githubusercontent.com/bongochong/CombinedPrivacyBlockLists/master/newhosts-final.hosts',
'https://raw.githubusercontent.com/doadin/Pi-Hole-Blocklist/main/block.list',
'https://raw.githubusercontent.com/durablenapkin/scamblocklist/master/hosts.txt',
'https://raw.githubusercontent.com/hagezi/dns-blocklists/main/adblock/anti.piracy.txt',
'https://raw.githubusercontent.com/hagezi/dns-blocklists/main/adblock/fake.txt',
'https://raw.githubusercontent.com/hagezi/dns-blocklists/main/adblock/gambling.txt',
'https://raw.githubusercontent.com/hagezi/dns-blocklists/main/domains/ultimate.txt',
'https://raw.githubusercontent.com/lightswitch05/hosts/master/docs/lists/tracking-aggressive-extended.txt',
'https://raw.githubusercontent.com/logroid/adaway-hosts/master/hosts.txt',
'https://raw.githubusercontent.com/mitchellkrogza/Phishing.Database/master/phishing-domains-ACTIVE.txt',
'https://raw.githubusercontent.com/mitchellkrogza/Ultimate.Hosts.Blacklist/master/domains/domains0.list',
'https://raw.githubusercontent.com/mitchellkrogza/Ultimate.Hosts.Blacklist/master/domains/domains1.list',
'https://raw.githubusercontent.com/mitchellkrogza/Ultimate.Hosts.Blacklist/master/domains/domains2.list',
'https://raw.githubusercontent.com/phishfort/phishfort-lists/master/blacklists/domains.json',
'https://raw.githubusercontent.com/r-a-y/mobile-hosts/master/AdguardDNS.txt',
'https://raw.githubusercontent.com/r-a-y/mobile-hosts/master/AdguardMobileAds.txt',
'https://raw.githubusercontent.com/r-a-y/mobile-hosts/master/EasyPrivacy3rdParty.txt',
'https://raw.githubusercontent.com/stamparm/aux/master/maltrail-malware-domains.txt',
'https://raw.githubusercontent.com/stamparm/blackbook/master/blackbook.txt',
'https://raw.githubusercontent.com/stamparm/maltrail/master/trails/static/suspicious/android_pua.txt',
'https://raw.githubusercontent.com/stamparm/maltrail/master/trails/static/suspicious/pua.txt',
'https://www.github.developerdan.com/hosts/lists/ads-and-tracking-extended.txt',
'https://www.github.developerdan.com/hosts/lists/tracking-aggressive-extended.txt',
'https://raw.githubusercontent.com/AssoEchap/stalkerware-indicators/master/generated/hosts',
'https://raw.githubusercontent.com/olbat/ut1-blacklists/master/blacklists/phishing/domains',
'https://raw.githubusercontent.com/olbat/ut1-blacklists/master/blacklists/malware/domains',
'https://raw.githubusercontent.com/olbat/ut1-blacklists/master/blacklists/warez/domains'
];

async function checkBlacklists(domain) {
    const resultsBody = document.getElementById('results-body');
    resultsBody.innerHTML = ''; // Clear previous results
    for (const url of blacklists) {
        const row = document.createElement('tr');
        const cell1 = document.createElement('td');
        const cell2 = document.createElement('td');
        cell1.textContent = url;
        cell2.textContent = 'Checking...';
        row.appendChild(cell1);
        row.appendChild(cell2);
        resultsBody.appendChild(row);

        // Fetch the blacklist and check the domain (simplified)
        // In a real-world application, you'd handle errors and edge cases
        try {
            const response = await fetch(url);
            const text = await response.text();
            const lines = text.split('\n');
            if (lines.includes(domain)) {
                cell2.textContent = 'Found';
                cell2.className = 'text-danger';
            } else {
                cell2.textContent = 'Not Found';
                cell2.className = 'text-success';
            }
        } catch (error) {
            cell2.textContent = 'Error';
            cell2.className = 'text-warning';
        }
    }
}
