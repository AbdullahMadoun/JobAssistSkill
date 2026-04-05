"""Browser lifecycle management for Playwright with advanced anti-detection."""

import asyncio
import json
import logging
import random
from pathlib import Path
from typing import Optional, Dict, Any, Literal
from playwright.async_api import async_playwright, Browser, BrowserContext, Page, Playwright

from .exceptions import NetworkError

try:
    from playwright_stealth.stealth import Stealth as PlaywrightStealth
    STEALTH_AVAILABLE = True
except ImportError:
    STEALTH_AVAILABLE = False
    PlaywrightStealth = None

logger = logging.getLogger(__name__)

STEALTH_LEVELS = Literal["basic", "moderate", "aggressive"]

STEALTH_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
]

VIEWPORTS = [
    {"width": 1920, "height": 1080},
    {"width": 1680, "height": 1050},
    {"width": 1440, "height": 900},
    {"width": 1536, "height": 864},
    {"width": 1366, "height": 768},
    {"width": 2560, "height": 1440},
    {"width": 1280, "height": 720},
]

CANVAS_NOISE_JS = """
(function() {
    const origGetContext = HTMLCanvasElement.prototype.getContext;
    HTMLCanvasElement.prototype.getContext = function(type, attributes) {
        const ctx = origGetContext.call(this, type, attributes);
        if (type === '2d' && ctx) {
            const origGetImageData = ctx.getImageData;
            ctx.getImageData = function(sx, sy, sw, sh) {
                const imageData = origGetImageData.call(this, sx, sy, sw, sh);
                if (imageData && imageData.data) {
                    const noise = Math.random() * 2 - 1;
                    for (let i = 0; i < imageData.data.length; i += Math.ceil(imageData.data.length / 1000)) {
                        imageData.data[i] = Math.max(0, Math.min(255, imageData.data[i] + Math.floor(noise * 5)));
                    }
                }
                return imageData;
            };
            const origPutImageData = ctx.putImageData;
            ctx.putImageData = function(imageData, dx, dy) {
                return origPutImageData.call(this, imageData, dx, dy);
            };
        }
        return ctx;
    };
})();
"""

WEBGL_NOISE_JS = """
(function() {
    const getParameterProxy = new Proxy(WebGLRenderingContext.prototype.getParameter, {
        apply: function(target, thisArg, args) {
            const param = args[0];
            if (param === 37445) return 'Intel Inc.';
            if (param === 37446) return 'Intel Iris OpenGL Engine';
            if (param === 34072) return 'WEBGL_debug_renderer_info';
            if (param === 7937) return 'Google Inc. (Intel)',
            const value = target.apply(thisArg, args);
            if (typeof value === 'string' && (value.includes('SwiftShader') || value.includes('llvmpipe'))) {
                const fakeGPUs = ['Intel(R) UHD Graphics 630', 'AMD Radeon RX 580', 'NVIDIA GeForce GTX 1060'];
                return fakeGPUs[Math.floor(Math.random() * fakeGPUs.length)];
            }
            return value;
        }
    });
    WebGLRenderingContext.prototype.getParameter = getParameterProxy;
    
    if (WebGL2RenderingContext) {
        const getParameterProxy2 = new Proxy(WebGL2RenderingContext.prototype.getParameter, {
            apply: function(target, thisArg, args) {
                const param = args[0];
                if (param === 37445) return 'Intel Inc.';
                if (param === 37446) return 'Intel Iris OpenGL Engine';
                if (param === 7937) return 'Google Inc. (Intel)',
                const value = target.apply(thisArg, args);
                if (typeof value === 'string' && (value.includes('SwiftShader') || value.includes('llvmpipe'))) {
                    const fakeGPUs = ['Intel(R) UHD Graphics 630', 'AMD Radeon RX 580', 'NVIDIA GeForce GTX 1060'];
                    return fakeGPUs[Math.floor(Math.random() * fakeGPUs.length)];
                }
                return value;
            }
        });
        WebGL2RenderingContext.prototype.getParameter = getParameterProxy2;
    }
})();
"""

