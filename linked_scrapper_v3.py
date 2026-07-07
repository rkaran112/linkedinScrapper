"""
LinkedIn Profile Scraper with Automatic Fetching
=================================================
Extracts comprehensive profile data from LinkedIn URLs.
Handles authentication, dynamic content, and rate limiting.

Requirements:
- beautifulsoup4
- selenium
- webdriver-manager
"""

import re
import json
import time
import pickle
import os
from typing import Dict, List, Optional, Any
from pathlib import Path

from bs4 import BeautifulSoup, Tag
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager


class LinkedInProfileExtractor:
    """
    Extracts structured data from LinkedIn profile HTML.
    Uses semantic HTML patterns and text-based section detection.
    """
    
    # Section header patterns (case-insensitive)
    SECTION_HEADERS = {
        'about': ['about', 'summary'],
        'experience': ['experience'],
        'education': ['education'],
        'skills': ['skills', 'skills & endorsements'],
        'certifications': ['licenses & certifications', 'certifications'],
        'projects': ['projects'],
        'honors': ['honors & awards', 'honors', 'awards'],
        'volunteering': ['volunteering', 'volunteer experience']
    }
    
    def __init__(self, html: str):
        self.soup = BeautifulSoup(html, 'html.parser')
        self.profile_data = self._initialize_structure()
    
    def _initialize_structure(self) -> Dict[str, Any]:
        """Initialize the output data structure."""
        return {
            'basic_profile': {
                'full_name': None,
                'headline': None,
                'location': None,
                'current_company': None,
                'profile_summary': None
            },
            'experience': [],
            'education': [],
            'skills': [],
            'certifications': [],
            'projects': [],
            'honors_awards': [],
            'volunteering': []
        }
    
    def extract(self) -> Dict[str, Any]:
        """Main extraction orchestrator."""
        self._extract_basic_profile()
        self._extract_experience()
        self._extract_education()
        self._extract_skills()
        self._extract_certifications()
        self._extract_projects()
        self._extract_honors_awards()
        self._extract_volunteering()
        
        return self.profile_data
    
    # ==================== UTILITY METHODS ====================
    
    @staticmethod
    def _normalize_text(text: Optional[str]) -> Optional[str]:
        """Normalize whitespace and clean text."""
        if not text:
            return None
        cleaned = re.sub(r'\s+', ' ', text.strip())
        return cleaned if cleaned else None
    
    @staticmethod
    def _extract_date_range(text: str) -> tuple[Optional[str], Optional[str], Optional[str]]:
        """Extract start_date, end_date, and duration from text."""
        date_pattern = r'([A-Za-z]+\s+\d{4}|\d{4})\s*[–-]\s*([A-Za-z]+\s+\d{4}|\d{4}|Present)'
        duration_pattern = r'·\s*(.+?)(?:\s*·|$)'
        
        start_date = end_date = duration = None
        
        date_match = re.search(date_pattern, text, re.IGNORECASE)
        if date_match:
            start_date = date_match.group(1).strip()
            end_date = date_match.group(2).strip()
        
        duration_match = re.search(duration_pattern, text)
        if duration_match:
            duration = duration_match.group(1).strip()
        
        return start_date, end_date, duration
    
    def _find_section_by_header(self, header_keywords: List[str]) -> Optional[Tag]:
        """Find a section by looking for header text that matches keywords."""
        for element in self.soup.find_all(['h2', 'h3', 'h4', 'span', 'div']):
            text = self._normalize_text(element.get_text())
            if not text:
                continue
            
            text_lower = text.lower()
            for keyword in header_keywords:
                if text_lower == keyword.lower() or text_lower.startswith(keyword.lower()):
                    section = element.find_parent(['section', 'div'])
                    if section:
                        return section
        
        return None
    
    def _get_list_items_from_section(self, section: Tag) -> List[Tag]:
        """Extract repeating content blocks from a section."""
        list_items = section.find_all('li', recursive=True)
        if list_items:
            return list_items
        
        containers = section.find_all(['ul', 'ol', 'div'], recursive=True)
        for container in containers:
            direct_children = [child for child in container.children 
                             if isinstance(child, Tag) and child.name == 'div']
            if len(direct_children) >= 2:
                return direct_children
        
        return []
    
    # ==================== BASIC PROFILE EXTRACTION ====================
    
    def _extract_basic_profile(self):
        """Extract name, headline, location, and about section."""
        h1_tags = self.soup.find_all('h1')
        for h1 in h1_tags:
            name = self._normalize_text(h1.get_text())
            if name and len(name) < 100:
                self.profile_data['basic_profile']['full_name'] = name
                break
        
        if h1_tags:
            parent = h1_tags[0].find_parent(['div', 'section'])
            if parent:
                for element in parent.find_all(['div', 'p', 'span']):
                    text = self._normalize_text(element.get_text())
                    if text and 10 < len(text) < 200 and text != self.profile_data['basic_profile']['full_name']:
                        if not re.search(r'\b(area|region|country)\b', text.lower()):
                            self.profile_data['basic_profile']['headline'] = text
                            break
        
        for element in self.soup.find_all(['span', 'div', 'p']):
            text = self._normalize_text(element.get_text())
            if text and any(indicator in text.lower() for indicator in ['area', 'location', ',']):
                if re.search(r'^[\w\s,]+,[\w\s,]+$', text) and len(text) < 100:
                    self.profile_data['basic_profile']['location'] = text
                    break
        
        about_section = self._find_section_by_header(self.SECTION_HEADERS['about'])
        if about_section:
            paragraphs = []
            for p in about_section.find_all(['p', 'div', 'span']):
                text = self._normalize_text(p.get_text())
                if text and text.lower() not in self.SECTION_HEADERS['about'] and len(text) > 20:
                    paragraphs.append(text)
            
            if paragraphs:
                self.profile_data['basic_profile']['profile_summary'] = max(paragraphs, key=len)
    
    # ==================== EXPERIENCE EXTRACTION ====================
    
    def _extract_experience(self):
        """Extract all experience entries."""
        experience_section = self._find_section_by_header(self.SECTION_HEADERS['experience'])
        if not experience_section:
            return
        
        list_items = self._get_list_items_from_section(experience_section)
        
        for item in list_items:
            experience = self._parse_experience_item(item)
            if experience and experience.get('job_title'):
                self.profile_data['experience'].append(experience)
        
        for exp in self.profile_data['experience']:
            if exp.get('end_date') and exp['end_date'].lower() == 'present':
                self.profile_data['basic_profile']['current_company'] = exp.get('company_name')
                break
    
    def _parse_experience_item(self, item: Tag) -> Dict[str, Any]:
        """Parse a single experience entry."""
        experience = {
            'job_title': None,
            'company_name': None,
            'employment_type': None,
            'start_date': None,
            'end_date': None,
            'duration': None,
            'location': None,
            'description': []
        }
        
        text_elements = []
        for elem in item.find_all(['span', 'div', 'p', 'h3', 'h4']):
            text = self._normalize_text(elem.get_text())
            if text:
                text_elements.append(text)
        
        if not text_elements:
            return experience
        
        for i, text in enumerate(text_elements):
            if len(text) > 3 and not any(x in text.lower() for x in ['experience', '·']):
                experience['job_title'] = text
                text_elements = text_elements[i+1:]
                break
        
        if text_elements:
            experience['company_name'] = text_elements[0]
            text_elements = text_elements[1:]
        
        for text in text_elements[:]:
            if any(emp_type in text for emp_type in ['Full-time', 'Part-time', 'Contract', 
                                                       'Freelance', 'Internship', 'Self-employed']):
                experience['employment_type'] = text
                text_elements.remove(text)
                break
        
        for text in text_elements[:]:
            if re.search(r'\d{4}|Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec|Present', text, re.IGNORECASE):
                start_date, end_date, duration = self._extract_date_range(text)
                if start_date:
                    experience['start_date'] = start_date
                    experience['end_date'] = end_date
                    experience['duration'] = duration
                    text_elements.remove(text)
                    break
        
        for text in text_elements[:]:
            if ',' in text or any(x in text.lower() for x in ['remote', 'hybrid']):
                if len(text) < 100:
                    experience['location'] = text
                    text_elements.remove(text)
                    break
        
        description_list = item.find_all('li')
        if description_list:
            experience['description'] = [self._normalize_text(li.get_text()) 
                                        for li in description_list if self._normalize_text(li.get_text())]
        else:
            for text in text_elements:
                if len(text) > 50:
                    experience['description'].append(text)
        
        return experience
    
    # ==================== EDUCATION EXTRACTION ====================
    
    def _extract_education(self):
        """Extract all education entries."""
        education_section = self._find_section_by_header(self.SECTION_HEADERS['education'])
        if not education_section:
            return
        
        list_items = self._get_list_items_from_section(education_section)
        
        for item in list_items:
            education = self._parse_education_item(item)
            if education and education.get('institution_name'):
                self.profile_data['education'].append(education)
    
    def _parse_education_item(self, item: Tag) -> Dict[str, Any]:
        """Parse a single education entry."""
        education = {
            'institution_name': None,
            'degree': None,
            'field_of_study': None,
            'start_year': None,
            'end_year': None,
            'grade': None,
            'activities': None
        }
        
        text_elements = []
        for elem in item.find_all(['span', 'div', 'p', 'h3', 'h4']):
            text = self._normalize_text(elem.get_text())
            if text and text.lower() != 'education':
                text_elements.append(text)
        
        if not text_elements:
            return education
        
        education['institution_name'] = text_elements[0]
        text_elements = text_elements[1:]
        
        for text in text_elements[:]:
            if any(degree in text for degree in ['Bachelor', 'Master', 'PhD', 'Associate', 
                                                   'Doctorate', 'Diploma', 'Certificate']):
                parts = text.split(',')
                education['degree'] = parts[0].strip()
                if len(parts) > 1:
                    education['field_of_study'] = parts[1].strip()
                text_elements.remove(text)
                break
        
        for text in text_elements[:]:
            year_match = re.findall(r'\b(19|20)\d{2}\b', text)
            if len(year_match) == 2:
                education['start_year'] = year_match[0]
                education['end_year'] = year_match[1]
                text_elements.remove(text)
                break
            elif len(year_match) == 1:
                education['end_year'] = year_match[0]
                text_elements.remove(text)
                break
        
        for text in text_elements[:]:
            if any(x in text.lower() for x in ['gpa', 'grade', 'cgpa', 'score']):
                education['grade'] = text
                text_elements.remove(text)
                break
        
        for text in text_elements[:]:
            if 'activities' in text.lower() or len(text) > 30:
                education['activities'] = text
                break
        
        return education
    
    # ==================== SKILLS EXTRACTION ====================
    
    def _extract_skills(self):
        """Extract skills list."""
        skills_section = self._find_section_by_header(self.SECTION_HEADERS['skills'])
        if not skills_section:
            return
        
        skills = []
        
        for elem in skills_section.find_all(['span', 'div', 'li', 'p']):
            text = self._normalize_text(elem.get_text())
            if text and 2 < len(text) < 50 and text.lower() not in ['skills', 'endorsements']:
                if text not in skills and not any(text in s for s in skills):
                    skills.append(text)
        
        self.profile_data['skills'] = skills
    
    # ==================== CERTIFICATIONS EXTRACTION ====================
    
    def _extract_certifications(self):
        """Extract certifications."""
        cert_section = self._find_section_by_header(self.SECTION_HEADERS['certifications'])
        if not cert_section:
            return
        
        list_items = self._get_list_items_from_section(cert_section)
        
        for item in list_items:
            cert = self._parse_certification_item(item)
            if cert and cert.get('name'):
                self.profile_data['certifications'].append(cert)
    
    def _parse_certification_item(self, item: Tag) -> Dict[str, Any]:
        """Parse a single certification entry."""
        cert = {
            'name': None,
            'issuing_organization': None,
            'issue_date': None,
            'expiration_date': None
        }
        
        text_elements = []
        for elem in item.find_all(['span', 'div', 'p', 'h3', 'h4']):
            text = self._normalize_text(elem.get_text())
            if text:
                text_elements.append(text)
        
        if not text_elements:
            return cert
        
        cert['name'] = text_elements[0]
        text_elements = text_elements[1:]
        
        if text_elements:
            cert['issuing_organization'] = text_elements[0]
            text_elements = text_elements[1:]
        
        for text in text_elements:
            if re.search(r'issued|expires', text, re.IGNORECASE):
                issued_match = re.search(r'issued\s+([A-Za-z]+\s+\d{4})', text, re.IGNORECASE)
                expires_match = re.search(r'expires\s+([A-Za-z]+\s+\d{4})', text, re.IGNORECASE)
                
                if issued_match:
                    cert['issue_date'] = issued_match.group(1)
                if expires_match:
                    cert['expiration_date'] = expires_match.group(1)
        
        return cert
    
    # ==================== PROJECTS EXTRACTION ====================
    
    def _extract_projects(self):
        """Extract projects."""
        projects_section = self._find_section_by_header(self.SECTION_HEADERS['projects'])
        if not projects_section:
            return
        
        list_items = self._get_list_items_from_section(projects_section)
        
        for item in list_items:
            project = self._parse_project_item(item)
            if project and project.get('project_name'):
                self.profile_data['projects'].append(project)
    
    def _parse_project_item(self, item: Tag) -> Dict[str, Any]:
        """Parse a single project entry."""
        project = {
            'project_name': None,
            'role': None,
            'description': None,
            'associated_dates': None
        }
        
        text_elements = []
        for elem in item.find_all(['span', 'div', 'p', 'h3', 'h4']):
            text = self._normalize_text(elem.get_text())
            if text:
                text_elements.append(text)
        
        if not text_elements:
            return project
        
        project['project_name'] = text_elements[0]
        text_elements = text_elements[1:]
        
        for text in text_elements[:]:
            if re.search(r'\d{4}|Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec', text, re.IGNORECASE):
                project['associated_dates'] = text
                text_elements.remove(text)
                break
        
        for text in text_elements:
            if len(text) > 30:
                project['description'] = text
                break
        
        return project
    
    # ==================== HONORS & AWARDS EXTRACTION ====================
    
    def _extract_honors_awards(self):
        """Extract honors and awards."""
        honors_section = self._find_section_by_header(self.SECTION_HEADERS['honors'])
        if not honors_section:
            return
        
        list_items = self._get_list_items_from_section(honors_section)
        
        for item in list_items:
            honor = self._parse_honor_item(item)
            if honor and honor.get('title'):
                self.profile_data['honors_awards'].append(honor)
    
    def _parse_honor_item(self, item: Tag) -> Dict[str, Any]:
        """Parse a single honor/award entry."""
        honor = {
            'title': None,
            'issuer': None,
            'date': None,
            'description': None
        }
        
        text_elements = []
        for elem in item.find_all(['span', 'div', 'p', 'h3', 'h4']):
            text = self._normalize_text(elem.get_text())
            if text:
                text_elements.append(text)
        
        if not text_elements:
            return honor
        
        honor['title'] = text_elements[0]
        text_elements = text_elements[1:]
        
        if text_elements:
            honor['issuer'] = text_elements[0]
            text_elements = text_elements[1:]
        
        for text in text_elements[:]:
            if re.search(r'\d{4}|Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec', text, re.IGNORECASE):
                honor['date'] = text
                text_elements.remove(text)
                break
        
        for text in text_elements:
            if len(text) > 20:
                honor['description'] = text
                break
        
        return honor
    
    # ==================== VOLUNTEERING EXTRACTION ====================
    
    def _extract_volunteering(self):
        """Extract volunteering experience."""
        volunteering_section = self._find_section_by_header(self.SECTION_HEADERS['volunteering'])
        if not volunteering_section:
            return
        
        list_items = self._get_list_items_from_section(volunteering_section)
        
        for item in list_items:
            volunteer = self._parse_volunteer_item(item)
            if volunteer and volunteer.get('organization'):
                self.profile_data['volunteering'].append(volunteer)
    
    def _parse_volunteer_item(self, item: Tag) -> Dict[str, Any]:
        """Parse a single volunteering entry."""
        volunteer = {
            'organization': None,
            'role': None,
            'cause': None,
            'date_range': None,
            'description': None
        }
        
        text_elements = []
        for elem in item.find_all(['span', 'div', 'p', 'h3', 'h4']):
            text = self._normalize_text(elem.get_text())
            if text:
                text_elements.append(text)
        
        if not text_elements:
            return volunteer
        
        volunteer['role'] = text_elements[0]
        text_elements = text_elements[1:]
        
        if text_elements:
            volunteer['organization'] = text_elements[0]
            text_elements = text_elements[1:]
        
        for text in text_elements[:]:
            if re.search(r'\d{4}|Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec|Present', text, re.IGNORECASE):
                volunteer['date_range'] = text
                text_elements.remove(text)
                break
        
        for text in text_elements[:]:
            if 'cause' in text.lower() or any(c in text for c in ['Education', 'Environment', 'Health']):
                volunteer['cause'] = text
                text_elements.remove(text)
                break
        
        for text in text_elements:
            if len(text) > 30:
                volunteer['description'] = text
                break
        
        return volunteer


