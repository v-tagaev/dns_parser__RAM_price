import os
import requests
import time
import random
import subprocess
import json
from datetime import datetime
from pathlib import Path
from typing import Tuple, Optional
from playwright.sync_api import Browser, Page, BrowserContext
from setup_logger import setup_logger

logger = setup_logger(__name__)


# ============================================================================
# КОНСТАНТЫ
# ============================================================================

PROJECT_DIR = Path(__file__).parent.absolute()
CHROME_PROFILE_DIR = PROJECT_DIR / "chrome_debug_profile"

CHROME_CDP_URL = "http://127.0.0.1:9222"
CONNECT_TIMEOUT_MS = 90000       # таймаут подключения Playwright к CDP
READY_TIMEOUT_SEC = 60           # сколько ждать готовности Chrome
CONNECT_MAX_ATTEMPTS = 3         # сколько раз пробовать connect_over_cdp


# ============================================================================
# ПРОВЕРКА ДОСТУПНОСТИ CHROME
# ============================================================================

def check_chrome_cdp_available() -> bool:
    """Проверяет, отвечает ли Chrome на CDP-порту."""
    try:
        response = requests.get(f"{CHROME_CDP_URL}/json/version", timeout=3)
        if response.status_code == 200:
            logger.info("Chrome с CDP уже запущен и отвечает")
            return True
    except requests.exceptions.RequestException:
        pass
    return False


def wait_for_chrome_ready(timeout_sec: int = READY_TIMEOUT_SEC) -> bool:
    """Ждёт, пока Chrome начнёт отвечать на CDP. Возвращает True/False."""
    logger.info(f"Ждём готовности Chrome (до {timeout_sec} сек)...")
    for i in range(timeout_sec):
        if check_chrome_cdp_available():
            return True
        time.sleep(1)
    logger.error(f"!! Chrome не отвечает за {timeout_sec} секунд")
    return False


# ============================================================================
# ЗАПУСК CHROME (ЛОКАЛЬНО ИЛИ УДАЛЁННО)
# ============================================================================

def launch_chrome_local() -> bool:
    """Запускает Chrome с CDP на текущей машине (для Windows-режима)."""
    chrome_path = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
    if not Path(chrome_path).exists():
        logger.error(f"!! Chrome не найден по пути: {chrome_path}")
        return False

    # Если Chrome уже отвечает — ничего не запускаем
    if check_chrome_cdp_available():
        return True

    cmd = [
        chrome_path,
        "--remote-debugging-port=9222",
        "--remote-debugging-address=0.0.0.0",
        f"--user-data-dir={CHROME_PROFILE_DIR}",
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-blink-features=AutomationControlled",
        "about:blank",
    ]
    try:
        logger.info("Запускаем Chrome с CDP...")
        subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return wait_for_chrome_ready()
    except Exception as e:
        logger.error(f"!! Ошибка при запуске Chrome: {e}")
        return False


