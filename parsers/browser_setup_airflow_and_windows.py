import os
import requests
import time
import random
import subprocess
import logging
import json
from datetime import datetime
from pathlib import Path
from typing import Tuple, Optional
from playwright.sync_api import sync_playwright, Browser, Page, BrowserContext
try:
    from playwright_stealth import stealth_sync
except ImportError:
    stealth_sync = None

# ============================================================================
# ЛОГИРОВАНИЕ
# ============================================================================

def setup_logger(name: str, log_file: str = "parser.log"):
    """Настраивает логирование с выводом в файл и консоль."""
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)
    
    # Формат логов
    formatter = logging.Formatter(
        fmt='%(asctime)s | %(levelname)-8s | %(name)s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Обработчик для файла
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    
    # Обработчик для консоли
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    return logger

logger = setup_logger(__name__)

# ============================================================================
# КОНСТАНТЫ И КОНФИГУРАЦИЯ
# ============================================================================

# User-Agent список (для ротации)
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
]

# Параметры retry-логики
RETRY_CONFIG = {
    'max_retries': 5,
    'initial_delay': 1,  # секунды
    'max_delay': 60,  # максимальная задержка
    'exponential_base': 2,  # для экспоненциального увеличения
}

# Пути к файлам
PROJECT_DIR = Path(__file__).parent.absolute()
COOKIES_DIR = PROJECT_DIR / "cookies"
CHROME_PROFILE_DIR = PROJECT_DIR / "chrome_debug_profile"
COOKIES_DIR.mkdir(exist_ok=True)

# ============================================================================
# УПРАВЛЕНИЕ COOKIES И СЕССИЕЙ
# ============================================================================

class CookieManager:
    """Управляет сохранением и загрузкой cookies."""
    
    def __init__(self, cookies_dir: Path = COOKIES_DIR):
        self.cookies_dir = cookies_dir
        self.cookies_dir.mkdir(exist_ok=True)
        logger.info(f"CookieManager инициализирован. Папка: {self.cookies_dir}")
    
    def get_cookie_file(self, domain: str) -> Path:
        """Возвращает путь к файлу cookies для домена."""
        safe_domain = domain.replace('/', '_').replace(':', '_')
        return self.cookies_dir / f"{safe_domain}_cookies.json"
    
    def save_cookies(self, page: Page, domain: str) -> None:
        """Сохраняет cookies из страницы в JSON файл."""
        try:
            cookies = page.context.cookies()
            cookie_file = self.get_cookie_file(domain)
            
            with open(cookie_file, 'w', encoding='utf-8') as f:
                json.dump(cookies, f, indent=2, ensure_ascii=False)
            
            logger.info(f"✅ Cookies сохранены ({len(cookies)} шт.) в {cookie_file}")
        except Exception as e:
            logger.error(f"❌ Ошибка при сохранении cookies: {e}")
    
    def load_cookies(self, context: BrowserContext, domain: str) -> bool:
        """Загружает cookies из файла в контекст браузера."""
        try:
            cookie_file = self.get_cookie_file(domain)
            
            if not cookie_file.exists():
                logger.warning(f"⚠️ Файл cookies не найден: {cookie_file}")
                return False
            
            with open(cookie_file, 'r', encoding='utf-8') as f:
                cookies = json.load(f)
            
            # Приводим sameSite к допустимым значениям
            valid_same_site = {'Strict', 'Lax', 'None'}
            for cookie in cookies:
                if 'sameSite' in cookie:
                    if cookie['sameSite'] not in valid_same_site:
                        logger.debug(f"Исправляем sameSite '{cookie['sameSite']}' -> 'Lax' для cookie {cookie.get('name')}")
                        cookie['sameSite'] = 'Lax'
                else:
                    # Playwright требует наличия sameSite, добавляем Lax по умолчанию
                    cookie['sameSite'] = 'Lax'
                
                # Если есть url вместо domain, Playwright может потребовать. Убедимся, что есть domain.
                if 'domain' not in cookie and 'url' not in cookie:
                    cookie['domain'] = '.dns-shop.ru'  # замените на ваш домен
                # Убираем нестандартные поля, которые могут мешать (необязательно)
                # например, 'hostOnly', 'session' и т.п.
                for key in list(cookie.keys()):
                    if key not in ('name', 'value', 'url', 'domain', 'path', 'expires', 'httpOnly', 'secure', 'sameSite'):
                        del cookie[key]
            
            context.add_cookies(cookies)
            logger.info(f"✅ Cookies загружены ({len(cookies)} шт.) из {cookie_file}")
            return True
        except Exception as e:
            logger.error(f"❌ Ошибка при загрузке cookies: {e}")
            return False
    
    def clear_cookies(self, domain: str) -> None:
        """Удаляет файл cookies для домена."""
        try:
            cookie_file = self.get_cookie_file(domain)
            if cookie_file.exists():
                cookie_file.unlink()
                logger.info(f"✅ Cookies удалены: {cookie_file}")
        except Exception as e:
            logger.error(f"❌ Ошибка при удалении cookies: {e}")

