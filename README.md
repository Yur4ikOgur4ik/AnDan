# Анализ динамики курсов валют по данным ЦБ РФ

Итоговый проект по дисциплине **"Анализ данных на Python"**.

Проект исследует динамику восьми валют относительно рубля за период с **01.01.2014 по 12.06.2026**. Основной источник данных - официальный XML API Банка России. Для годового контекста данные обогащены макропоказателями России из World Bank Open Data.

## Участники

- Кононов М. С.
- Потапов Д. А.
- Чирцов Ю. С.

## Источники данных

- Банк России, справочник валют: <https://www.cbr.ru/scripts/XML_valFull.asp>
- Банк России, XML-сервисы: <https://www.cbr.ru/development/SXML/>
- Банк России, пример запроса истории USD/RUB: <https://www.cbr.ru/scripts/XML_dynamic.asp?date_req1=01%2F01%2F2014&date_req2=12%2F06%2F2026&VAL_NM_RQ=R01235>
- World Bank API, инфляция РФ: <https://api.worldbank.org/v2/country/RUS/indicator/FP.CPI.TOTL.ZG?format=json&per_page=200>
- World Bank API, рост ВВП РФ: <https://api.worldbank.org/v2/country/RUS/indicator/NY.GDP.MKTP.KD.ZG?format=json&per_page=200>
- World Bank API, официальный курс LCU/USD: <https://api.worldbank.org/v2/country/RUS/indicator/PA.NUS.FCRF?format=json&per_page=200>

В `src/collect_data.py` технические адреса с названием `*_ENDPOINT` используются только как API-endpoint'ы. Их не нужно открывать без параметров: полный рабочий запрос собирается в коде из endpoint'а и параметров.

## Что сделано

- Автоматический сбор данных из API ЦБ РФ и World Bank.
- Очистка и приведение типов: даты, числовые курсы, номиналы валют.
- Создание расчетных признаков: дневная доходность, лог-доходность, 30-дневная волатильность, индекс курса от 2014 года, флаги экстремальных изменений.
- Глубокий разведочный анализ: динамика курсов, годовая волатильность, экстремальные дни, корреляции.
- Проверка гипотез статистическими тестами.
- Регрессионная модель USD/RUB и диагностика мультиколлинеарности через VIF.
- Кластеризация валют по поведению.
- Визуализации сохранены в `reports/figures`.

## Структура проекта

```text
.
├── data/
│   ├── raw/                         # исходные выгрузки из API
│   └── processed/                   # обработанные таблицы для анализа
├── notebooks/
│   └── analysis_cbr_currency_rates.ipynb
├── reports/
│   └── figures/                     # графики из ноутбука
├── src/
│   ├── collect_data.py              # сбор и подготовка данных
│   └── build_notebook.py            # генератор ноутбука
├── run_notebook.ps1                 # быстрый запуск на Windows
├── README.md
└── requirements.txt
```

## Как запустить

### Быстрый запуск на Windows

Откройте PowerShell в папке проекта и выполните:

```powershell
.\run_notebook.ps1
```

Скрипт создаст `.venv`, установит зависимости, зарегистрирует kernel `Python (Moneto4ka CBR)` и откроет Jupyter Notebook.

Если PowerShell пишет, что выполнение сценариев отключено, используйте один из вариантов:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\run_notebook.ps1
```

или запустите:

```powershell
.\run_notebook.bat
```

### Ручной запуск

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m ipykernel install --user --name moneto4ka-cbr --display-name "Python (Moneto4ka CBR)"
.\.venv\Scripts\python.exe -m notebook notebooks\analysis_cbr_currency_rates.ipynb
```

Если нужно заново собрать данные из API:

```powershell
.\.venv\Scripts\python.exe src\collect_data.py
```

В ноутбуке флаг `RUN_DATA_COLLECTION = False` оставлен для быстрого запуска с уже сохраненными данными. Если нужно обновить данные из API, поменяйте его на `True`.

## Ключевые выводы

- С 2014 по 2026 год сильнее всего к рублю выросли CHF и USD.
- TRY и KZT снизились относительно рубля из-за собственной девальвации.
- 2022 год выделяется как самый волатильный период почти по всем валютам.
- Дневные изменения USD/RUB и EUR/RUB имеют сильную положительную статистически значимую связь.
- Волатильность USD/RUB в 2022-2023 годах статистически выше, чем в 2017-2019 годах.
- Регрессионная модель частично объясняет USD/RUB через другие валюты, но высокая мультиколлинеарность ограничивает интерпретацию отдельных коэффициентов.
