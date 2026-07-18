"""Internationalization tests: language switching, Arabic RTL, Chinese."""
from django.test import TestCase

from users.models import User


class I18nTest(TestCase):
    def setUp(self):
        self.agent = User.objects.create_user(
            username="i18n_agent", password="pw", role="agent", status="active"
        )

    def test_set_language_endpoint_switches_and_persists(self):
        r = self.client.post("/i18n/setlang/", {"language": "ar", "next": "/"}, follow=True)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(self.client.cookies.get("django_language").value, "ar")

    def test_arabic_renders_rtl_with_rtl_bootstrap(self):
        self.client.cookies["django_language"] = "ar"
        body = self.client.get("/").content.decode("utf-8")
        self.assertIn('dir="rtl"', body)
        self.assertIn("bootstrap.rtl.min.css", body)
        self.assertIn("المنح الدراسية", body)  # "Scholarships"

    def test_chinese_renders_translated_ltr(self):
        self.client.cookies["django_language"] = "zh-hans"
        body = self.client.get("/").content.decode("utf-8")
        self.assertIn('dir="ltr"', body)
        self.assertIn("奖学金", body)  # "Scholarships"

    def test_english_default_unchanged(self):
        body = self.client.get("/").content.decode("utf-8")
        self.assertIn('dir="ltr"', body)
        self.assertIn("Scholarships", body)

    def test_agent_portal_arabic_rtl(self):
        self.client.force_login(self.agent)
        self.client.cookies["django_language"] = "ar"
        body = self.client.get("/agent/").content.decode("utf-8")
        self.assertIn('dir="rtl"', body)
        self.assertIn("بوابة الوكيل", body)  # "Agent Portal"
