import sys
import time
import random
from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator
import pendulum

sys.path.append('/opt/airflow/parsers')

from dns_ram_parser import main as parse_ram
from cbr_currency_parser import main as parse_currency

# Функция для создания случайной задержки перед парсингом
def wait_random_time():
    # Задержка от 0 до 120 секунд (до 2 минут)
    delay = random.randint(0, 120)
    print(f"Ожидание {delay} секунд перед началом парсинга...")
    time.sleep(delay)

default_args = {
    'owner': 'de_user_airflow',
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}

with DAG(
    dag_id='ram_price_pipeline_airflow',
    default_args=default_args,
    description='Ежедневный парсинг цен на RAM и курса валют',
    schedule_interval="30 14 * * *",      #Запуск ежедневно в 14:30 (по Москве),
    start_date=datetime(2026, 1, 1,tzinfo=pendulum.UTC),
    catchup=False,
    tags=['portfolio', 'etl'],
) as dag:
    
    delay_task = PythonOperator(
            task_id='random_delay',
            python_callable=wait_random_time,
        )
    
    task_currency = PythonOperator(
        task_id='parse_currency',
        python_callable=parse_currency,
    )    
    
    task_ram = PythonOperator(
        task_id='parse_ram',
        python_callable=parse_ram,
    )

    delay_task >>  task_currency >> task_ram  # сначала случайная задержка, потомкурс, потом цены