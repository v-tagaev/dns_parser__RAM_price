<div align="center">
  <img src="logo.png" alt="Logo" width="200" height="auto" />
  <h1>DNS RAM Price Parser</h1>
  <p>
    Автоматизированный инструмент для мониторинга цен на оперативную память в магазине DNS.
  </p>

<!-- Бейджи -->
<p align="center">
  <img src="https://img.shields.io/badge/Python-3.10+-blue?logo=python" alt="Python">
  <img src="https://img.shields.io/badge/Airflow-2.8.1-red?logo=apache-airflow" alt="Airflow">
  <img src="https://img.shields.io/badge/PostgreSQL-15-blue?logo=postgresql" alt="PostgreSQL">
  <img src="https://img.shields.io/badge/Docker-Compose-blue?logo=docker" alt="Docker">
  <img src="https://img.shields.io/badge/Playwright-enabled-green?logo=playwright" alt="Playwright">
</p>

<p align="center">
  <a href="#-о-проекте">О проекте</a> •
  <a href="#-технологии">Технологии</a> •
  <a href="#-установка">Установка</a> •
  <a href="#-использование">Использование</a> •
  <a href="#-скриншоты">Скриншоты</a>
</p>

---

## О проекте

Парсер позволяет собирать актуальные данные о стоимости оперативной памяти sodimm, dimm с сайта DNS. Инструмент полезен для отслеживания динамики цен и поиска наиболее выгодных предложений.
   Обойти защиты сайта с самого docker пока не получилось, защиты отслеживают сигнатуры кастрированного linux, имитация бурной деятельности человека, эмуляция экрана, подброс живых куки, скрытые режимы playwright, прокси - не помогли. Нужен был живой браузер со следами пользователя.

**Два режима работы:**

| Режим | Описание | Результат |
|-------|----------|-----------|
| **Windows** | Локальный запуск `python dns_ram_parser.py` | Данные в Excel-файл |
| **Docker/Airflow** | Ежедневный парсинг по расписанию через SSH-туннель к браузеру на Windows | Данные в PostgreSQL |


**Схема работы:**

```mermaid
graph LR
    A[Airflow Scheduler] --> B[SSH-туннель]
    B --> C[Chrome на Windows]
    C --> D[DNS-shop]
    D --> C
    C --> E[BeautifulSoup]
    E --> F[PostgreSQL]
```

## 1.Технологии

Проект построен с использованием следующего стека:

<p align="left">
  <a href="https://skillicons.dev">
    <img src="https://skillicons.dev/icons?i=py,postgres,docker,github,vscode" />
    <img src="airflow/logo.png" alt="Logo" width="46" height="auto"/>
  </a>
</p>
| Категория | Инструмент | Назначение |
|-----------|------------|------------|
| Язык | Python 3.10+ | Основной язык разработки |
| Оркестрация | Apache Airflow | Планирование и запуск ETL-процессов |
| База данных | PostgreSQL 15 | Хранение исторических данных |
| Контейнеризация | Docker, Docker Compose | Развёртывание инфраструктуры |
| Парсинг | Playwright, BeautifulSoup4 | Сбор и обработка данных |
| Обработка данных | Pandas, SQLAlchemy | Трансформация и загрузка данных |
```
---
##  Скриншоты

### Airflow DAG
![Airflow DAG](docs/airflow_graph.png)
<img src="docs/airflow_graph.png" height="auto" />


### Данные в PostgreSQL
![pgAdmin](docs/pgadmin_tables.png)
<img src="pg_admin_table_ram_items.png" height="auto" />
<img src="pg_admin_table_currency.png" height="auto" />
### Результат в Excel
![Excel](docs/excel_result.png)
<img src="docs/airflow_graph.png" height="auto" />
```
---

## Установка

### 1. Клонируйте репозиторий
```bash
git clone https://github.com/v-tagaev/dns_parser__RAM_price.git
cd dns_parser__RAM_price
```

### 2. Создайте файл `.env`
Скопируйте шаблон и заполните своими значениями:
```bash
cp .env.example .env
```

### 3. Запустите контейнеры
```bash
docker compose up -d
```

### 4. Откройте Airflow
- **URL:** [http://localhost:8082](http://localhost:8082)
- **Логин:** `admin`
- **Пароль:** `admin`
```
---
##  Планы по развитию

- [ ] Добавить парсинг других комплектующих (SSD, GPU)
- [ ] Добавить алерты в Telegram при изменении цен