class LinkedInScraper:
    """
    Automated LinkedIn profile scraper using Selenium.
    Handles authentication, dynamic content loading, and session management.
    """
    
    def __init__(self, headless: bool = False, session_file: str = "linkedin_session.pkl"):
        """
        Initialize the scraper.
        
        Args:
            headless: Run browser in headless mode (no UI)
            session_file: Path to save/load session cookies
        """
        self.headless = headless
        self.session_file = session_file
        self.driver = None
        self.is_logged_in = False
    
    def _setup_driver(self):
        """Setup Chrome WebDriver with appropriate options."""
        chrome_options = Options()
        
        if self.headless:
            chrome_options.add_argument('--headless')
        
        # Anti-detection measures
        chrome_options.add_argument('--disable-blink-features=AutomationControlled')
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        
        # Set realistic window size
        chrome_options.add_argument('--window-size=1920,1080')
        
        # User agent
        chrome_options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
        
        # Initialize driver
        service = Service(ChromeDriverManager().install())
        self.driver = webdriver.Chrome(service=service, options=chrome_options)
        
        # Additional anti-detection
        self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    
    def _save_session(self):
        """Save cookies to file for session persistence."""
        with open(self.session_file, 'wb') as f:
            pickle.dump(self.driver.get_cookies(), f)
        print(f"✓ Session saved to {self.session_file}")
    
    def _load_session(self) -> bool:
        """
        Load cookies from file to restore session.
        
        Returns:
            True if session loaded successfully, False otherwise
        """
        if not os.path.exists(self.session_file):
            return False
        
        try:
            self.driver.get("https://www.linkedin.com")
            time.sleep(2)
            
            with open(self.session_file, 'rb') as f:
                cookies = pickle.load(f)
            
            for cookie in cookies:
                self.driver.add_cookie(cookie)
            
            # Verify session is valid
            self.driver.get("https://www.linkedin.com/feed/")
            time.sleep(3)
            
            # Check if we're redirected to login
            if "login" in self.driver.current_url or "authwall" in self.driver.current_url:
                print("✗ Session expired")
                return False
            
            print("✓ Session restored successfully")
            self.is_logged_in = True
            return True
            
        except Exception as e:
            print(f"✗ Failed to load session: {e}")
            return False
    
    def login(self, email: Optional[str] = None, password: Optional[str] = None):
        """
        Login to LinkedIn. Tries session first, then manual login.
        
        Args:
            email: LinkedIn email (optional if session exists)
            password: LinkedIn password (optional if session exists)
        """
        if not self.driver:
            self._setup_driver()
        
        # Try loading existing session
        if self._load_session():
            return
        
        # Manual login required
        if not email or not password:
            print("\n" + "="*60)
            print("MANUAL LOGIN REQUIRED")
            print("="*60)
            print("A browser window will open. Please:")
            print("1. Log in to LinkedIn manually")
            print("2. Complete any verification if required")
            print("3. Wait on the feed page")
            print("4. The script will continue automatically")
            print("="*60 + "\n")
            
            self.driver.get("https://www.linkedin.com/login")
            
            # Wait for user to login manually
            print("Waiting for manual login...")
            WebDriverWait(self.driver, 300).until(
                lambda driver: "feed" in driver.current_url or "mynetwork" in driver.current_url
            )
            print("✓ Login successful!")
            
        else:
            # Automated login
            print("Logging in to LinkedIn...")
            self.driver.get("https://www.linkedin.com/login")
            time.sleep(2)
            
            try:
                # Enter email
                email_field = self.driver.find_element(By.ID, "username")
                email_field.send_keys(email)
                
                # Enter password
                password_field = self.driver.find_element(By.ID, "password")
                password_field.send_keys(password)
                
                # Click login
                login_button = self.driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
                login_button.click()
                
                # Wait for redirect
                time.sleep(5)
                
                # Check for verification challenge
                if "checkpoint" in self.driver.current_url or "challenge" in self.driver.current_url:
                    print("\n⚠ Verification required. Please complete it in the browser...")
                    WebDriverWait(self.driver, 300).until(
                        lambda driver: "feed" in driver.current_url
                    )
                
                print("✓ Login successful!")
                
            except Exception as e:
                print(f"✗ Automated login failed: {e}")
                print("Please login manually in the browser window...")
                WebDriverWait(self.driver, 300).until(
                    lambda driver: "feed" in driver.current_url
                )
        
        self.is_logged_in = True
        self._save_session()
    
    def scrape_profile(self, profile_url: str, scroll_pause: float = 2.0) -> str:
        """
        Scrape HTML from a LinkedIn profile URL.
        
        Args:
            profile_url: Full LinkedIn profile URL
            scroll_pause: Time to pause between scrolls (seconds)
        
        Returns:
            HTML content of the profile page
        """
        if not self.is_logged_in:
            raise Exception("Not logged in. Call login() first.")
        
        print(f"\nScraping profile: {profile_url}")
        
        # Navigate to profile
        self.driver.get(profile_url)
        time.sleep(3)
        
        # Check if profile is accessible
        if "authwall" in self.driver.current_url:
            raise Exception("Profile not accessible. You may not have permission to view this profile.")
        
        # Scroll to load all dynamic content
        print("Loading profile content...")
        last_height = self.driver.execute_script("return document.body.scrollHeight")
        scroll_attempts = 0
        max_scrolls = 10
        
        while scroll_attempts < max_scrolls:
            # Scroll down
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(scroll_pause)
            
            # Calculate new height
            new_height = self.driver.execute_script("return document.body.scrollHeight")
            
            if new_height == last_height:
                # Try clicking "Show more" buttons
                try:
                    show_more_buttons = self.driver.find_elements(By.XPATH, 
                        "//*[contains(text(), 'Show more') or contains(text(), 'Show all')]")
                    for button in show_more_buttons:
                        try:
                            self.driver.execute_script("arguments[0].click();", button)
                            time.sleep(1)
                        except:
                            pass
                except:
                    pass
                
                # Check again
                new_height = self.driver.execute_script("return document.body.scrollHeight")
                if new_height == last_height:
                    break
            
            last_height = new_height
            scroll_attempts += 1
            print(f"  Scroll {scroll_attempts}/{max_scrolls}")
        
        print("✓ Profile loaded successfully")
        
        # Get page source
        html = self.driver.page_source
        return html
    
    def close(self):
        """Close the browser."""
        if self.driver:
            self.driver.quit()
            print("Browser closed")


