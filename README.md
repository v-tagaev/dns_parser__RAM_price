проверка БД в докере
docker exec -it de_postgres psql -U postgres -d dns_prices

----
при изменении в init.sql

перезапуск докера
docker compose down && docker compose up -d postgres
---

docker logs de_airflow
проверка парсера вручную


python parsers/dns_ram_parser.py
docker exec -it de_postgres psql -U postgres -d dns_prices -c "SELECT count(*) FROM ram_prices;"