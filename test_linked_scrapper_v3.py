"""
Unit tests for LinkedInProfileExtractor in linked_scrapper_v3.py.
Covers text normalization, date parsing, and full extraction from
small synthetic HTML fixtures (no live LinkedIn HTML required).
"""

import unittest

from linked_scrapper_v3 import LinkedInProfileExtractor


class TestNormalizeText(unittest.TestCase):

    def test_collapses_whitespace(self):
        self.assertEqual(
            LinkedInProfileExtractor._normalize_text("  Hello\n\n  World  "),
            "Hello World"
        )

    def test_none_input_returns_none(self):
        self.assertIsNone(LinkedInProfileExtractor._normalize_text(None))

    def test_empty_string_returns_none(self):
        self.assertIsNone(LinkedInProfileExtractor._normalize_text("   "))

    def test_plain_string_unchanged(self):
        self.assertEqual(LinkedInProfileExtractor._normalize_text("Software Engineer"), "Software Engineer")


class TestExtractDateRange(unittest.TestCase):

    def test_month_year_to_present(self):
        start, end, duration = LinkedInProfileExtractor._extract_date_range(
            "Jan 2020 - Present · 5 yrs 6 mos"
        )
        self.assertEqual(start, "Jan 2020")
        self.assertEqual(end, "Present")
        self.assertEqual(duration, "5 yrs 6 mos")

    def test_year_only_range(self):
        start, end, duration = LinkedInProfileExtractor._extract_date_range("2018 - 2022")
        self.assertEqual(start, "2018")
        self.assertEqual(end, "2022")
        self.assertIsNone(duration)

    def test_no_date_returns_all_none(self):
        start, end, duration = LinkedInProfileExtractor._extract_date_range("No dates here")
        self.assertIsNone(start)
        self.assertIsNone(end)
        self.assertIsNone(duration)

    def test_employment_type_prefix_does_not_swallow_duration(self):
        # A leading "Full-time · ..." segment before the date range must not
        # be mistaken for the duration that follows the date range.
        start, end, duration = LinkedInProfileExtractor._extract_date_range(
            "Full-time · Jan 2020 - Present · 5 yrs 6 mos"
        )
        self.assertEqual(start, "Jan 2020")
        self.assertEqual(end, "Present")
        self.assertEqual(duration, "5 yrs 6 mos")


class TestExtractExperience(unittest.TestCase):

    def _build_html(self, job_title, company, dates):
        return f"""
        <html><body>
        <h1>Jane Doe</h1>
        <section>
            <h2>Experience</h2>
            <ul>
                <li>
                    <span>{job_title}</span>
                    <span>{company}</span>
                    <span>{dates}</span>
                </li>
            </ul>
        </section>
        </body></html>
        """

    def test_parses_job_title_company_and_dates(self):
        html = self._build_html("Senior Engineer", "Acme Corp", "Jan 2020 - Present · 5 yrs")
        data = LinkedInProfileExtractor(html).extract()

        self.assertEqual(len(data['experience']), 1)
        exp = data['experience'][0]
        self.assertEqual(exp['job_title'], "Senior Engineer")
        self.assertEqual(exp['company_name'], "Acme Corp")
        self.assertEqual(exp['start_date'], "Jan 2020")
        self.assertEqual(exp['end_date'], "Present")

    def test_current_company_set_from_present_role(self):
        html = self._build_html("Senior Engineer", "Acme Corp", "Jan 2020 - Present · 5 yrs")
        data = LinkedInProfileExtractor(html).extract()

        self.assertEqual(data['basic_profile']['current_company'], "Acme Corp")

    def test_short_job_title_is_not_skipped(self):
        # Titles like "CTO", "VP", "CFO" are 3 characters or fewer and must
        # still be recognized as the job title rather than being skipped in
        # favor of the company name.
        html = self._build_html("CTO", "Acme Corp", "Jan 2020 - Present · 5 yrs")
        data = LinkedInProfileExtractor(html).extract()

        exp = data['experience'][0]
        self.assertEqual(exp['job_title'], "CTO")
        self.assertEqual(exp['company_name'], "Acme Corp")

    def test_nested_description_bullets_are_not_treated_as_separate_entries(self):
        # LinkedIn wraps each description bullet in its own <li>, nested
        # inside the entry's outer <li>. Those nested bullets must not be
        # picked up as additional top-level experience entries.
        html = """
        <html><body>
        <h1>Jane Doe</h1>
        <section>
            <h2>Experience</h2>
            <ul>
                <li>
                    <span>Senior Engineer</span>
                    <span>Acme Corp</span>
                    <span>Jan 2020 - Present</span>
                    <ul>
                        <li><span>Led a team of 5 engineers on the payments platform.</span></li>
                        <li><span>Reduced latency by 30 percent through caching.</span></li>
                    </ul>
                </li>
            </ul>
        </section>
        </body></html>
        """
        data = LinkedInProfileExtractor(html).extract()

        self.assertEqual(len(data['experience']), 1)
        exp = data['experience'][0]
        self.assertEqual(exp['job_title'], "Senior Engineer")
        self.assertEqual(exp['company_name'], "Acme Corp")
        self.assertEqual(exp['description'], [
            "Led a team of 5 engineers on the payments platform.",
            "Reduced latency by 30 percent through caching.",
        ])

    def test_duplicate_accessibility_spans_are_collapsed(self):
        # LinkedIn renders visible text plus an aria-hidden duplicate of the
        # same text; leaf-text collection must not treat these as two fields.
        html = """
        <html><body>
        <h1>Jane Doe</h1>
        <section>
            <h2>Experience</h2>
            <ul>
                <li>
                    <span aria-hidden="true">Senior Engineer</span>
                    <span class="visually-hidden">Senior Engineer</span>
                    <span>Acme Corp</span>
                </li>
            </ul>
        </section>
        </body></html>
        """
        data = LinkedInProfileExtractor(html).extract()

        self.assertEqual(len(data['experience']), 1)
        exp = data['experience'][0]
        self.assertEqual(exp['job_title'], "Senior Engineer")
        self.assertEqual(exp['company_name'], "Acme Corp")