# ==================== MAIN FUNCTIONS ====================

def scrape_linkedin_profile_from_url(
    profile_url: str,
    email: Optional[str] = None,
    password: Optional[str] = None,
    headless: bool = False,
    save_html: bool = False
) -> Dict[str, Any]:
    """
    Main function to scrape a LinkedIn profile from URL.
    
    Args:
        profile_url: LinkedIn profile URL (e.g., https://www.linkedin.com/in/username)
        email: LinkedIn login email (optional if session exists)
        password: LinkedIn login password (optional if session exists)
        headless: Run browser in headless mode
        save_html: Save raw HTML to file for debugging
    
    Returns:
        Structured profile data dictionary
    """
    scraper = LinkedInScraper(headless=headless)
    
    try:
        # Login
        scraper.login(email, password)
        
        # Scrape profile
        html = scraper.scrape_profile(profile_url)
        
        # Save HTML if requested
        if save_html:
            filename = f"profile_{int(time.time())}.html"
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(html)
            print(f"✓ HTML saved to {filename}")
        
        # Extract data
        print("\nExtracting profile data...")
        extractor = LinkedInProfileExtractor(html)
        profile_data = extractor.extract()
        
        print("✓ Extraction complete!")
        return profile_data
        
    finally:
        scraper.close()


