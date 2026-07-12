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


if __name__ == "__main__":
    unittest.main()