NAVIGATOR_OVERRIDE_BASIC = """
Object.defineProperty(navigator, 'webdriver', {
    get: () => undefined,
    configurable: true, enumerable: true
});
Object.defineProperty(navigator, 'plugins', {
    get: () => [1, 2, 3, 4, 5],
    configurable: true, enumerable: true
});
Object.defineProperty(navigator, 'languages', {
    get: () => ['en-US', 'en', 'bl'],
    configurable: true, enumerable: true
});
Object.defineProperty(navigator, 'maxTouchPoints', {
    get: () => 0,
    configurable: true, enumerable: true
});
Object.defineProperty(navigator, 'hardwareConcurrency', {
    get: () => [2, 4, 8][Math.floor(Math.random() * 3)],
    configurable: true, enumerable: true
});
window.chrome = { runtime: {}, loadTimes: function() {}, csi: function() {} };
"""

NAVIGATOR_OVERRIDE_MODERATE = NAVIGATOR_OVERRIDE_BASIC + """
Object.defineProperty(navigator, 'deviceMemory', {
    get: () => 8,
    configurable: true, enumerable: true
});
Object.defineProperty(navigator, 'connection', {
    get: () => ({ effectiveType: '4g', downlink: 10, rtt: 50, saveData: false }),
    configurable: true, enumerable: true
});
Object.defineProperty(navigator, 'platform', {
    get: () => 'Win32',
    configurable: true, enumerable: true
});
Object.defineProperty(navigator, 'vendor', {
    get: () => 'Google Inc.',
    configurable: true, enumerable: true
});
Object.defineProperty(navigator, 'permissions', {
    get: () => ({
        query: (name) => Promise.resolve({ state: 'granted' })
    }),
    configurable: true, enumerable: true
});
"""

NAVIGATOR_OVERRIDE_AGGRESSIVE = NAVIGATOR_OVERRIDE_MODERATE + """
Object.defineProperty(navigator, 'webdriver', {
    get: () => false,
    configurable: true, enumerable: true
});
Object.defineProperty(navigator, 'product', {
    get: () => 'Gecko',
    configurable: true, enumerable: true
});
Object.defineProperty(navigator, 'productSub', {
    get: () => '20030107',
    configurable: true, enumerable: true
});
Object.defineProperty(navigator, 'vendorSub', {
    get: () => '',
    configurable: true, enumerable: true
});
Object.defineProperty(navigator, 'appCodeName', {
    get: () => 'Mozilla',
    configurable: true, enumerable: true
});
Object.defineProperty(navigator, 'appName', {
    get: () => 'Netscape',
    configurable: true, enumerable: true
});
Object.defineProperty(navigator, 'appVersion', {
    get: () => '5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    configurable: true, enumerable: true
});
Object.defineProperty(navigator, 'platform', {
    get: () => 'Win32',
    configurable: true, enumerable: true
});
Object.defineProperty(navigator, 'oscpu', {
    get: () => 'Windows NT 10.0; Win64; x64',
    configurable: true, enumerable: true
});
Object.defineProperty(navigator, 'cpuClass', {
    get: () => 'x64',
    configurable: true, enumerable: true
});
Object.defineProperty(navigator, 'architecture', {
    get: () => 'x64',
    configurable: true, enumerable: true
});
Object.defineProperty(navigator, 'hardwareConcurrency', {
    get: () => 8,
    configurable: true, enumerable: true
});
Object.defineProperty(navigator, 'bluetooth', {
    get: () => undefined,
    configurable: true, enumerable: true
});
Object.defineProperty(navigator, 'clipboard', {
    get: () => ({ read: () => Promise.reject(), write: () => Promise.reject() }),
    configurable: true, enumerable: true
});
Object.defineProperty(navigator, 'credentials', {
    get: () => ({ get: () => null, create: () => null }),
    configurable: true, enumerable: true
});
Object.defineProperty(navigator, 'storage', {
    get: () => ({ estimate: () => Promise.resolve({ usage: 0, quota: 0 }), persist: () => Promise.resolve(false), permissions: () => Promise.resolve({ state: 'granted' }) }),
    configurable: true, enumerable: true
});
Object.defineProperty(navigator, 'xr', {
    get: () => undefined,
    configurable: true, enumerable: true
});
Object.defineProperty(HTMLIFrameElement.prototype, 'contentWindow', {
    get: function() {
        const win = this._contentWindow;
        if (!win) return null;
        return new Proxy(win, {
            get: function(target, prop) {
                if (prop === 'navigator') {
                    return target.navigator;
                }
                return target[prop];
            }
        });
    },
    configurable: true
});
"""