def extract_from_html_file(html_file_path: str) -> Dict[str, Any]:
    """
    Extract profile data from a saved HTML file.
    
    Args:
        html_file_path: Path to HTML file
    
    Returns:
        Structured profile data dictionary
    """
    with open(html_file_path, 'r', encoding='utf-8') as f:
        html = f.read()
    
    extractor = LinkedInProfileExtractor(html)
    return extractor.extract()


# ==================== EXAMPLE USAGE ====================

if __name__ == "__main__":
    import sys
    
    print("""
╔═══════════════════════════════════════════════════════════╗
║          LinkedIn Profile Scraper                         ║
║          Automated data extraction tool                   ║
╚═══════════════════════════════════════════════════════════╝
    """)
    
    # Example 1: Scrape from URL (first time - will require login)
    print("\n--- METHOD 1: Scrape from URL ---")
    print("Note: First time will require manual login in browser")
    print("Subsequent runs will use saved session\n")
    
    # Get profile URL from user
    profile_url = input("Enter LinkedIn profile URL: ").strip()
    
    if not profile_url:
        print("No URL provided. Exiting...")
        sys.exit(0)
    
    # Validate URL
    if not profile_url.startswith("https://www.linkedin.com/in/"):
        print("⚠ Warning: URL should start with 'https://www.linkedin.com/in/'")
        confirm = input("Continue anyway? (y/n): ")
        if confirm.lower() != 'y':
            sys.exit(0)
    
    # Scrape profile
    try:
        profile_data = scrape_linkedin_profile_from_url(
            profile_url=profile_url,
            email=None,  # Will use manual login
            password=None,
            headless=False,  # Set to True to run without browser UI
            save_html=True  # Save HTML for debugging
        )
        
        # Save results
        output_file = f"profile_data_{int(time.time())}.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(profile_data, f, indent=2, ensure_ascii=False)
        
        print(f"\n✓ Profile data saved to: {output_file}")
        
        # Display summary
        print("\n" + "="*60)
        print("PROFILE SUMMARY")
        print("="*60)
        print(f"Name: {profile_data['basic_profile']['full_name']}")
        print(f"Headline: {profile_data['basic_profile']['headline']}")
        print(f"Location: {profile_data['basic_profile']['location']}")
        print(f"Current Company: {profile_data['basic_profile']['current_company']}")
        print(f"\nExperience Entries: {len(profile_data['experience'])}")
        print(f"Education Entries: {len(profile_data['education'])}")
        print(f"Skills: {len(profile_data['skills'])}")
        print(f"Certifications: {len(profile_data['certifications'])}")
        print("="*60)
        
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()