# ============================================================================
# RETRY-ЛОГИКА С ЭКСПОНЕНЦИАЛЬНОЙ ЗАДЕРЖКОЙ
# ============================================================================

class RetryHandler:
    """Обработчик повторных попыток с экспоненциальной задержкой."""
    
    def __init__(self, config: dict = None):
        self.config = config or RETRY_CONFIG
        logger.info(f"RetryHandler инициализирован с конфигом: {self.config}")
    
    def calculate_delay(self, attempt: int) -> float:
        """
        Вычисляет задержку для попытки.
        Формула: initial_delay * (exponential_base ^ attempt) + случайный jitter
        """
        delay = self.config['initial_delay'] * (
            self.config['exponential_base'] ** attempt
        )
        # Ограничиваем максимальной задержкой
        delay = min(delay, self.config['max_delay'])
        # Добавляем jitter (±20%)
        jitter = delay * random.uniform(-0.2, 0.2)
        return delay + jitter
    
    def retry(self, func, *args, **kwargs):
        """
        Выполняет функцию с повторными попытками.
        
        Args:
            func: функция для выполнения
            *args, **kwargs: аргументы функции
        
        Returns:
            результат функции или None
        """
        for attempt in range(self.config['max_retries']):
            try:
                logger.debug(f"Попытка {attempt + 1}/{self.config['max_retries']}")
                result = func(*args, **kwargs)
                logger.info(f"✅ Успех на попытке {attempt + 1}")
                return result
            except Exception as e:
                if attempt < self.config['max_retries'] - 1:
                    delay = self.calculate_delay(attempt)
                    logger.warning(
                        f"⚠️ Попытка {attempt + 1} не удалась: {e}. "
                        f"Ожидание {delay:.2f}с перед повтором..."
                    )
                    time.sleep(delay)
                else:
                    logger.error(
                        f"❌ Все {self.config['max_retries']} попытки исчерпаны. "
                        f"Последняя ошибка: {e}"
                    )
                    raise

# ============================================================================
# ПРОВЕРКА И ЗАПУСК CHROME
# ============================================================================

def check_chrome_cdp_available():
    """Проверяет, доступен ли Chrome на порту 9222."""
    try:
        response = requests.get(
            "http://localhost:9222/json/version",
            timeout=2
        )
        if response.status_code == 200:
            logger.info("✅ Chrome с CDP уже запущен на порту 9222")
            return True
    except requests.exceptions.RequestException as e:
        logger.debug(f"Chrome не доступен: {e}")
    return False

def launch_chrome_with_cdp():
    chrome_path = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
    if not Path(chrome_path).exists():
        logger.error(f"❌ Chrome не найден по пути: {chrome_path}")
        return False

    profile_path = CHROME_PROFILE_DIR
    cmd = [
        chrome_path,
        "--remote-debugging-port=9222",
        f"--user-data-dir={profile_path}",
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-blink-features=AutomationControlled",
    ]
    try:
        logger.info("🔧 Запускаем Chrome с CDP на порту 9222...")
        subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for _ in range(10):
            time.sleep(1)
            if check_chrome_cdp_available():
                logger.info("✅ Chrome успешно запущен и доступен")
                return True
        logger.error("❌ Chrome не ответил после запуска")
        return False
    except Exception as e:
        logger.error(f"❌ Ошибка при запуске Chrome: {e}")
        return False

def ensure_chrome_is_running_with_cdp():
    """Проверяет Chrome, если не запущен — запускает."""
    if check_chrome_cdp_available():
        return True
    return launch_chrome_with_cdp()

# ============================================================================
# ЗАКРЫТИЕ ВСПЛЫВАЮЩИХ ОКОН
# ============================================================================

def close_popups(page: Page, timeout: int = 5000):
    """Закрывает типичные всплывающие окна на сайте."""
    popups = [
        ("Остаться в браузере", timeout),
        ("Все верно", timeout),
        ("Понятно", timeout),
        ("Закрыть", timeout),
        ("OK", timeout),
    ]
    
    for text, popup_timeout in popups:
        try:
            selector = f'text="{text}"'
            page.wait_for_selector(
                selector,
                timeout=popup_timeout,
                state="visible"
            )
            page.click(selector)
            logger.info(f"✅ Закрыто окно: '{text}'")
            time.sleep(1)
        except Exception:
            logger.debug(f"ℹ️ Окно '{text}' не найдено")

