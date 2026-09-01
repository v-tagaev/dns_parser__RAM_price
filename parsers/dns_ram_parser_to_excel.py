import os
import random
import time
import re
import subprocess
import requests
import pandas as pd
from datetime import datetime, timezone
from playwright.sync_api import sync_playwright
from openpyxl import load_workbook
from openpyxl.utils import get_column_letter

def ensure_chrome_is_running_with_cdp():
    """
    Функция проверяет, доступен ли порт 9222.
    Если порт закрыт, она сама запускает Chrome в режиме удаленной отладки.
    """
    try:
        # Проверяем, отвечает ли уже какой-то Chrome на порту 9222
        response = requests.get("http://localhost:9222/json/version", timeout=2)
        if response.status_code == 200:
            print("ℹ️ Отладочный Chrome уже запущен, подключаемся к нему...")
            return True
    except requests.exceptions.RequestException:
        # Если получили ошибку соединения, значит порт закрыт — нужно запускать Chrome
        print("🔧 Отладочный Chrome не найден. Запускаем автоматически...")
        
    # Стандартный путь к Chrome на Windows
    chrome_path = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
    # Создаем папку для профиля прямо внутри папки пет-проекта, чтобы не мусорить в системе
    project_dir = os.path.dirname(os.path.abspath(__file__))
    profile_path = os.path.join(project_dir, "chrome_debug_profile")
    
    # Формируем команду запуска (точно такую же, как мы писали в cmd)
    cmd = [
        chrome_path,
        "--remote-debugging-port=9222",
        f'--user-data-dir={profile_path}',
        "--no-first-run",
        "--no-default-browser-check"
    ]
    
    try:
        # subprocess.Popen запускает процесс асинхронно, чтобы скрипт Python не завис 
        # в ожидании закрытия браузера, а пошел выполнять код дальше
        subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        # Даем браузеру 3 секунды, чтобы он успел инициализироваться и открыть порт
        time.sleep(3)
        return True
    except Exception as e:
        print(f"❌ Не удалось автоматически запустить Chrome: {e}")
        print("💡 Пожалуйста, убедитесь, что путь к chrome.exe указан верно.")
        return False

def parser_dns_auto_cdp(url_that_we_need,output_file):
    url = url_that_we_need
    data = []

    # ШАГ 1: Автоматически проверяем/запускаем браузер
    if not ensure_chrome_is_running_with_cdp():
        return

    # ШАГ 2: Подключаемся через Playwright
    cdp_url = "http://localhost:9222"
    with sync_playwright() as p:
        try:
            browser = p.chromium.connect_over_cdp(cdp_url)
            context = browser.contexts[0] # Берем первый доступный контекст
            
            # Проверяем, открыта ли уже вкладока
            page = None
            for open_page in context.pages:
                if url in open_page.url:
                    page = open_page
                    print(f"!!Найдена открытая вкладка, обновляем ее, и затем парсим: {page.url}")
                    break
            
            # Если нужной вкладки нет, создаем новую и сами переходим по URL
            if not page:
                page = context.new_page()
                print(f"Переходим на страницу: {url}")
                page.goto(url, wait_until="domcontentloaded", timeout=60000)
                
                # ---- блок обработки всплывающих окон ----
                print("Проверяем наличие всплывающего окна 'В приложении удобнее'...")
                try:
                    # DNS часто меняет селекторы, но текст на кнопке остается. 
                    # text="Остаться в браузере" — ищет элемент именно по его текстовому содержимому.
                    # timeout=5000 — ждем окно не более 5 секунд. Если оно не появилось, идем дальше.
                    close_button_selector = 'text="Остаться в браузере"'
                    # Ждем, пока кнопка станет видимой на экране
                    page.wait_for_selector(close_button_selector, timeout=5000, state="visible")
                    # Кликаем по ней
                    page.click(close_button_selector)
                    print("Успешно нажали кнопку 'Остаться в браузере'!")
                    # Даем сайту 1-2 секунды, чтобы окно плавно исчезло и не мешало парсингу
                    time.sleep(2)
                    
                except Exception:
                    print("ℹ️ Всплывающее окно не появилось или селектор изменился. Продолжаем работу.")

                # --------
                print("Проверяем наличие всплывающего окна 'Ваш город'...")
                try:
                    close_button_selector = 'text="Все верно"'
                    page.wait_for_selector(close_button_selector, timeout=5000, state="visible")
                    page.click(close_button_selector)
                    print("Успешно нажали кнопку 'Все верно'!")
                    time.sleep(2)
                except Exception:
                    print("Всплывающее окно не появилось или селектор изменился. Продолжаем работу.")
                # ---- ----
                    print("Проверяем наличие всплывающего окна 'Сайт использует cookies'...")
                    try:
                        close_button_selector = 'text="Понятно"'
                        page.wait_for_selector(close_button_selector, timeout=5000, state="visible")
                        page.click(close_button_selector)
                        print("Успешно нажали кнопку 'Понятно'!")
                        time.sleep(2)
                    except Exception:
                        print("Всплывающее окно не появилось или селектор изменился. Продолжаем работу.")
                # ---- КОНЕЦ БЛОКА ОБРАБОТКИ ВСПЛЫВАЮЩЕГО ОКНА ----

                # Итоговая небольшая пауза для окончательной прогрузки всех карточек
                time.sleep(random.randint(3, 5))
                
        except Exception as e:
            print(f"❌ Ошибка подключения Playwright к порту 9222: {e}")
            return

        # Проверка на блокировку IP-адреса
        if "Forbidden" in page.title() or "Доступ ограничен" in page.content():
            print("❌ Защита сайта заблокировала сессию (403 Forbidden).")
            return   
