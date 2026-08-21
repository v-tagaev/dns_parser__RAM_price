--таблица моделей оперативы
create table if not exist ram_items (
    id serial primary key,
    data_code varchar(50) unique,       --артикул
    model varchar(30),                  --модель ram производителя
    brand varchar(100),                  --бренд
    full_name text not null,            
    type_of_ram varchar(20) not null,   --sodimm/dimm
    generation varchar(20) not null,    --ddr3/ddr4...
    size_gb smallint not null,
    amount_in_set smallint not null,
    speed_mhz smallint,
    timings varchar(50),
    full_title text,                    --полные характеристики для будущего
    created_at timestamp default current_timestamp
);
--таблица цен 
create table if not exist ram_prices (
    id_price serial primary key,
    ram_product_id int references ram_items(id) on delete cascade,
    parsed_at timestamp default current_timestamp,
    price_rub numeric(10,2) not null   --цена в рублях с сайта
);
-- таблица курсов валют
create or replace table if not exist rate_money (
    id_rate serial primary key,
    currency varchar(20) not null,     --название валюты
    rate numeric(10,2) not null,   --курс
    rate_date timestamp default current_timestamp
);

-- индексы для быстрой аналитики
create index if not exists idx_ram_items_analitic on ram_items(size_gb, generation, speed_mhz);
create index if not exists idx_ram_prices_analitic on ram_prices(ram_product_id);
create index if not exists idx_rate_money_analitic on rate_money(currency, rate_date DESC);

-- Представление для аналитики: цена в рублях и долларах 
create or replace view ram_prices_usd as
select 
    p.id,
    p.brand,
    p.category,
    p.type_of_ram,
    p.generation,
    p.size_gb,
    p.amount_in_set,
    p.speed_mhz,
    c.price_rub,
    c.price_rub /(
        select d.rate 
        from rate_money d 
        where d.currency = 'USD' and  d.rate_date::date <= c.parsed_at::date
        order by d.rate_date DESC
        limit 1) as price_usd
from ram_items p
left join ram_prices c 
    on p.id = c.ram_product_id