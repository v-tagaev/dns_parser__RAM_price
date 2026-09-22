import os
import pandas as pd
from typing import Tuple, Optional

from sqlalchemy import create_engine
#логгирование
import logging
from setup_logger import setup_logger
logger = setup_logger(__name__)



# --подключаемся к БД
def get_engine(): 
    logger.info("Подключаемся к БД PostgreSQL")  
    # Имена переменных окружения приведены в точное соответствие с вашим .env
    db_user = os.getenv('DB_USER', 'your_username')
    db_password = os.getenv('DB_PASSWORD', 'your_password')
    db_host = os.getenv('DB_HOST', 'localhost')
    db_port = os.getenv('DB_PORT', '5432')
    db_name = os.getenv('DB_NAME', 'your_database')

    connection_string = f'postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}'
    return create_engine(connection_string)

def save_df_to_postgres(df: pd.DataFrame):
    logger.info("Сохраняем DataFrame в БД PostgreSQL")
    """
    Принимаем DataFrame, в каждой строке есть характеристики и цена.
    Раскладываем данные по двум таблицам без ошибок дублирования.
    """
    engine = get_engine()
        
    # -------------------------------------------------------------------------
    # 1) Фильтруем и загружаем ТОЛЬКО НОВЫЕ модели в ram_items    
    # Вытаскиваем из базы данных артикулы, которые там УЖЕ ЕСТЬ
    try:
        existing_codes_df = pd.read_sql("SELECT ram_data_code FROM ram_items", engine)
        existing_codes = set(existing_codes_df['ram_data_code'].tolist())
    except Exception:
        # Если таблица в базе еще абсолютно пустая, считаем список существующего пустым
        existing_codes = set()

    # Выделяем из парсинга только характеристики и убираем дубликаты артикулов внутри текущего запуска
    df_items = df[[
        'ram_data_code', 'ram_model', 'ram_brand', 
        'ram_type_of_ram', 'ram_generation', 'ram_size_gb', 
        'ram_amount_in_set', 'ram_speed_mhz', 'ram_timings', 'ram_full_title'
    ]].drop_duplicates(subset=['ram_data_code'])
    
    # Оставляем только те строки, которых нет в множестве existing_codes
    # Символ ~ означает "НЕ", то есть "НЕ входит в список существующих"
    df_new_items = df_items[~df_items['ram_data_code'].isin(existing_codes)]
    
    
    # -------------------------------------------------------------------------
    # 2) Берем из общего DataFrame ТОЛЬКО колонки для цен и дописываем все
    
    # Подготавливаем данные для цен
    df_prices = df[['ram_data_code', 'ram_price_rub', 'ram_parsed_at']]

    # Используем контекстный менеджер соединения для единой транзакции в таблицы моделей ram_items и цен ram_prices
    with engine.begin() as connection:
        # Загружаем только чистые новые модели оперативы
        if not df_new_items.empty:
            df_new_items.to_sql('ram_items', connection, if_exists='append', index=False)
            logger.info(f'Успешно добавлено новых моделей в каталог (ram_items): {len(df_new_items)}')
        else:
            logger.info('Новых моделей оперативной памяти для каталога не найдено.')

        
        # Загружаем цены для всех позиций
        
        df_prices.to_sql('ram_prices', connection, if_exists='append', index=False)
        logger.info(f'Успешно сохранено временных срезов цен (ram_prices): {len(df_prices)} строк.')