#---------------------------------------------------------------------------------
 # САМ ПАРСИНГ                     

# Ищем все карточки товаров на странице по CSS-классу '.catalog-product'
        products = page.query_selector_all('.catalog-product')
        print(f"📦 Найдено элементов на странице: {len(products)}")

        # Итерируемся (проходим циклом) по каждой найденной карточке товара
        for product in products:
            try:
                # Ищем элемент с названием плашки памяти
                name_elem = product.query_selector('.catalog-product__name')
                if not name_elem:
                    continue  # Если названия нет (например, это баннер), пропускаем элемент
                # Заменяем найденный мусор на пустоту, а .str.strip() уберет случайные пробелы по краям
                full_name_temp = name_elem.inner_text().strip()
                full_name = re.sub(r'Оперативная память\s*(?:SODIMM)?\s*',' ', full_name_temp).strip()
                # заберем спеку, она немного отделльно
                spec_ram = name_elem.get_attribute("title")                
                #print(f'spec_ram {spec_ram}')
                # Изолированный блок try-except для цены (чтобы из-за одной ошибки не падал весь цикл)
                try:
                    price_elem = product.query_selector('.product-buy__price')
                    if price_elem:
                        # Удаляем знак рубля, вырезаем пробелы-разделители (например: "10 500" -> "10500")
                        price_text = price_elem.inner_text().replace('₽', '').replace(' ', '').strip()
                        # Если в строке остались только цифры — приводим к типу int, иначе оставляем строкой
                        price = int(price_text) if price_text.isdigit() else price_text
                    else:
                        price = "Нет в наличии"
                except Exception:
                    price = "Ошибка цены"
                # Изолированный блок try-except для артикула
                try:
                    # В верстке DNS код товара ВСЕГДА зашит в атрибут 'data-product' самой карточки.
                    # get_attribute() считывает его моментально, без наведения мышки и ожидания.
                        # Если вдруг на этой категории используется другой атрибут, проверяем альтернативу
                    data_code = product.get_attribute('data-code')
                    if not data_code:
                        data_code = "Не найден"
                except Exception:
                    data_code = "Ошибка артикула"

                # РЕГУЛЯРНЫЕ ВЫРАЖЕНИЯ (Regex)
                # Ищем объем памяти: цифры, после которых идет "ГБ" (например: 8 ГБ, 16ГБ)
                size_match = re.search(r'(\d+)\s*ГБ', spec_ram.split('DDR')[1])
                # group(1) забирает только то, что попало в круглые скобки — то есть саму цифру объема
                size = f"{size_match.group(1)}" if size_match else "Не указан"

                # Ищем количество: (в штуках)
                amount_match = re.search(r'(\d+)\s*шт', spec_ram)
                # group(1) забирает только то, что попало в круглые скобки — то есть саму цифру объема
                amount = f"{amount_match.group(1)}" if amount_match else "Не указан"

                # Ищем тип поколения памяти: DDR3, DDR4, DDR5 или DDR3L
                type_match = re.search(r'(DDR\d[L]?)', spec_ram)
                ram_type = type_match.group(1) if type_match else "Не указан"

                # Ищем тип памяти: SODIMM, DIMM
                type_main_match = re.search(r'SODIMM', spec_ram, re.IGNORECASE)                 
                if type_main_match:
                    ram_type_main = f'{type_main_match.group()}'
                #заплатка на DIMM память - на сайте нет в характеристиках
                elif re.search(r'_DIMM_', output_file, re.IGNORECASE):
                    ram_type_main = 'DIMM'
                else:
                    "Не указан"

                # Ищем частоту памяти в МГц (например: 1600 МГц, 3200 МГц)
                freq_match = re.search(r'(\d+)\s*МГц', spec_ram)
                frequency = f"{freq_match.group(1)}" if freq_match else "Не указана"

                # Ищем тайминги. Шаблон ищет структуру типа "11-11-11-28" или "22-22-22"
                # Предварительно удаляем пробелы из описания, чтобы дефисы стояли вплотную к цифрам
                timings_match = re.search(r'(\d+(?:\([A-Z]+\))?-\d+-\d+(?:-\d+)?)', spec_ram.replace(' ', ''))
                timings = timings_match.group(1) if timings_match else "Не указаны"

                # Ищем маркировку модели в заголовке (например: [SP008GLSTU160N02])
                model_match = re.search(r'\[([^\]]+)\]', full_name)
                model = f"{model_match.group(1)}" if model_match else "Не указана"

                # Ищем название бренда в заголовке (например: DEXP)
                brand_match = re.search(r'^([^\s]+)', full_name)
                brand = f"{brand_match.group(1)}" if brand_match else "Не указан"

                # Добавляем собранный структурированный словарь в наш итоговый список ram_rows
                data.append({
                    "Полное название": full_name,
                    'Артикул': data_code,
                    'Тип': ram_type_main,
                    "Поколение": ram_type,
                    "Объем, ГБ": size,
                    'В комплекте, шт.': amount,
                    "Частота, МГц": frequency,
                    "Тайминги": timings,
                    'Модель': model,
                    'Бренд' : brand,
                    "Цена (руб.)": price,
                    'Полный title': spec_ram
                })

            except Exception:
                # Если упал парсинг конкретной карточки, ключевое слово `continue` 
                # заставляет скрипт проигнорировать её и перейти к следующему товару
                continue 

        # Закрываем браузер и освобождаем занятую им оперативную память компьютера
        context.close()

        # Мы не закрываем сам браузер (browser.close()), чтобы окно оставалось открытым для вас.
        # Мы просто закрываем соединение скрипта с ним.

    # ШАГ 4: Сохранение результатов в Excel через pandas и openpyxl
    if data:
        df = pd.DataFrame(data)
        df.to_excel(output_file, index=False)
        
        wb = load_workbook(output_file)
        ws = wb.active
        for col_idx, col in enumerate(ws.columns, 1):
            max_len = max(len(str(cell.value or '')) for cell in col)
            col_letter = get_column_letter(col_idx)
            ws.column_dimensions[col_letter].width = max(max_len + 3, 12)
        wb.save(output_file)
        print(f"✅ Данные успешно сохранены в файл: {output_file}")
    else:
        print("❌ Не удалось собрать данные.")

#запускаем

def main():
    url_that_we_need = 'https://www.dns-shop.ru/catalog/17a9b91b16404e77/operativnaa-pamat-so-dimm/'
    output_file = "dns_auto_parsed_SODIMM_RAM.xlsx"
    parser_dns_auto_cdp(url_that_we_need,output_file)

    url_that_we_need = 'https://www.dns-shop.ru/catalog/17a89a3916404e77/operativnaa-pamat-dimm/'
    output_file = "dns_auto_parsed_DIMM_RAM.xlsx"
    parser_dns_auto_cdp(url_that_we_need,output_file)
if __name__ == "__main__":
    main()