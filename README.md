# LinkedIn Scraper

A collection of Python/Selenium scripts for scraping LinkedIn profile data (experience, education, skills, certifications, etc.) into structured JSON.

## What it does

This repo holds several iterations of a LinkedIn profile scraper built with Selenium and BeautifulSoup:

- **`linkedin_scraper.py`** — first version. `LinkedInProfileScraper` class with manual (Google OAuth / email-password) login and an interactive `if __name__ == "__main__"` entry point.
- **`linkedin_scrapper_v2.py`** — a larger rewrite adding a `ScraperConfig` / `LinkedInProfile` dataclass setup, retry logic, logging, multi-format export (JSON/CSV/Excel) scaffolding, and a `main()` entry point.
- **`linked_scrapper_v3.py`** — a further rewrite that separates concerns into `LinkedInProfileExtractor` (parses saved HTML into a structured profile dict covering basic info, experience, education, skills, certifications, projects, honors/awards, and volunteering) and `LinkedInScraper` (Selenium driver: login, session persistence via a pickled cookie file, scrolling to load dynamic content). Run directly, it prompts for a profile URL, scrapes it, and writes a `profile_data_<timestamp>.json` file.
- **`html_diagnosis.py`** — a standalone diagnostic script that loads a previously saved LinkedIn HTML file and prints a report (page type, headings, sections found) to help debug why extraction might be failing.
- **`profile_Omkaar_Chakraborty.json`** — a sample scraped-output file checked into the repo, showing the shape of the extracted data.

There is no single "correct" entry point — the three scraper files are independent, overlapping implementations rather than one script that supersedes the others.

## Tech stack

- Python 3
- Selenium (`selenium==4.15.2`) + `webdriver-manager` (auto-downloads ChromeDriver) for browser automation
- BeautifulSoup4 + lxml for HTML parsing
- pandas / openpyxl for potential CSV/Excel export (used in v2)
- python-dotenv, colorama, tqdm, requests (declared dependencies, not all exercised by every script)

## Setup

```bash
pip install -r requirements.txt
```

Requires Google Chrome installed locally; `webdriver-manager` fetches a matching ChromeDriver automatically. A `.env.example` file exists but is currently empty, so there is no documented set of environment variables to configure.

## Usage example

Run the v3 scraper interactively (prompts for a profile URL, opens a browser for manual login, scrapes, and saves JSON):

```bash
python linked_scrapper_v3.py
```

To extract data from an HTML file you already saved (e.g. via `save_html=True`), use it as a library:

```python
from linked_scrapper_v3 import extract_from_html_file

data = extract_from_html_file("profile_1234567890.html")
print(data["basic_profile"]["full_name"])
```

To debug a saved HTML file that isn't extracting cleanly:

```bash
python html_diagnosis.py path/to/saved_profile.html
```

## Status

**Work in progress.** Observations from reading the code:

- Three separate, overlapping scraper implementations (`linkedin_scraper.py`, `linkedin_scrapper_v2.py`, `linked_scrapper_v3.py`) exist side by side with no clear indication of which is current/canonical — they appear to be successive rewrites rather than a single maintained tool.
- `linkedin_scrapper_v2.py` defines export/CSV/Excel and retry scaffolding (`ScraperConfig`, `LinkedInProfile` dataclasses) that isn't wired up in the other versions.
- The v3 HTML extractor (`LinkedInProfileExtractor`) uses heuristic, order-based text parsing (e.g. "first text element is the title, second is the company") which is fragile against LinkedIn markup changes and is explicitly why `html_diagnosis.py` exists as a debugging aid.
- `.env.example` is present but empty — no documented environment-variable configuration.
- No automated tests.
- No packaging (`setup.py`/`pyproject.toml`) or CLI entry point beyond running scripts directly.
- LinkedIn scraping may violate LinkedIn's Terms of Service; use at your own risk and for educational/personal purposes only.
