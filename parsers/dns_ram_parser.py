import os
import random
import time
import re
import pandas as pd
from datetime import datetime, timezone
from openpyxl import load_workbook
from openpyxl.utils import get_column_letter
from playwright.sync_api import sync_playwright, Browser, Page, BrowserContext

from save_parsers_to_db import save_df_to_postgres   #общее подключение к БД postgres
from browser_setup_airflow_and_windows import setup_browser


def parser_dns_auto_cdp(url_that_we_need: str):
    with sync_playwright() as playwright:
        # подключаемся и получаем страницы, подключение и статус
        page, browser, status_browser_opened = setup_browser(playwright, url_that_we_need)

        print(f"URL: {page.url}")
        print(f"Title: {page.title()}")
        # Выведем первые 100 символов текста страницы, чтобы понять, что загрузилось
        print(page.inner_text('body')[:100])
        
        try: 
            ram_rows = [] #данные на выход (будет лист со словарями)      
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
                    # Изолированный блок try-except для цены
                    try:
                        price_elem = product.query_selector('.product-buy__price')
                        if price_elem:
                            try:
                                # забираем текст через .inner_text()
                                price_text = price_elem.inner_text()      
                                # очищаем строку от мусора и пробелов
                                price_clean = price_text.replace('₽', '').replace(' ', '').replace(',', '.').strip()
                                price = float(price_clean)                            
                                #print(price)                    
                            except ValueError:
                                price = None
                                print('Ошибка цены бля')
                        else:
                            price = None # Если элемента цены нет на карточке 
                    except Exception as e:
                        print(f"Ошибка цены: {e}")
                        price = None
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
                    size = int(size_match.group(1)) if size_match else None

                    # Ищем количество: (в штуках)
                    amount_match = re.search(r'(\d+)\s*шт', spec_ram)
                    # group(1) забирает только то, что попало в круглые скобки — то есть саму цифру объема
                    amount = int(amount_match.group(1)) if amount_match else 1

                    # Ищем тип поколения памяти: DDR3, DDR4, DDR5 или DDR3L
                    type_match = re.search(r'(DDR\d[L]?)', spec_ram)
                    ram_type = type_match.group(1) if type_match else "Не указан"

                    # Ищем тип памяти: SODIMM, DIMM
                    type_main_match = re.search(r'SODIMM', spec_ram, re.IGNORECASE)                 
                    if type_main_match:
                        ram_type_main = f'{type_main_match.group()}'
                    else:
                        ram_type_main = 'DIMM'

                    # Ищем частоту памяти в МГц (например: 1600 МГц, 3200 МГц)
                    freq_match = re.search(r'(\d+)\s*МГц', spec_ram)
                    frequency = int(freq_match.group(1)) if freq_match else None

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
                    ram_rows.append({
                        'full_name': full_name,         #-- "Полное название"
                        'data_code': data_code,         #-- "Артикул"
                        'type_of_ram': ram_type_main,   #-- "Тип"
                        'generation': ram_type,         #-- "Поколение"
                        'size_gb': size,                #-- "Объем, ГБ"
                        'amount_in_set': amount,        #-- "В комплекте, шт."
                        'speed_mhz': frequency,         #-- "Частота, МГц"
                        'timings': timings,             #-- "Тайминги"
                        'model': model,                 #-- "Модель"
                        'brand': brand,                 #-- "Бренд"
                        'price_rub': price,             #-- "Цена (руб.)"
                        'full_title': spec_ram          #-- "Полный title"
                    })

                except Exception:
                    # Если упал парсинг конкретной карточки, ключевое слово `continue` 
                    # заставляет скрипт проигнорировать её и перейти к следующему товару
                    continue 

            return ram_rows

        except Exception as e:
            print(f"Ошибка {type(e).__name__}: {e}")
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
    df['parsed_at'] = datetime.now(timezone.utc)   #--добавляем колонку created_at

    """
    Проверяем работаем в Docker или Windows
    сохраняем либо в БД, либо в Excel (windows)
    """
    is_docker = "AIRFLOW_HOME" in os.environ

    if is_docker:
        print("🚀 Парсер запущен в Docker/Airflow. Сохраняем в БД")
        save_df_to_postgres(df)    #--сохраняем таблицу df в БД в таблицы ram_items и ram_prices

    else:
        print("💻 Парсер запущен на Windows. Сохраняем в Excel")
        #--название для excel файла
        output_file = 'dns_auto_parsed_RAM.xlsx' 

        if not df.empty:
                # Убираем временную зону для Excel
                df_excel = df.copy()
                df_excel['parsed_at'] = df_excel['parsed_at'].dt.tz_localize(None)  

                df_excel.to_excel(output_file, index=False)
                
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
    
if __name__ == "__main__":
    main()