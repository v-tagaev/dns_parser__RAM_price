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

Этот парсер позволяет собирать актуальные данные о стоимости плашек оперативной памяти (DDR4/DDR5) с сайта DNS. Инструмент полезен для отслеживания динамики цен и поиска наиболее выгодных предложений.

**Зачем это нужно?**
- Мониторинг скидок.
- Сбор данных для анализа рынка.
- Автоматическое уведомление об изменении цены (в планах).

---

## Основные функции

- **Парсинг категорий:** автоматический сбор данных по заданным фильтрам.
- **Экспорт данных:** сохранение результатов в форматы `.csv` или `.json`.
- **Детальная информация:** сбор названия, цены, характеристик и ссылок на товар.
- **Скорость:** использование асинхронности (или многопоточности) для ускорения процесса.

---

## Технологии

Проект построен с использованием следующего стека:

<p align="left">
  <a href="https://skillicons.dev">
    <img src="https://skillicons.dev/icons?i=py,selenium,github,vscode" />
  </a>
</p>

*Примечание: Если используешь другие библиотеки (BeautifulSoup, Playwright), замени иконки выше.*

---

## Установка

1. **Клонируйте репозиторий:**
   ```bash
   git clone https://github.com/v-tagaev/dns_parser__RAM_price.git
   cd dns_parser__RAM_price