class TestExtractEducation(unittest.TestCase):

    def _build_html(self, institution, degree, years):
        return f"""
        <html><body>
        <h1>Jane Doe</h1>
        <section>
            <h2>Education</h2>
            <ul>
                <li>
                    <span>{institution}</span>
                    <span>{degree}</span>
                    <span>{years}</span>
                </li>
            </ul>
        </section>
        </body></html>
        """

    def test_parses_full_start_and_end_year(self):
        html = self._build_html("State University", "Bachelor of Science, Computer Science", "2018 - 2022")
        data = LinkedInProfileExtractor(html).extract()

        self.assertEqual(len(data['education']), 1)
        edu = data['education'][0]
        self.assertEqual(edu['start_year'], "2018")
        self.assertEqual(edu['end_year'], "2022")

    def test_parses_single_year(self):
        html = self._build_html("State University", "Bachelor of Science, Computer Science", "2022")
        data = LinkedInProfileExtractor(html).extract()

        edu = data['education'][0]
        self.assertIsNone(edu['start_year'])
        self.assertEqual(edu['end_year'], "2022")


class TestExtractCertifications(unittest.TestCase):

    def _build_html(self, name, org, dates):
        return f"""
        <html><body>
        <h1>Jane Doe</h1>
        <section>
            <h2>Licenses & Certifications</h2>
            <ul>
                <li>
                    <span>{name}</span>
                    <span>{org}</span>
                    <span>{dates}</span>
                </li>
            </ul>
        </section>
        </body></html>
        """

    def test_parses_name_organization_and_dates(self):
        html = self._build_html(
            "AWS Certified Solutions Architect", "Amazon Web Services",
            "Issued Jan 2022 · Expires Jan 2025"
        )
        data = LinkedInProfileExtractor(html).extract()

        self.assertEqual(len(data['certifications']), 1)
        cert = data['certifications'][0]
        self.assertEqual(cert['name'], "AWS Certified Solutions Architect")
        self.assertEqual(cert['issuing_organization'], "Amazon Web Services")
        self.assertEqual(cert['issue_date'], "Jan 2022")
        self.assertEqual(cert['expiration_date'], "Jan 2025")

    def test_missing_expiration_leaves_it_none(self):
        html = self._build_html(
            "Certified Kubernetes Administrator", "The Linux Foundation", "Issued Jun 2023"
        )
        data = LinkedInProfileExtractor(html).extract()

        cert = data['certifications'][0]
        self.assertEqual(cert['issue_date'], "Jun 2023")
        self.assertIsNone(cert['expiration_date'])


class TestExtractSkills(unittest.TestCase):

    def _build_html(self, skills):
        items = "".join(f"<li><span>{skill}</span></li>" for skill in skills)
        return f"""
        <html><body>
        <h1>Jane Doe</h1>
        <section>
            <h2>Skills</h2>
            <ul>{items}</ul>
        </section>
        </body></html>
        """

    def test_keeps_skills_that_are_substrings_of_other_skills(self):
        html = self._build_html(["JavaScript", "Java", "Python"])
        data = LinkedInProfileExtractor(html).extract()

        self.assertEqual(data['skills'], ["JavaScript", "Java", "Python"])

    def test_dedupes_exact_duplicate_skills(self):
        html = self._build_html(["Python", "Python"])
        data = LinkedInProfileExtractor(html).extract()

        self.assertEqual(data['skills'], ["Python"])