PROXY_DETECTION_BYPASS = """
Object.defineProperty(navigator, 'proxy', {
    get: () => undefined,
    configurable: true, enumerable: true
});
Object.defineProperty(HTMLIFrameElement.prototype, 'contentWindow', {
    get: function() {
        return this._contentWindow;
    }
});
"""

AUTOMATION_DETECTION_REMOVAL = """
delete window.cdc_adoQpoasnfa76pfcZLmcfl_Array;
delete window.cdc_adoQpoasnfa76pfcZLmcfl_Promise;
delete window.cdc_adoQpoasnfa76pfcZLmcfl_Symbol;
delete window.__webdriver_script_fn;
delete window.__webdriver_script_func;
delete window.__webdriver_script_element;
delete window.$cdc_asdjflasutopfhvcZLmcfl_;
delete window.$chrome_asyncScriptInfo;
delete window.selenium;
delete window.driver;
delete window.webdriver;
delete window.__webgl积雪;
delete window.__listener;
"""

BROWSER_ARGS_BASE = [
    "--no-sandbox",
    "--disable-setuid-sandbox",
    "--disable-dev-shm-usage",
    "--no-first-run",
    "--no-zygote",
    "--disable-default-apps",
    "--disable-extensions",
    "--disable-sync",
    "--disable-translate",
    "--metrics-recording-only",
    "--mute-audio",
    "--no-default-browser-check",
    "--no-pingsend",
    "--disable-logging",
    "--log-file=/dev/null",
]

BROWSER_ARGS_BASIC = BROWSER_ARGS_BASE + [
    "--disable-blink-features=AutomationControlled",
    "--disable-accelerated-2d-canvas",
    "--disable-gpu",
]

BROWSER_ARGS_MODERATE = BROWSER_ARGS_BASIC + [
    "--disable-background-timer-throttling",
    "--disable-backgrounding-occluded-windows",
    "--disable-renderer-backgrounding",
    "--disable-client-side-phishing-detection",
    "--disable-oopr-debug-crash-dump",
    "--no-crash-upload",
    "--disable-ipc-flooding-protection",
    "--disable-renderer-accessibility",
    "--disable-background-networking",
    "--disable-hang-monitor",
    "--disable-popup-blocking",
    "--disable-back-forward-cache",
    "--disable-browser-candidate-vectors",
    "--enable-features=NetworkService,NetworkServiceInProcess",
    "--force-color-profile=srgb",
    "--disable-font-subpixel-positioning",
]