def launch_chrome_remote_ssh(host: str, port: int, user: str, password: str) -> bool:
    """
    Запускает Chrome на удалённой Windows-машине через SSH,
    ТОЛЬКО если он ещё не отвечает на CDP.

    Старые процессы Chrome НЕ убиваются.
    """
    # Если Chrome уже отвечает (через SSH-туннель) — не трогаем
    if check_chrome_cdp_available():
        logger.info("Chrome уже запущен, перезапуск не нужен")
        return True

    chrome_path = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
    profile_path = r"D:\Parser_dns_shop_pet_project\parser_ram_dns_shop\parsers\chrome_debug_profile"

    remote_cmd = (
        f'"{chrome_path}" '
        f'--remote-debugging-port=9222 '
        f'--remote-debugging-address=0.0.0.0 '
        f'--user-data-dir="{profile_path}" '
        f'--no-first-run --no-default-browser-check '
        f'--disable-blink-features=AutomationControlled '
        f'about:blank'
    )
    ssh_cmd = [
        "sshpass", "-p", password,
        "ssh",
        "-o", "StrictHostKeyChecking=no",
        "-o", "UserKnownHostsFile=/dev/null",
        "-o", "ConnectTimeout=10",
        "-p", str(port),
        f"{user}@{host}",
        remote_cmd
    ]
    try:
        logger.info("Удалённый запуск Chrome через SSH...")
        subprocess.Popen(ssh_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return wait_for_chrome_ready(timeout_sec=30)
    except Exception as e:
        logger.error(f"!! Не удалось запустить Chrome удалённо: {e}")
        return False


# ============================================================================
# SSH-ТУННЕЛЬ ДЛЯ CDP
# ============================================================================

def setup_ssh_tunnel_for_cdp(host: str, port: int, user: str, password: str,
                             local_cdp_port: int = 9222) -> bool:
    """
    Создаёт SSH-туннель для проброса CDP порта с Windows в контейнер.
    Если туннель уже есть — не создаёт повторно.
    """
    # Проверяем, может, туннель уже установлен
    if check_chrome_cdp_available():
        logger.info("Туннель уже работает, пересоздание не нужно")
        return True

    logger.info(f"Создаём SSH-туннель для CDP до {user}@{host}:{port}...")
    cmd = [
        "sshpass", "-p", password,
        "ssh", "-L", f"{local_cdp_port}:127.0.0.1:9222",
        "-N", "-f",
        "-o", "StrictHostKeyChecking=no",
        "-o", "UserKnownHostsFile=/dev/null",
        "-o", "ExitOnForwardFailure=yes",
        "-o", "ServerAliveInterval=30",
        "-o", "ServerAliveCountMax=3",
        "-p", str(port),
        f"{user}@{host}"
    ]
    try:
        subprocess.run(cmd, check=True, timeout=15)
        time.sleep(2)
        logger.info(f"SSH-туннель установлен, порт {local_cdp_port} -> Windows:9222")
        return True
    except Exception as e:
        logger.error(f"!! SSH-туннель не создан: {e}")
        return False


# ============================================================================
# ПОДКЛЮЧЕНИЕ К CHROME С RETRY
# ============================================================================

def connect_to_chrome_with_retry(playwright):
    """
    Подключается к Chrome через CDP с несколькими попытками.
    Возвращает browser или поднимает исключение.
    """
    last_error = None
    for attempt in range(1, CONNECT_MAX_ATTEMPTS + 1):
        try:
            logger.info(f"Подключение к CDP (попытка {attempt}/{CONNECT_MAX_ATTEMPTS})...")

            # Дожидаемся ответа Chrome перед connect_over_cdp
            if not wait_for_chrome_ready(timeout_sec=15):
                raise RuntimeError("Chrome не отвечает на /json/version")

            browser = playwright.chromium.connect_over_cdp(
                CHROME_CDP_URL,
                timeout=CONNECT_TIMEOUT_MS
            )
            logger.info("Подключение к Chrome успешно")
            return browser

        except Exception as e:
            last_error = e
            logger.warning(f"Попытка {attempt} не удалась: {e}")
            if attempt < CONNECT_MAX_ATTEMPTS:
                time.sleep(10)

    raise RuntimeError(f"Не удалось подключиться к Chrome после {CONNECT_MAX_ATTEMPTS} попыток: {last_error}")


def connect_to_chrome(playwright, url: str, timeout: int = 60000):
    """
    Подключается к Chrome через CDP, возвращает page и browser.
    ПЕРЕИСПОЛЬЗУЕТ существующую вкладку — новую создаёт только при необходимости.
    """
    browser = connect_to_chrome_with_retry(playwright)
    context = browser.contexts[0]

    logger.info(f"Открыто вкладок: {len(context.pages)}")

    # 1. Ищем вкладку с нужным URL
    page = None
    for p in context.pages:
        if url in p.url:
            page = p
            logger.info(f"Найдена вкладка с нужным URL: {p.url}")
            page.reload(wait_until="domcontentloaded", timeout=timeout)
            break

    # 2. Если не нашли — используем первую доступную (даже about:blank)
    if page is None and context.pages:
        page = context.pages[0]
        logger.info(f"Используем существующую вкладку: {page.url}")
        page.goto(url, wait_until="domcontentloaded", timeout=timeout)

    # 3. Если вкладок нет вообще — создаём
    if page is None:
        page = context.new_page()
        logger.info(f"Создаём новую вкладку для {url}")
        page.goto(url, wait_until="domcontentloaded", timeout=timeout)

    # ✅ Ждём полной загрузки
    try:
        page.wait_for_load_state("load", timeout=30000)
    except Exception as e:
        logger.warning(f"load state не дождались: {e}")

    # ✅ Даём странице немного времени на JS
    time.sleep(1.5)

    # 5. Сбрасываем скролл в начало
    try:
        page.evaluate("window.scrollTo(0, 0)")
        time.sleep(0.5)
    except Exception as e:
        logger.warning(f"Не удалось сбросить скролл: {e}")

    return page, browser


# ============================================================================
# ЗАКРЫТИЕ ВСПЛЫВАЮЩИХ ОКОН
# ============================================================================

def close_popups(page: Page, timeout: int = 5000):
    """Закрывает типичные всплывающие окна на сайте."""
    popups = ["Остаться в браузере", "Все верно", "Понятно", "Закрыть", "OK"]
    for text in popups:
        try:
            selector = f'text="{text}"'
            page.wait_for_selector(selector, timeout=timeout, state="visible")
            page.click(selector)
            logger.info(f"Закрыто окно: '{text}'")
            time.sleep(0.5)
        except Exception:
            logger.debug(f"Окно '{text}' не найдено")


# ============================================================================
# ДИАГНОСТИКА
# ============================================================================

def diagnose_page(page: Page, response_status: Optional[int] = None):
    """Собирает диагностическую информацию о странице."""
    logger.info("=" * 60)
    logger.info("ДИАГНОСТИКА СТРАНИЦЫ")
    logger.info("=" * 60)
    logger.info(f"URL: {page.url}")
    logger.info(f"Title: {page.title()}")
    if response_status:
        logger.info(f"HTTP Status: {response_status}")

    try:
        body_text = page.inner_text('body')
        logger.info(f"Body text (первые 200 символов): {body_text[:200]}")
    except Exception as e:
        logger.error(f"Не удалось получить текст страницы: {e}")

    captcha_selectors = [
        'iframe[src*="captcha"]', 'iframe[src*="challenge"]',
        '.g-recaptcha', '[class*="captcha"]', '[id*="captcha"]',
        '#qrator-captcha', '.qrator-captcha',
    ]
    for sel in captcha_selectors:
        if page.query_selector(sel):
            logger.warning(f"!!! Обнаружен элемент: {sel}")

    cookies = page.context.cookies()
    logger.info(f"Cookies: {len(cookies)} шт.")
    logger.info("=" * 60)


# ============================================================================
# ОСНОВНАЯ ФУНКЦИЯ ПОДГОТОВКИ БРАУЗЕРА
# ============================================================================

def setup_browser(playwright, url: str, timeout: int = 60000):
    """Подготавливает браузер для парсинга."""
    is_docker = "AIRFLOW_HOME" in os.environ

    try:
        if is_docker:
            logger.info(f"Режим Docker/Airflow. URL: {url}")
            ssh_host = os.getenv('SSH_HOST', 'host.docker.internal')
            ssh_port = int(os.getenv('SSH_PORT', '22'))
            ssh_user = os.getenv('SSH_USER')
            ssh_password = os.getenv('SSH_PASSWORD')

            # 1. Создаём/переиспользуем SSH-туннель
            if not setup_ssh_tunnel_for_cdp(ssh_host, ssh_port, ssh_user, ssh_password, 9222):
                raise RuntimeError("CDP tunnel failed")

            # 2. Если Chrome не отвечает — запускаем его удалённо через SSH
            if not check_chrome_cdp_available():
                launch_chrome_remote_ssh(ssh_host, ssh_port, ssh_user, ssh_password)

        else:
            logger.info(f"Режим Windows. URL: {url}")
            if not ensure_chrome_is_running_locally():
                raise RuntimeError("!! Не удалось запустить Chrome с CDP")

        # 3. Подключаемся с retry
        page, browser = connect_to_chrome(playwright, url, timeout)

        # 4. Проверка блокировки
        title = ""
        try:
            title = page.title()
        except Exception as e:
            logger.warning(f"Не удалось получить title: {e}")

        logger.info(f"URL: {page.url}")
        logger.info(f"Title: {title}")

        if "Forbidden" in title or "403" in title or "Доступ ограничен" in title:
            logger.error(f"!! 403 Forbidden (title={title!r})")
            raise RuntimeError("Сайт заблокировал доступ (403)")
        
        close_popups(page)

        return page, browser, False
        
    except Exception as e:
        logger.error(f"!! Ошибка при подготовке браузера: {e}")
        raise


def ensure_chrome_is_running_locally() -> bool:
    """Проверяет Chrome на локальной машине (Windows-режим)."""
    if check_chrome_cdp_available():
        return True
    return launch_chrome_local()


# ============================================================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ============================================================================

def scroll_to_bottom(page: Page, max_scrolls: int = 50, pause: float = 2.0):
    """Прокручивает страницу вниз, ожидая подгрузку контента."""
    last_height = 0
    for i in range(max_scrolls):
        height = page.evaluate("() => document.body.scrollHeight")
        if height == last_height:
            logger.info(f"Достигнут конец страницы на прокрутке {i}")
            break

        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")

        waited = 0.0
        new_height = height
        while waited < pause:
            time.sleep(0.1)
            waited += 0.1
            new_height = page.evaluate("() => document.body.scrollHeight")
            if new_height > height:
                break

        logger.info(f"Прокрутка {i+1}: {height} -> {new_height} (ждали {waited:.1f}с)")
        last_height = height
    else:
        logger.warning(f"!! Достигнут максимум прокруток ({max_scrolls})")