class TestExtractProjects(unittest.TestCase):

    def _build_html(self, name, dates, description):
        return f"""
        <html><body>
        <h1>Jane Doe</h1>
        <section>
            <h2>Projects</h2>
            <ul>
                <li>
                    <span>{name}</span>
                    <span>{dates}</span>
                    <span>{description}</span>
                </li>
            </ul>
        </section>
        </body></html>
        """

    def test_parses_name_dates_and_description(self):
        html = self._build_html(
            "Personal Portfolio Website", "Jan 2021 - Mar 2021",
            "Built a responsive portfolio site using React and deployed it to Vercel."
        )
        data = LinkedInProfileExtractor(html).extract()

        self.assertEqual(len(data['projects']), 1)
        project = data['projects'][0]
        self.assertEqual(project['project_name'], "Personal Portfolio Website")
        self.assertEqual(project['associated_dates'], "Jan 2021 - Mar 2021")
        self.assertEqual(project['description'],
                          "Built a responsive portfolio site using React and deployed it to Vercel.")


class TestExtractHonorsAwards(unittest.TestCase):

    def _build_html(self, title, issuer, date, description):
        return f"""
        <html><body>
        <h1>Jane Doe</h1>
        <section>
            <h2>Honors & Awards</h2>
            <ul>
                <li>
                    <span>{title}</span>
                    <span>{issuer}</span>
                    <span>{date}</span>
                    <span>{description}</span>
                </li>
            </ul>
        </section>
        </body></html>
        """

    def test_parses_title_issuer_date_and_description(self):
        html = self._build_html(
            "Employee of the Year", "Acme Corp", "Issued Dec 2022",
            "Awarded for outstanding contributions to the engineering team."
        )
        data = LinkedInProfileExtractor(html).extract()

        self.assertEqual(len(data['honors_awards']), 1)
        honor = data['honors_awards'][0]
        self.assertEqual(honor['title'], "Employee of the Year")
        self.assertEqual(honor['issuer'], "Acme Corp")
        self.assertEqual(honor['date'], "Issued Dec 2022")
        self.assertEqual(honor['description'],
                          "Awarded for outstanding contributions to the engineering team.")


class TestExtractVolunteering(unittest.TestCase):

    def _build_html(self, role, organization, dates, cause, description):
        return f"""
        <html><body>
        <h1>Jane Doe</h1>
        <section>
            <h2>Volunteering</h2>
            <ul>
                <li>
                    <span>{role}</span>
                    <span>{organization}</span>
                    <span>{dates}</span>
                    <span>{cause}</span>
                    <span>{description}</span>
                </li>
            </ul>
        </section>
        </body></html>
        """

    def test_parses_role_organization_dates_cause_and_description(self):
        html = self._build_html(
            "Mentor", "Code for Good", "Jan 2019 - Present", "Education",
            "Mentored students in web development fundamentals every weekend."
        )
        data = LinkedInProfileExtractor(html).extract()

        self.assertEqual(len(data['volunteering']), 1)
        volunteer = data['volunteering'][0]
        self.assertEqual(volunteer['role'], "Mentor")
        self.assertEqual(volunteer['organization'], "Code for Good")
        self.assertEqual(volunteer['date_range'], "Jan 2019 - Present")
        self.assertEqual(volunteer['cause'], "Education")
        self.assertEqual(volunteer['description'],
                          "Mentored students in web development fundamentals every weekend.")


class TestExtractBasicProfile(unittest.TestCase):

    def test_extracts_full_name_from_first_h1(self):
        html = "<html><body><h1>John Smith</h1></body></html>"
        data = LinkedInProfileExtractor(html).extract()
        self.assertEqual(data['basic_profile']['full_name'], "John Smith")

    def test_missing_sections_leave_empty_lists(self):
        html = "<html><body><h1>John Smith</h1></body></html>"
        data = LinkedInProfileExtractor(html).extract()
        self.assertEqual(data['experience'], [])
        self.assertEqual(data['education'], [])
        self.assertEqual(data['skills'], [])

    def test_parses_location_with_comma(self):
        html = """
        <html><body>
        <div>
            <h1>Jane Doe</h1>
            <div>Senior Software Engineer at Acme Corp</div>
            <span>New York, NY</span>
        </div>
        </body></html>
        """
        data = LinkedInProfileExtractor(html).extract()
        self.assertEqual(data['basic_profile']['location'], "New York, NY")

    def test_parses_metro_area_location_without_comma(self):
        # LinkedIn commonly renders metro-area locations with no comma at all.
        html = """
        <html><body>
        <div>
            <h1>Jane Doe</h1>
            <div>Senior Software Engineer at Acme Corp</div>
            <span>San Francisco Bay Area</span>
        </div>
        </body></html>
        """
        data = LinkedInProfileExtractor(html).extract()
        self.assertEqual(data['basic_profile']['location'], "San Francisco Bay Area")

    def test_parses_location_with_punctuation_in_place_name(self):
        # Many real place names include periods, hyphens, or apostrophes
        # (e.g. "St. Louis", "Winston-Salem", "Coeur d'Alene) and must not
        # be rejected by the location character filter.
        html = """
        <html><body>
        <div>
            <h1>Jane Doe</h1>
            <div>Senior Software Engineer at Acme Corp</div>
            <span>St. Louis, MO</span>
        </div>
        </body></html>
        """
        data = LinkedInProfileExtractor(html).extract()
        self.assertEqual(data['basic_profile']['location'], "St. Louis, MO")


if __name__ == "__main__":
    unittest.main()
