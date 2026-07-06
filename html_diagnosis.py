"""
LinkedIn HTML Diagnostic Tool
==============================
Analyzes saved LinkedIn HTML to help understand the structure
and identify why data extraction might be failing.
"""

import sys
import json
from bs4 import BeautifulSoup
import re


def analyze_linkedin_html(html_file_path: str):
    """
    Comprehensive analysis of LinkedIn profile HTML.
    """
    
    with open(html_file_path, 'r', encoding='utf-8') as f:
        html = f.read()
    
    soup = BeautifulSoup(html, 'html.parser')
    
    print("\n" + "="*70)
    print("LINKEDIN HTML DIAGNOSTIC REPORT")
    print("="*70)
    print(f"File: {html_file_path}")
    print(f"HTML Size: {len(html):,} characters")
    print("="*70)
    
    # 1. Check if it's the login/authwall page
    print("\n1. PAGE TYPE CHECK")
    print("-"*70)
    if 'authwall' in html.lower() or '/login' in html.lower():
        print("⚠️  WARNING: This appears to be a LOGIN/AUTHWALL page!")
        print("    The scraper may not be properly authenticated.")
        print("    Try deleting linkedin_session.pkl and logging in again.")
        return
    else:
        print("✓ Appears to be a profile page (not login/authwall)")
    
    # 2. Find all headings
    print("\n2. PAGE HEADINGS (H1, H2, H3)")
    print("-"*70)
    headings_found = 0
    for tag_name in ['h1', 'h2', 'h3']:
        tags = soup.find_all(tag_name)
        if tags:
            print(f"\n{tag_name.upper()} tags ({len(tags)} found):")
            for i, tag in enumerate(tags[:10], 1):  # Show first 10
                text = ' '.join(tag.get_text().split())[:80]
                if text:
                    print(f"  {i}. {text}")
                    headings_found += 1
    
    if headings_found == 0:
        print("⚠️  No headings found - this might be an empty or restricted page")
    
    # 3. Find sections
    print("\n3. SECTIONS AND MAIN CONTAINERS")
    print("-"*70)
    
    sections = soup.find_all('section')
    print(f"Total <section> tags: {len(sections)}")
    if sections:
        print("\nSection IDs and classes:")
        for i, section in enumerate(sections[:15], 1):
            section_id = section.get('id', 'no-id')
            classes = ' '.join(section.get('class', []))[:60]
            print(f"  {i}. id='{section_id}' class='{classes}'")
    
    # Look for specific profile sections
    print("\nSearching for key profile sections:")
    section_keywords = {
        'Experience': ['experience'],
        'Education': ['education'],
        'Skills': ['skills', 'skill'],
        'About': ['about', 'summary'],
        'Certifications': ['certification', 'license']
    }
    
    for section_name, keywords in section_keywords.items():
        found = False
        for section in soup.find_all(['section', 'div']):
            text = ' '.join(section.get_text().split()).lower()[:200]
            if any(keyword in text for keyword in keywords):
                found = True
                break
        status = "✓ FOUND" if found else "✗ NOT FOUND"
        print(f"  {status}: {section_name}")
    
    # 4. Check for profile name
    print("\n4. PROFILE NAME DETECTION")
    print("-"*70)
    
    h1_tags = soup.find_all('h1')
    if h1_tags:
        print(f"Found {len(h1_tags)} H1 tags:")
        for i, h1 in enumerate(h1_tags[:5], 1):
            text = ' '.join(h1.get_text().split())[:100]
            if text:
                print(f"  {i}. {text}")
        
        # Likely name
        if h1_tags:
            likely_name = ' '.join(h1_tags[0].get_text().split())
            print(f"\n  → Likely profile name: '{likely_name}'")
    else:
        print("⚠️  No H1 tags found")
    
    # 5. Check for common LinkedIn classes
    print("\n5. LINKEDIN-SPECIFIC ELEMENTS")
    print("-"*70)
    
    common_classes = [
        'pv-text-details__left-panel',
        'pv-top-card',
        'pvs-list',
        'experience-section',
        'pv-profile-section',
        'artdeco-card'
    ]
    
    print("Checking for common LinkedIn CSS classes:")
    for class_name in common_classes:
        elements = soup.find_all(class_=lambda x: x and class_name in str(x))
        status = f"✓ Found {len(elements)}" if elements else "✗ Not found"
        print(f"  {status}: .{class_name}")
    
    # 6. Sample text content
    print("\n6. TEXT CONTENT SAMPLE")
    print("-"*70)
    
    # Get all visible text
    all_text = soup.get_text(separator=' ', strip=True)
    words = all_text.split()
    
    print(f"Total words in HTML: {len(words):,}")
    print(f"\nFirst 200 words:")
    print(' '.join(words[:200]))
    
    # 7. Check for list items (often used in LinkedIn)
    print("\n7. LIST STRUCTURE ANALYSIS")
    print("-"*70)
    
    ul_tags = soup.find_all('ul')
    li_tags = soup.find_all('li')
    
    print(f"<ul> tags found: {len(ul_tags)}")
    print(f"<li> tags found: {len(li_tags)}")
    
    if ul_tags:
        print("\nLargest lists (by number of items):")
        ul_with_counts = [(ul, len(ul.find_all('li', recursive=False))) for ul in ul_tags]
        ul_with_counts.sort(key=lambda x: x[1], reverse=True)
        
        for i, (ul, count) in enumerate(ul_with_counts[:5], 1):
            ul_class = ' '.join(ul.get('class', []))[:50]
            print(f"  {i}. {count} items, class='{ul_class}'")
    
    # 8. Check for JavaScript data
    print("\n8. EMBEDDED DATA")
    print("-"*70)
    
    script_tags = soup.find_all('script')
    print(f"<script> tags found: {len(script_tags)}")
    
    # Look for JSON data
    json_found = 0
    for script in script_tags:
        if script.string and ('{' in script.string or '[' in script.string):
            json_found += 1
    
    print(f"Scripts potentially containing JSON: {json_found}")
    
    # 9. Recommendations
    print("\n9. RECOMMENDATIONS")
    print("-"*70)
    
    if headings_found == 0:
        print("⚠️  CRITICAL: No content found!")
        print("  → Check if you're logged in properly")
        print("  → Try deleting linkedin_session.pkl")
        print("  → Make sure the profile is public or you have access")
    elif 'authwall' in html.lower():
        print("⚠️  CRITICAL: Authwall detected!")
        print("  → Delete linkedin_session.pkl")
        print("  → Re-run and login again")
    else:
        print("✓ HTML appears to contain profile data")
        print("  → The parser may need adjustment for this specific HTML structure")
        print("  → Check LinkedInProfileExtractor's section detection in linked_scrapper_v3.py")
    
    print("\n" + "="*70)
    print("END OF DIAGNOSTIC REPORT")
    print("="*70)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python html_diagnostic.py <path_to_html_file>")
        print("\nExample: python html_diagnostic.py profile_1770315476.html")
        sys.exit(1)
    
    html_file = sys.argv[1]
    
    try:
        analyze_linkedin_html(html_file)
    except FileNotFoundError:
        print(f"Error: File '{html_file}' not found")
    except Exception as e:
        print(f"Error analyzing HTML: {e}")
        import traceback
        traceback.print_exc()