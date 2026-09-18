<div align="center">

  <img src="logo.png" alt="Logo" width="200" height="auto" />

  <h1>DNS RAM Price Parser</h1>

  <p>
    Автоматизированный инструмент для мониторинга цен на оперативную память в магазине DNS.
  </p>

<!-- Бейджи -->
<p align="center">
  <img src="https://img.shields.io/github/stars/v-tagaev/dns_parser__RAM_price?style=for-the-badge&color=orange" alt="stars">
  <img src="https://img.shields.io/github/issues/v-tagaev/dns_parser__RAM_price?style=for-the-badge&color=red" alt="issues">
  <img src="https://img.shields.io/github/license/v-tagaev/dns_parser__RAM_price?style=for-the-badge&color=blue" alt="license">
  <img src="https://img.shields.io/badge/Python-3.10+-yellow?style=for-the-badge&logo=python" alt="python">
</p>

<h4>
    <a href="#основные-функции">Функции</a>
    •
    <a href="#технологии">Стек</a>
    •
    <a href="#установка">Установка</a>
    •
    <a href="#использование">Запуск</a>
  </h4>
</div>

---

## О проекте

Парсер позволяет собирать актуальные данные о стоимости оперативной памяти sodimm, dimm с сайта DNS. Инструмент полезен для отслеживания динамики цен и поиска наиболее выгодных предложений.
1) запуск на Windows в cmd через python dns_ram_parser.py спарсит страницы в excel
2) реализован запуск на Docker в Airflow с ежедневным расписанием. Airflow подключается через SSH к браузеру на Windows и производит парсинг данных в базу Postgres.
   Обойти защиты сайта с самого docker пока не получилось, защиты отслеживают сигнатуры кастрированного linux, имитация бурной деятельности человека, эмуляция экрана, подброс живых куки, скрытые режимы playwright, прокси - не помогли. Нужен был живой браузер со следами пользователя.


## Технологии

Проект построен с использованием следующего стека:

<p align="left">
  <a href="https://skillicons.dev">
    <img src="https://skillicons.dev/icons?i=py,postgres,docker,github,vscode" />
    <img src="airflow/logo.png"/>
  </a>
</p>


---

## Установка

1. **Клонируйте репозиторий:**
   ```bash
   git clone https://github.com/v-tagaev/dns_parser__RAM_price.git
   cd dns_parser__RAM_price
