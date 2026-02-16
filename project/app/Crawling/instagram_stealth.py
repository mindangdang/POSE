import logging
from typing import List, Optional

from selenium.webdriver.remote.webdriver import WebDriver

logger = logging.getLogger(__name__)


def build_chrome_stealth_args(proxy: Optional[str] = None, user_agent: Optional[str] = None) -> List[str]:
    """Return recommended Chrome args for lower Selenium detectability in server environments."""
    args = [
        "--headless=new",
        "--disable-blink-features=AutomationControlled",
        "--no-sandbox",
        "--disable-dev-shm-usage",
        "--window-size=1280,1696",
        "--lang=ko-KR,ko,en-US,en",
    ]
    if user_agent:
        args.append(f"--user-agent={user_agent}")
    if proxy:
        args.append(f"--proxy-server={proxy}")
    return args


def apply_runtime_stealth(driver: WebDriver) -> None:
    """Apply runtime webdriver-evasion script via CDP if available.

    This should be called once after driver initialization.
    """
    try:
        driver.execute_cdp_cmd(
            "Page.addScriptToEvaluateOnNewDocument",
            {
                "source": """
                    Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
                    Object.defineProperty(navigator, 'platform', {get: () => 'Win32'});
                    Object.defineProperty(navigator, 'language', {get: () => 'ko-KR'});
                """
            },
        )
    except Exception:
        logger.debug("CDP stealth script injection is not available for this driver.", exc_info=True)