BROWSER_ARGS_AGGRESSIVE = BROWSER_ARGS_MODERATE + [
    "--disable-bluetooth",
    "--disable-camera",
    "--disable-databases",
    "--disable-display-locales",
    "--disable-domain-reliability",
    "--disable-external-intent-requests",
    "--disable-features=ImprovedYardstickDistanceCalculation,LocalLinks",
    "--disable-geolocation",
    "--disable-get-user-media",
    "--disable-hooke",
    "--disable-image-loading",
    "--disable-ipv6",
    "--disable-media-session-api",
    "--disable-namespace-sandbox",
    "--disable-navigation-traversal",
    "--disable-ping",
    "--disable-prompt-for-repost",
    "--disable-quic",
    "--disable-read-image",
    "--disable-vertical-scroll",
    "--disable-web-security",
    "--disable-window-name-setting",
    "--enable-async-dns",
    "--enable-auto-reload",
    "--enable-features=NetworkPrediction,NetworkPredictionV2",
    "--enable-logging",
    "--ignore-certificate-errors",
    "--ignore-certificate-errors-spki-list",
    "--ignore-ssl-errors",
    "--no-experiments",
    "--no-proxy-server",
    "--single-process",
    "--service-worker-gc-notification-interval=3600000",
    "--touch-events=enabled",
]


