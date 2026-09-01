import os
import pandas as pd
from sqlalchemy import create_engine
from dotenv import load_dotenv #--подключение к .env

load_dotenv(dotenv_path='../.env')

# --подключаемся к БД
def get_engine(): 
       
    # Имена переменных окружения приведены в точное соответствие с вашим .env
    db_user = os.getenv('POSTGRES_USER', 'your_username')
    db_password = os.getenv('POSTGRES_PASSWORD', 'your_password')
    db_host = os.getenv('DB_HOST', 'localhost')
    db_port = os.getenv('DB_PORT', '5432')
    db_name = os.getenv('POSTGRES_DB', 'your_database')

    connection_string = f'postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}'
    return create_engine(connection_string)

def save_df_to_postgres(df: pd.DataFrame):
    """
    Принимаем DataFrame, в каждой строке есть характеристики и цена.
    Раскладываем данные по двум таблицам без ошибок дублирования.
    """
    engine = get_engine()
    
    # Принудительно делаем артикул строкой, чтобы избежать конфликтов типов в Pandas
    df['data_code'] = df['data_code'].astype(str)
    
    # -------------------------------------------------------------------------
    # Шаг 1. Фильтруем и загружаем ТОЛЬКО НОВЫЕ модели в ram_items
    # -------------------------------------------------------------------------
    # 1.1. Вытаскиваем из базы данных артикулы, которые там УЖЕ ЕСТЬ
    try:
        existing_codes_df = pd.read_sql("SELECT data_code FROM ram_items", engine)
        existing_codes = set(existing_codes_df['data_code'].tolist())
    except Exception:
        # Если таблица в базе еще абсолютно пустая, считаем список существующего пустым
        existing_codes = set()

    # 1.2. Выделяем из парсинга только характеристики и убираем дубликаты артикулов внутри текущего запуска
    df_items = df[[
        'data_code', 'model', 'brand', 'full_name', 
        'type_of_ram', 'generation', 'size_gb', 
        'amount_in_set', 'speed_mhz', 'timings', 'full_title'
    ]].drop_duplicates(subset=['data_code'])
    
    # 1.3. ТРЮК: Оставляем только те строки, которых нет в множестве existing_codes
    # Символ ~ означает "НЕ", то есть "НЕ входит в список существующих"
    df_new_items = df_items[~df_items['data_code'].isin(existing_codes)]
    
    # 1.4. Загружаем только чистые новые модели
    if not df_new_items.empty:
        df_new_items.to_sql('ram_items', engine, if_exists='append', index=False)
        print(f'Успешно добавлено новых моделей в каталог (ram_items): {len(df_new_items)}')
    else:
        print('Новых моделей оперативной памяти для каталога не найдено.')

    # -------------------------------------------------------------------------
    # Шаг 2. Берем из общего DataFrame ТОЛЬКО колонки для цен и дописываем все
    # -------------------------------------------------------------------------
    df_prices = df[['data_code', 'price_rub', 'parsed_at']]
    
    # Цены просто дописываем в конец — тут дубликатов быть не может, 
    # так как дата и время (parsed_at) всегда новые!
    df_prices.to_sql('ram_prices', engine, if_exists='append', index=False)
    
    print(f'Успешно сохранено временных срезов цен (ram_prices): {len(df_prices)} строк.')
