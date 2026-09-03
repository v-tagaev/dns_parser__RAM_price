import requests
import pandas as pd
from datetime import datetime, timezone
from save_parsers_to_db import save_df_to_postgres   #общее подключение к БД postgres и парсер

def main():
    url = "https://www.cbr-xml-daily.ru/daily_json.js"
    resp = requests.get(url)
    resp.raise_for_status()
    data = resp.json()
    
    usd_rate = data['Valute']['USD']['Value']
    rate_date = data['Date'][:10]  # YYYY-MM-DD
    
    df = pd.DataFrame([{
        'currency': 'USD',
        'rate_to_rub': usd_rate,
        'rate_date': rate_date,
        'loaded_at': datetime.now(timezone.utc)
    }])
    
    save_df_to_postgres(df, 'currency_rates')

if __name__ == '__main__':
    main()