class BrowserManager:
    """Async context manager for Playwright browser with advanced stealth."""
    
    STEALTH_SCRIPTS = {
        "basic": NAVIGATOR_OVERRIDE_BASIC,
        "moderate": NAVIGATOR_OVERRIDE_MODERATE + CANVAS_NOISE_JS,
        "aggressive": NAVIGATOR_OVERRIDE_AGGRESSIVE + CANVAS_NOISE_JS + WEBGL_NOISE_JS + PROXY_DETECTION_BYPASS + AUTOMATION_DETECTION_REMOVAL,
    }
    
    BROWSER_ARGS = {
        "basic": BROWSER_ARGS_BASIC,
        "moderate": BROWSER_ARGS_MODERATE,
        "aggressive": BROWSER_ARGS_AGGRESSIVE,
    }
    
    def __init__(
        self,
        headless: bool = True,
        slow_mo: int = 0,
        viewport: Optional[Dict[str, int]] = None,
        user_agent: Optional[str] = None,
        stealth: bool = True,
        stealth_level: STEALTH_LEVELS = "moderate",
        **launch_options: Any
    ):
        """
        Initialize browser manager with anti-detection.
        
        Args:
            headless: Run browser in headless mode
            slow_mo: Slow down operations by specified milliseconds
            viewport: Browser viewport size
            user_agent: Custom user agent string
            stealth: Enable advanced anti-detection
            stealth_level: Anti-detection level ("basic", "moderate", "aggressive")
            **launch_options: Additional Playwright launch options
        """
        self.headless = headless
        self.slow_mo = slow_mo
        self.stealth = stealth
        self.stealth_level = stealth_level if stealth else "basic"
        
        if stealth:
            self.viewport = viewport or random.choice(VIEWPORTS)
            self.user_agent = user_agent or random.choice(STEALTH_USER_AGENTS)
        else:
            self.viewport = viewport or {"width": 1280, "height": 720}
            self.user_agent = user_agent
            
        self.launch_options = launch_options
        
        self._playwright: Optional[Playwright] = None
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        self._page: Optional[Page] = None
        self._is_authenticated = False
    
    async def __aenter__(self) -> "BrowserManager":
        await self.start()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.close()
    
    async def start(self) -> None:
        """Start Playwright and launch browser with stealth."""
        try:
            self._playwright = await async_playwright().start()
            
            launch_options = {
                "headless": self.headless,
                "slow_mo": self.slow_mo,
            }
            
            if self.stealth:
                launch_options["args"] = self.BROWSER_ARGS[self.stealth_level].copy()
            
            launch_options.update(self.launch_options)
            
            self._browser = await self._playwright.chromium.launch(**launch_options)
            
            logger.info(f"Browser launched (headless={self.headless}, stealth={self.stealth}, level={self.stealth_level})")
            
            context_options: Dict[str, Any] = {
                "viewport": self.viewport,
                "user_agent": self.user_agent,
                "locale": "en-US",
                "timezone_id": "America/New_York",
                "geolocation": {"longitude": -73.935242, "latitude": 40.730610},
                "permissions": ["geolocation"],
            }
            
            if self.stealth:
                context_options["ignore_https_errors"] = True
                context_options["base_url"] = "https://www.linkedin.com"
            
            self._context = await self._browser.new_context(**context_options)
            
            await self._apply_stealth_init_script()
            
            self._page = await self._context.new_page()
            
            if self.stealth and STEALTH_AVAILABLE and PlaywrightStealth:
                try:
                    stealth_instance = PlaywrightStealth()
                    await stealth_instance.apply_stealth_async(self._page)
                    logger.info("Playwright-stealth applied successfully")
                except Exception as e:
                    logger.warning(f"Playwright-stealth failed: {e}")
            
            logger.info("Browser context and page created")
            
        except Exception as e:
            await self.close()
            raise NetworkError(f"Failed to start browser: {e}")
    
    async def _apply_stealth_init_script(self) -> None:
        """Apply stealth scripts BEFORE any page is created via context-level init script."""
        if not self.stealth:
            return
        
        stealth_script = self.STEALTH_SCRIPTS[self.stealth_level]
        
        await self._context.add_init_script(stealth_script)
        
        logger.debug(f"Stealth init script applied (level={self.stealth_level})")
    
    async def close(self) -> None:
        """Close browser and cleanup."""
        try:
            if self._page:
                await self._page.close()
                self._page = None
            if self._context:
                await self._context.close()
                self._context = None
            if self._browser:
                await self._browser.close()
                self._browser = None
            if self._playwright:
                await self._playwright.stop()
                self._playwright = None
            logger.info("Browser closed")
        except Exception as e:
            logger.error(f"Error closing browser: {e}")
    
    async def new_page(self) -> Page:
        if not self._context:
            raise RuntimeError("Browser context not initialized")
        page = await self._context.new_page()
        if self.stealth and PlaywrightStealth:
            stealth_instance = PlaywrightStealth()
            await stealth_instance.apply_stealth_async(page)
        return page
    
    @property
    def page(self) -> Page:
        if not self._page:
            raise RuntimeError("Browser not started")
        return self._page
    
    @property
    def context(self) -> BrowserContext:
        if not self._context:
            raise RuntimeError("Browser not initialized")
        return self._context
    
    @property
    def browser(self) -> Browser:
        if not self._browser:
            raise RuntimeError("Browser not started")
        return self._browser
    
    async def save_session(self, filepath: str) -> None:
        if not self._context:
            raise RuntimeError("No browser context to save")
        storage_state = await self._context.storage_state()
        path = Path(filepath)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(filepath, 'w') as f:
            json.dump(storage_state, f, indent=2)
        logger.info(f"Session saved to {filepath}")
    
    async def load_session(self, filepath: str) -> None:
        if not Path(filepath).exists():
            raise FileNotFoundError(f"Session file not found: {filepath}")
        
        if self._context:
            await self._context.close()
        
        if not self._browser:
            raise RuntimeError("Browser not started")
        
        self._context = await self._browser.new_context(
            storage_state=filepath,
            viewport=self.viewport,
            user_agent=self.user_agent,
        )
        
        await self._apply_stealth_init_script()
        
        if self._page:
            await self._page.close()
        self._page = await self._context.new_page()
        
        if self.stealth and PlaywrightStealth:
            stealth_instance = PlaywrightStealth()
            await stealth_instance.apply_stealth_async(self._page)
        
        self._is_authenticated = True
        logger.info(f"Session loaded from {filepath}")
    
    async def set_cookie(self, name: str, value: str, domain: str = ".linkedin.com") -> None:
        if not self._context:
            raise RuntimeError("No browser context")
        await self._context.add_cookies([{
            "name": name, "value": value, "domain": domain, "path": "/"
        }])
    
    @property
    def is_authenticated(self) -> bool:
        return self._is_authenticated
    
    @is_authenticated.setter
    def is_authenticated(self, value: bool) -> None:
        self._is_authenticated = value
