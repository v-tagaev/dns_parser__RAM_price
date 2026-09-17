-- 1. Создаем отдельную чистую базу данных для парсера цен (если её нет)
SELECT 'CREATE DATABASE dns_prices_db'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'dns_prices_db')
\gexec

-- 2. Переключаемся в созданную базу данных
\c dns_prices_db;

--таблица моделей оперативы
create table if not exists ram_items (
    ram_id serial primary key,
    ram_data_code varchar(50) unique,       --артикул    
    ram_brand varchar(100),                 --бренд
    ram_model varchar(100),                 --модель ram производителя
    ram_type_of_ram varchar(20) not null,   --sodimm/dimm
    ram_generation varchar(20),             --ddr3/ddr4...
    ram_size_gb int,
    ram_amount_in_set int not null,
    ram_speed_mhz int,
    ram_timings varchar(50),
    ram_full_title text,                    --полные характеристики для будущего
    ram_created_at timestamp default current_timestamp
);
--таблица цен 
create table if not exists ram_prices (
    ram_id_price serial primary key,
    ram_data_code varchar(50) references ram_items(ram_data_code) on delete cascade,
    ram_parsed_at timestamp default current_timestamp,
    ram_price_rub numeric(10,2) not null   --цена в рублях с сайта
);
-- таблица списка валют
create table if not exists currency (
    currency_id serial primary key,
    currency_numcode varchar(10) unique,    --код валюты ЦБ
    currency_charcode varchar(10) unique,   --код валюты буквенный
    currency_name varchar(100) not null     --название валюты
);

-- таблица курсов валют
create table if not exists exchange_rate (
    rate_id serial primary key,
    currency_id int references currency(currency_id) on delete cascade, --ID валюты в нашей базе   
    rate_nominal int not null,          --номинал валюты 
    rate numeric(10,4) not null,        --курс
    rate_date timestamp not null        --дата публикации курса
);
-----------------------------------------------------------------------------------------------
-- индексы для быстрой аналитики
create index if not exists idx_ram_items_analitic   on ram_items(ram_data_code,ram_size_gb, ram_type_of_ram, ram_generation, ram_speed_mhz);
create index if not exists idx_ram_prices_analitic  on ram_prices(ram_data_code, ram_parsed_at DESC);
create index if not exists idx_currency_analitic    on currency(currency_id, currency_charcode);
create index if not exists idx_rate_analitic        on exchange_rate(currency_id, rate_date);

-----------------------------------------------------------------------------------------------
--комментарии к таблицам postgres
    comment on column ram_items.ram_data_code       is 'артикул';
    comment on column ram_items.ram_model           is 'модель ram производителя';
    comment on column ram_items.ram_brand           is 'бренд';       
    comment on column ram_items.ram_type_of_ram     is 'sodimm/dimm';
    comment on column ram_items.ram_generation      is 'ddr3/ddr4';
    comment on column ram_items.ram_timings         is 'тайминги RAM';
    comment on column ram_items.ram_full_title      is 'полные характеристики для будущей диагностики';
--комментарии к таблица цен     
    comment on column ram_prices.ram_data_code      is 'артикул';
    comment on column ram_prices.ram_price_rub      is 'цена в рублях с сайта';
-- комментарии к таблица списка валют
    comment on column currency.currency_numcode     is 'код валюты ЦБ';
    comment on column currency.currency_name        is 'название валюты';
    comment on column currency.currency_charcode    is 'код валюты буквенный';
-- комментарии к таблица курсов валют
    comment on column exchange_rate.currency_id         is 'ID валюты';
    comment on column exchange_rate.rate                is 'курс';
    comment on column exchange_rate.rate_date           is 'дата публикации курса';

-----------------------------------------------------------------------------------------------
-- Представление для аналитики: цена в рублях и долларах 
create or replace view ram_prices_usd as
select 
    p.ram_data_code,
    p.ram_brand,
    p.ram_model,
    p.ram_type_of_ram,
    p.ram_generation,
    p.ram_size_gb,
    p.ram_amount_in_set,
    p.ram_speed_mhz,
    c.ram_price_rub,
    c.ram_price_rub /(
        select e.rate/e.rate_nominal --курс доллара на дату парсинга цены 
        from exchange_rate e
        join currency cur on e.currency_id = cur.currency_id
        where cur.currency_charcode = 'USD' and  e.rate_date::date <= c.ram_parsed_at::date
        order by e.rate_date DESC
        limit 1) as rate_usd
from ram_items p
left join ram_prices c
    on p.ram_data_code = c.ram_data_code
