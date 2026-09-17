import os
import random
import time
import re
import pandas as pd
from datetime import datetime
from openpyxl import load_workbook
from openpyxl.utils import get_column_letter
from playwright.sync_api import sync_playwright, Browser, Page, BrowserContext
from bs4 import BeautifulSoup

from save_parsers_to_db import save_df_to_postgres              #общее подключение к БД postgres
from browser_setup_airflow_and_windows import setup_browser     #подключение к браузеру и загрузка страницы
from browser_setup_airflow_and_windows import scroll_to_bottom  #скроллинг страницы

#логгирование
import logging
from setup_logger import setup_logger
logger = setup_logger(__name__)

def parser_dns_auto_cdp(url_that_we_need: str):
    with sync_playwright() as playwright:
        # подключаемся и получаем страницы, подключение и статус
        page, browser, status_browser_opened = setup_browser(
            playwright,
            url_that_we_need,
            timeout=60000
        )

        logger.info(f"URL: {page.url}")
        logger.info(f"Title: {page.title()}")
         
        #скроллим страницы, чтобы подгрузить все карточки
        scroll_to_bottom(page)
        #---------------------------------------------------------------------------------
        # САМ ПАРСИНГ
        try:
            html = page.content()
            soup = BeautifulSoup(html, 'html.parser')
            products = soup.select('.catalog-product')
            logger.info(f"Найдено элементов на странице: {len(products)}")

            ram_rows = []
            for product in products:
                try:
                    name_elem = product.select_one('.catalog-product__name')
                    if not name_elem:
                        continue

                    full_name_temp = name_elem.get_text(strip=True)
                    full_name = re.sub(r'Оперативная память\s*(?:SODIMM)?\s*', ' ', full_name_temp).strip()
                    full_title = name_elem.get('title', '') or ''

                    # Цена
                    price_elem = product.select_one('.product-buy__price')
                    price = None
                    if price_elem:
                        price_text = price_elem.get_text(strip=True)
                        price_clean = (price_text
                                    .replace('₽', '')
                                    .replace(' ', '')
                                    .replace('\xa0', '')
                                    .replace(',', '.'))
                        try:
                            price = float(price_clean)
                        except ValueError:
                            price = None
                            logger.warning(f"Ошибка цены, глянь: {price_clean}")

                    # Артикул
                    data_code = product.get('data-code', '') or 'Не найден'

                    # РЕГУЛЯРНЫЕ ВЫРАЖЕНИЯ (Regex)                

                    # Ищем объем памяти: цифры, после которых идет "ГБ" (например: 8 ГБ, 16ГБ)
                    size_match = re.search(r'(\d+)\s*ГБ', full_title.split('DDR')[1])
                    # group(1) забирает только то, что попало в круглые скобки — то есть саму цифру объема
                    size = int(size_match.group(1)) if size_match else None

                    # Ищем количество: (в штуках)
                    amount_match = re.search(r'(\d+)\s*шт', full_title)
                    # group(1) забирает только то, что попало в круглые скобки — то есть саму цифру объема
                    amount = int(amount_match.group(1)) if amount_match else 1

                    # Ищем тип поколения памяти: DDR3, DDR4, DDR5 или DDR3L
                    type_match = re.search(r'(DDR\d[L]?)', full_title)
                    ram_type = type_match.group(1) if type_match else "Не указан"

                    # Ищем тип памяти: SODIMM, DIMM
                    type_main_match = re.search(r'SODIMM', full_title, re.IGNORECASE)                 
                    if type_main_match:
                        ram_type_main = f'{type_main_match.group()}'
                    else:
                        ram_type_main = 'DIMM'

                    # Ищем частоту памяти в МГц (например: 1600 МГц, 3200 МГц)
                    freq_match = re.search(r'(\d+)\s*МГц', full_title)
                    frequency = int(freq_match.group(1)) if freq_match else None

                    # Ищем тайминги. Шаблон ищет структуру типа "11-11-11-28" или "22-22-22"
                    # Предварительно удаляем пробелы из описания, чтобы дефисы стояли вплотную к цифрам
                    timings_match = re.search(r'(\d+(?:\([A-Z]+\))?-\d+-\d+(?:-\d+)?)', full_title.replace(' ', ''))
                    timings = timings_match.group(1) if timings_match else "Не указаны"

                    # Ищем маркировку модели в заголовке (например: [SP008GLSTU160N02])
                    model_match = re.search(r'\[([^\]]+)\]', full_name)
                    model = f"{model_match.group(1)}" if model_match else "Не указана"

                    # Ищем название бренда в заголовке (например: DEXP)
                    brand_match = re.search(r'^([^\s]+)', full_name)
                    brand = f"{brand_match.group(1)}" if brand_match else "Не указан"

                    # Добавляем собранный структурированный словарь в наш итоговый список ram_rows
                    ram_rows.append({                        
                        'ram_data_code': data_code,             #-- "Артикул"
                        'ram_type_of_ram': ram_type_main,       #-- "Тип"
                        'ram_generation': ram_type,             #-- "Поколение"
                        'ram_size_gb': size,                    #-- "Объем, ГБ"
                        'ram_amount_in_set': amount,            #-- "В комплекте, шт."
                        'ram_speed_mhz': frequency,             #-- "Частота, МГц"
                        'ram_timings': timings,                 #-- "Тайминги"
                        'ram_model': model,                     #-- "Модель"
                        'ram_brand': brand,                     #-- "Бренд"
                        'ram_price_rub': price,                 #-- "Цена (руб.)"
                        'ram_full_title': full_title            #-- "Полный title"
                    })
                except Exception:
                    logger.warning(f"!! Ошибка парсинга карточки: {full_name}")
                    # Если упал парсинг конкретной карточки, ключевое слово `continue` 
                    # заставляет скрипт проигнорировать её и перейти к следующему товару
                    continue

            logger.info(f"Собрано {len(ram_rows)} строк")
            return ram_rows

        except Exception as e:
            logger.error(f"!! Ошибка {type(e).__name__}: {e}")
            return []
        finally:
            if status_browser_opened:
                browser.close()