# ============================================================================
# ОСНОВНАЯ ФУНКЦИЯ ПОДГОТОВКИ БРАУЗЕРА
# ============================================================================

def setup_browser(playwright, url: str, use_cookies: bool = True, headless: bool = False):
    """
    Возвращает (page, browser, should_close)
    """
    cookie_manager = CookieManager()
    is_docker = "AIRFLOW_HOME" in os.environ
    logger.info(f"🚀 Инициализация браузера. Docker: {is_docker}, URL: {url}")

    try:
        if is_docker:
            logger.info("🐳 Режим Docker/Airflow. Запускаем Chromium...")
            subprocess.Popen(["Xvfb", ":99", "-screen", "0", "1280x800x24"],
                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

            # Ждём, пока Xvfb не создаст сокет
            for attempt in range(10):
                if os.path.exists('/tmp/.X11-unix/X99'):
                    logger.info("Xvfb готов (сокет обнаружен)")
                    break
                time.sleep(1)
            else:
                logger.error("Xvfb не поднялся за 10 секунд")

            os.environ['DISPLAY'] = ':99'
            time.sleep(1)  # небольшая пауза перед запуском браузера
            logger.info("дошли до запуска браузера")
            browser = playwright.chromium.launch(
                headless=False,
                env={"DISPLAY": ":99"},
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--disable-infobars",
                    "--no-sandbox",
                    "--lang=ru-RU",
                    "--display=:99",
                ],
            )
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                        "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
                locale="ru-RU",
                timezone_id="Europe/Moscow",
                viewport={"width": 1366, "height": 768},
            )
            context.add_init_script(
                "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
            )
            # Загружаем cookies ДО перехода
            if use_cookies:
                cookie_manager.load_cookies(context, url)

            page = context.new_page()
            if stealth_sync:
                stealth_sync(page)

            logger.info(f"Переходим на {url}")
            response = page.goto(url, wait_until="domcontentloaded", timeout=60000)
            logger.info(f"HTTP статус: {response.status if response else 'N/A'}")
            # Имитация человеческого поведения
            time.sleep(random.uniform(3, 7))
            # Двигаем мышь случайным образом
            for _ in range(random.randint(3, 6)):
                x = random.randint(100, 800)
                y = random.randint(100, 600)
                page.mouse.move(x, y, steps=random.randint(10, 20))
                time.sleep(random.uniform(0.3, 1.5))
            # Клик в случайное место (желательно не по ссылке, чтобы не уйти со страницы)
            page.mouse.click(random.randint(400, 700), random.randint(300, 500))
            time.sleep(random.uniform(2, 5))
            # Скролл страницы
            page.mouse.wheel(0, random.randint(300, 800))
            time.sleep(random.uniform(1, 2))
            page.mouse.wheel(0, -random.randint(200, 500))

            # Ожидание появления куки qrator_jsid или изменения заголовка
            try:
                page.wait_for_function(
                    "() => document.cookie.includes('qrator_jsid') || document.title.includes('DNS')",
                    timeout=60000
                )
                page.wait_for_load_state("networkidle")
                logger.info("✅ Qrator пройден, кука получена")
            except Exception:
                logger.warning("❌ Qrator не пройден, сохраняем диагностику")
                page.screenshot(path="/opt/airflow/logs/qrator_fail.png")
                with open("/opt/airflow/logs/qrator_fail.html", "w") as f:
                    f.write(page.content())
            #---------------------------------------------------
            #проверка браузера почему 401 страница
            if response:
                logger.info("=== Заголовки ответа ===")
                for key, value in response.headers.items():
                    logger.info(f"  {key}: {value}")
            logger.info("=== Текст страницы (первые 500 символов) ===")
            try:
                body_text = page.inner_text('body')
                logger.info(body_text[:500])
            except Exception as e:
                logger.error(f"Не удалось получить текст страницы: {e}")
            logger.info("=== Поиск признаков капчи/антибота ===")
            captcha_selectors = [
                'iframe[src*="captcha"]',
                'iframe[src*="challenge"]',
                '.g-recaptcha',
                '[class*="captcha"]',
                '[id*="captcha"]',
                '#qrator-captcha',
                '.qrator-captcha',
            ]
            found_any = False
            for sel in captcha_selectors:
                if page.query_selector(sel):
                    logger.warning(f"🔐 Обнаружен элемент: {sel}")
                    found_any = True
            if not found_any:
                logger.info("ℹ️ Капча или специфические элементы не обнаружены.")
            logger.info(f"Заголовок вкладки: {page.title()}")
            logger.info("=== Cookies после ответа ===")
            cookies = page.context.cookies()
            for c in cookies:
                logger.info(f"  {c['name']}: {c['value'][:30]}...")  # обрезаем длинные значения
            #-------------------------------------------------------
            # Если статус не 200, сохраняем скриншот и HTML
            if response and response.status != 200:
                screenshot_path = "/opt/airflow/logs/dns_error.png"
                html_path = "/opt/airflow/logs/dns_error.html"
                try:
                    page.screenshot(path=screenshot_path)
                    with open(html_path, "w", encoding="utf-8") as f:
                        f.write(page.content())
                    logger.info(f"📸 Сохранены диагностические файлы: {screenshot_path}, {html_path}")
                except Exception as e:
                    logger.error(f"Не удалось сохранить диагностические файлы: {e}")

            # Ожидание qrator (если нужно)
            try:
                page.wait_for_function(
                    "() => document.cookie.includes('qrator_jsid') && !document.title.includes('робот')",
                    timeout=30_000,
                )
                page.wait_for_load_state("networkidle")
            except Exception:
                page.screenshot(path="/tmp/qrator_fail.png")
                with open("/tmp/qrator_fail.html", "w") as f:
                    f.write(page.content())
            should_close = True
        else:
            # === Режим Windows ==================================================
            logger.info("💻 Режим Windows. Подключаемся к Chrome через CDP...")
            if not ensure_chrome_is_running_with_cdp():
                raise RuntimeError("Не удалось запустить Chrome с CDP")
            browser = playwright.chromium.connect_over_cdp("http://localhost:9222")
            context = browser.contexts[0]
            page = None
            for open_page in context.pages:
                if url in open_page.url:
                    page = open_page
                    logger.info(f"Найдена вкладка, обновляем: {page.url}")
                    page.reload(wait_until="domcontentloaded", timeout=60000)
                    break
            if not page:
                page = context.new_page()
                logger.info(f"Создаем новую вкладку для {url}")
                page.goto(url, wait_until="domcontentloaded", timeout=60000)
            should_close = False

        # Закрываем всплывающие окна
        close_popups(page)

        # Проверка на блокировку
        if "Forbidden" in page.title() or "Доступ ограничен" in page.content():
            logger.error("❌ Сайт вернул 403 Forbidden")
            if should_close:
                browser.close()
            raise RuntimeError("Сайт заблокировал доступ (403)")

        time.sleep(random.uniform(2, 4))
        logger.info("✅ Браузер успешно подготовлен")
        return page, browser, should_close
    except Exception as e:
        logger.error(f"❌ Ошибка при подготовке браузера: {e}")
        raise

