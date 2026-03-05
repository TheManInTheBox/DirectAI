"""Web frontend (agilecloud.ai) smoke tests."""

from __future__ import annotations

import httpx
import pytest


class TestLandingPage:
    """Public landing page."""

    def test_returns_200(self, web_client: httpx.Client) -> None:
        r = web_client.get("/")
        assert r.status_code == 200

    def test_title_contains_directai(self, web_client: httpx.Client) -> None:
        text = web_client.get("/").text
        assert "DirectAI" in text

    def test_branding_inside_your_azure(self, web_client: httpx.Client) -> None:
        text = web_client.get("/").text
        assert "Inside Your Azure" in text

    def test_content_type_html(self, web_client: httpx.Client) -> None:
        r = web_client.get("/")
        assert "text/html" in r.headers.get("content-type", "")


class TestPublicPages:
    """Key marketing pages load."""

    @pytest.mark.parametrize(
        "path",
        ["/pricing", "/waitlist", "/login", "/privacy", "/terms"],
    )
    def test_page_returns_200(self, web_client: httpx.Client, path: str) -> None:
        r = web_client.get(path, follow_redirects=True)
        # /login may redirect to the Entra login page (302 → external),
        # so accept 200 or the follow_redirects may land on the external page.
        assert r.status_code == 200, f"{path} returned {r.status_code}"


class TestDashboardRequiresAuth:
    """Dashboard routes are protected."""

    def test_dashboard_redirects_unauthenticated(
        self, web_client: httpx.Client
    ) -> None:
        r = web_client.get("/dashboard", follow_redirects=False)
        # NextAuth middleware should redirect to /login or /api/auth/signin
        assert r.status_code in (301, 302, 303, 307, 308), (
            f"Expected redirect, got {r.status_code}"
        )


class TestSecurityHeaders:
    """Basic security headers on the web frontend."""

    def test_no_server_leak(self, web_client: httpx.Client) -> None:
        r = web_client.get("/")
        server = r.headers.get("server", "").lower()
        # Should not expose "next.js" or detailed version info
        assert "next" not in server or server == "", (
            f"Server header leaks framework: {server}"
        )

    @pytest.mark.xfail(reason="Next.js does not set X-Frame-Options or CSP by default — configure in next.config.ts")
    def test_x_frame_options_or_csp(self, web_client: httpx.Client) -> None:
        r = web_client.get("/")
        has_xfo = "x-frame-options" in r.headers
        has_csp = "content-security-policy" in r.headers
        # At least one clickjacking mitigation should be present
        assert has_xfo or has_csp, "No clickjacking protection header found"