#запускаем

def main():
    ram_rows = []
    ram_rows += parser_dns_auto_cdp('https://www.dns-shop.ru/catalog/17a9b91b16404e77/operativnaa-pamat-so-dimm/')
    ram_rows += parser_dns_auto_cdp('https://www.dns-shop.ru/catalog/17a89a3916404e77/operativnaa-pamat-dimm/')

    df = pd.DataFrame(ram_rows) #-- pd-Pandas DataFrame-двумерная таблица
    df['ram_parsed_at'] = datetime.now()   #--добавляем колонку parsed_at

    """
    Проверяем работаем в Docker или Windows
    сохраняем либо в БД, либо в Excel (windows)
    """
    is_docker = "AIRFLOW_HOME" in os.environ

    if is_docker:
        logger.info("- Парсер был запущен в Docker/Airflow. Сохраняем в БД")
        save_df_to_postgres(df)    #--сохраняем таблицу df в БД в таблицы ram_items и ram_prices

    else:
        logger.info("- Парсер был запущен на Windows. Сохраняем в Excel")
        #--название для excel файла
        output_file = f'dns_auto_parsed_RAM_{datetime.now().strftime("%d.%m.%Y_%H-%M")}.xlsx'

        if not df.empty:
                
                df.to_excel(output_file, index=False)                
                wb = load_workbook(output_file)
                ws = wb.active
                for col_idx, col in enumerate(ws.columns, 1):
                    max_len = max(len(str(cell.value or '')) for cell in col)
                    col_letter = get_column_letter(col_idx)
                    ws.column_dimensions[col_letter].width = max(max_len + 3, 12)
                wb.save(output_file)
                logger.info(f"Данные успешно сохранены в файл: {output_file}")
        else:
            logger.error("!! Не удалось собрать данные.")
    
if __name__ == "__main__":
    main()