# ============================================================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ДЛЯ РАБОТЫ С БРАУЗЕРОМ
# ============================================================================

def safe_navigate(
    page: Page,
    url: str,
    retry_handler: RetryHandler = None,
    timeout: int = 60000
) -> bool:
    """
    Безопасный переход на URL с retry-логикой.
    
    Args:
        page: страница Playwright
        url: URL для перехода
        retry_handler: обработчик повторов
        timeout: таймаут в миллисекундах
    
    Returns:
        True если успешно, False если ошибка
    """
    retry_handler = retry_handler or RetryHandler()
    
    def navigate():
        logger.debug(f"Переходим на {url}")
        response = page.goto(
            url,
            wait_until="domcontentloaded",
            timeout=timeout
        )
        if response and response.status >= 400:
            raise RuntimeError(f"HTTP {response.status}")
        return True
    
    try:
        retry_handler.retry(navigate)
        logger.info(f"✅ Успешно перешли на {url}")
        return True
    except Exception as e:
        logger.error(f"❌ Не удалось перейти на {url}: {e}")
        return False

def safe_click(
    page: Page,
    selector: str,
    retry_handler: RetryHandler = None,
    timeout: int = 5000
) -> bool:
    """
    Безопасный клик по элементу с retry-логикой.
    """
    retry_handler = retry_handler or RetryHandler()
    
    def click():
        page.wait_for_selector(selector, timeout=timeout, state="visible")
        page.click(selector)
        return True
    
    try:
        retry_handler.retry(click)
        logger.info(f"✅ Клик по '{selector}' успешен")
        return True
    except Exception as e:
        logger.error(f"❌ Не удалось кликнуть по '{selector}': {e}")
        return False

def safe_fill(
    page: Page,
    selector: str,
    text: str,
        retry_handler: RetryHandler = None,
    timeout: int = 5000
) -> bool:
    """
    Безопасное заполнение поля с retry-логикой.
    """
    retry_handler = retry_handler or RetryHandler()
    
    def fill():
        page.wait_for_selector(selector, timeout=timeout, state="visible")
        page.fill(selector, text)
        return True
    
    try:
        retry_handler.retry(fill)
        logger.info(f"✅ Поле '{selector}' заполнено")
        return True
    except Exception as e:
        logger.error(f"❌ Не удалось заполнить '{selector}': {e}")
        return False