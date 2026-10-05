import re

from playwright.sync_api import BrowserContext, Page, expect


def test_playground_source_home(page: Page):
    """Test source service home page title and content while not logged in."""
    page.goto("http://playground-source:8000")

    expect(page).to_have_title(re.compile("Token exchange: source service"))
    expect(page.locator(".content > p")).to_have_text(
        "You should be connected to see your recordings."
    )


def test_playground_target_home(page: Page):
    """Test target service home page title and content while not logged in."""
    page.goto("http://playground-target:8000")

    expect(page).to_have_title(re.compile("Token exchange: target service"))
    expect(page.locator(".content > p")).to_have_text(
        "You should be connected to see your files."
    )


def test_playground_source_login(page: Page):
    """Test source service home page title and content while logged in."""
    page.goto("http://playground-source:8000")

    # Login via keycloak
    page.get_by_text("Login").click()
    expect(page).to_have_title(re.compile("Sign in to menshen"))

    # Fill keycloak login form
    page.locator("id=username").fill("menshen")
    page.locator("id=password").fill("menshen")
    page.locator("id=kc-login").click()

    # We should now be back to the source service and logged in
    expect(page).to_have_title(re.compile("Token exchange: source service"))
    expect(
        page.get_by_role("button", name=re.compile("logout", re.IGNORECASE))
    ).to_be_visible()

    # 3 recordings should be listed
    expect(page.locator("h3")).to_have_text("My recordings")
    expect(page.locator("tbody > tr")).to_have_count(3)


def test_playground_target_login(page: Page):
    """Test target service home page title and content while logged in."""
    page.goto("http://playground-target:8000")

    # Login via keycloak
    page.get_by_text("Login").click()
    expect(page).to_have_title(re.compile("Sign in to menshen"))

    # Fill keycloak login form
    page.locator("id=username").fill("menshen")
    page.locator("id=password").fill("menshen")
    page.locator("id=kc-login").click()

    # We should now be back to the source service and logged in
    expect(page).to_have_title(re.compile("Token exchange: target service"))
    expect(
        page.get_by_role("button", name=re.compile("logout", re.IGNORECASE))
    ).to_be_visible()

    # No files should be present at all
    expect(page.locator("h3")).to_have_text("My files")
    expect(page.locator("tbody > tr")).to_have_count(1)
    expect(page.locator("tbody > tr > td > em")).to_have_text("Your drive is empty.")


def test_playground_source_to_target_flow(context: BrowserContext):
    """Test the source to target token exchange flow."""
    # Login from the source service
    source = context.new_page()
    source.goto("http://playground-source:8000")
    source.get_by_text("Login").click()
    source.locator("id=username").fill("menshen")
    source.locator("id=password").fill("menshen")
    source.locator("id=kc-login").click()
    expect(source).to_have_title(re.compile("Token exchange: source service"))

    # Login from the target service
    target = context.new_page()
    target.goto("http://playground-target:8000")
    target.get_by_text("Login").click()
    # We expect a silent login to occur
    expect(target).to_have_title(re.compile("Token exchange: target service"))

    # Check initial state of the source and target services
    expect(source.locator("tbody > tr")).to_have_count(3)
    expect(target.locator("tbody > tr > td > em")).to_have_text("Your drive is empty.")

    # Perform backup
    source.get_by_test_id("backup-recording-2").click()
    expect(target.locator("tbody > tr > td > em")).to_have_count(0)
    expect(target.locator("tbody > tr > td > b")).to_have_count(1)
