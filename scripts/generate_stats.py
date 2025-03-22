import collections
from pathlib import Path

def load_blacklist(file_path):
    with open(file_path, 'r') as f:
        return [line.strip() for line in f if line.strip()]

def generate_stats(domains):
    total_domains = len(domains)

    # TLD (Top Level Domain) counting
    tld_counter = collections.Counter(domain.split('.')[-1].lower() for domain in domains)

    # Second-Level Domain (SLD) counting
    sld_counter = collections.Counter(domain.split('.')[-2].lower() for domain in domains if domain.count('.') >= 2)

    # Subdomain counting (anything before the SLD)
    subdomain_counter = collections.Counter('.'.join(domain.split('.')[:-2]).lower() for domain in domains if domain.count('.') >= 3)

    # Domain lengths
    domain_length_counter = collections.Counter(len(domain) for domain in domains)
    
    # Top 10 longest and shortest domains
    longest_domains = sorted(domains, key=lambda x: len(x), reverse=True)[:10]
    shortest_domains = sorted(domains, key=lambda x: len(x))[:10]

    # Character distribution in domains
    char_counter = collections.Counter(char.lower() for domain in domains for char in domain if char.isalnum())

    # Domains with numbers
    numeric_domains = [domain for domain in domains if any(char.isdigit() for char in domain)]
    num_numeric_domains = len(numeric_domains)

    # Domains with hyphens
    hyphenated_domains = [domain for domain in domains if '-' in domain]
    num_hyphenated_domains = len(hyphenated_domains)

    # Vowel/Consonant ratio
    vowels = set('aeiou')
    vowel_count = sum(1 for domain in domains for char in domain if char.lower() in vowels)
    consonant_count = sum(1 for domain in domains for char in domain if char.isalpha() and char.lower() not in vowels)

    return {
        'total_domains': total_domains,
        'top_10_tlds': tld_counter.most_common(10),
        'top_10_slds': sld_counter.most_common(10),
        'top_10_subdomains': subdomain_counter.most_common(10),
        'top_10_domain_lengths': domain_length_counter.most_common(10),
        'longest_domains': longest_domains,
        'shortest_domains': shortest_domains,
        'top_10_chars': char_counter.most_common(10),
        'num_numeric_domains': num_numeric_domains,
        'num_hyphenated_domains': num_hyphenated_domains,
        'vowel_consonant_ratio': (vowel_count, consonant_count),
    }

def write_markdown(stats):
    with open('stats.md', 'w') as f:
        f.write(f"# Blacklist Statistics\n\n")
        f.write(f"**Last Updated:** {Path('blacklist.txt').stat().st_mtime}\n\n")
        
        f.write(f"## Overview\n")
        f.write(f"- **Total Domains:** {stats['total_domains']}\n")
        f.write(f"- **Domains with Numbers:** {stats['num_numeric_domains']}\n")
        f.write(f"- **Domains with Hyphens:** {stats['num_hyphenated_domains']}\n")
        f.write(f"- **Vowel/Consonant Ratio:** {stats['vowel_consonant_ratio'][0]}/{stats['vowel_consonant_ratio'][1]}\n\n")
        
        f.write(f"## Top 10 TLDs\n")
        f.write("| TLD | Count |\n")
        f.write("| --- | ----- |\n")
        for tld, count in stats['top_10_tlds']:
            f.write(f"| .{tld} | {count} |\n")
        
        f.write(f"\n## Top 10 Second-Level Domains (SLDs)\n")
        f.write("| SLD | Count |\n")
        f.write("| --- | ----- |\n")
        for sld, count in stats['top_10_slds']:
            f.write(f"| {sld} | {count} |\n")
        
        f.write(f"\n## Top 10 Subdomains\n")
        f.write("| Subdomain | Count |\n")
        f.write("| --------- | ----- |\n")
        for subdomain, count in stats['top_10_subdomains']:
            f.write(f"| {subdomain} | {count} |\n")

        f.write(f"\n## Top 10 Domain Lengths\n")
        f.write("| Length | Count |\n")
        f.write("| ------ | ----- |\n")
        for length, count in stats['top_10_domain_lengths']:
            f.write(f"| {length} | {count} |\n")

        f.write(f"\n## Longest 10 Domains\n")
        f.write("| Domain |\n")
        f.write("| ------ |\n")
        for domain in stats['longest_domains']:
            f.write(f"| {domain} |\n")

        f.write(f"\n## Shortest 10 Domains\n")
        f.write("| Domain |\n")
        f.write("| ------ |\n")
        for domain in stats['shortest_domains']:
            f.write(f"| {domain} |\n")

        f.write(f"\n## Top 10 Characters in Domain Names\n")
        f.write("| Character | Count |\n")
        f.write("| --------- | ----- |\n")
        for char, count in stats['top_10_chars']:
            f.write(f"| {char} | {count} |\n")

def main():
    blacklist_file = 'blacklist.txt'
    domains = load_blacklist(blacklist_file)
    stats = generate_stats(domains)
    write_markdown(stats)

if __name__ == '__main__':
    main()
