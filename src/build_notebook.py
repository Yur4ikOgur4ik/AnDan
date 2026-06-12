from __future__ import annotations

from pathlib import Path
from textwrap import dedent

import nbformat as nbf


PROJECT_ROOT = Path(__file__).resolve().parents[1]
NOTEBOOK_PATH = PROJECT_ROOT / "notebooks" / "analysis_cbr_currency_rates.ipynb"


def md(text: str) -> nbf.NotebookNode:
    return nbf.v4.new_markdown_cell(dedent(text).strip())


def code(text: str) -> nbf.NotebookNode:
    return nbf.v4.new_code_cell(dedent(text).strip())


def build_notebook() -> nbf.NotebookNode:
    notebook = nbf.v4.new_notebook()
    notebook.metadata["kernelspec"] = {
        "display_name": "Python (Moneto4ka CBR)",
        "language": "python",
        "name": "moneto4ka-cbr",
    }
    notebook.metadata["language_info"] = {
        "name": "python",
        "pygments_lexer": "ipython3",
    }

    notebook.cells = [
        md(
            """
            # Анализ динамики курсов валют по данным ЦБ РФ

            **Итоговый проект по дисциплине "Анализ данных на Python"**

            Проект посвящен анализу поведения восьми валют относительно рубля за период с 1 января 2014 года по 12 июня 2026 года. Основной источник данных — официальный XML API Банка России. Для обогащения годовых выводов используются макропоказатели России из World Bank Open Data.

            Главная идея: не просто построить график курса доллара, а сравнить валюты между собой, оценить волатильность, проверить статистические гипотезы и построить простые модели, которые помогают интерпретировать структуру валютного рынка.
            """
        ),
        md(
            """
            ## Исследовательские вопросы

            1. Как изменилась стоимость основных валют к рублю с 2014 по 2026 год?
            2. Какие валюты были наиболее волатильными и в какие годы происходили основные всплески?
            3. Насколько синхронно движутся валюты относительно рубля?
            4. Отличается ли волатильность USD/RUB в шоковый период 2022-2023 годов от более спокойного периода 2017-2019 годов?
            5. Можно ли объяснить текущий курс USD/RUB через другие валютные курсы и временной тренд?
            6. Можно ли выделить группы валют с похожим поведением?

            ## Проверяемые гипотезы

            **H1.** Дневные изменения USD/RUB и EUR/RUB положительно связаны, потому что обе валюты отражают общий спрос на иностранную валюту относительно рубля.

            **H2.** Абсолютные дневные изменения USD/RUB в 2022-2023 годах статистически выше, чем в 2017-2019 годах.

            **H3.** Курс USD/RUB можно частично объяснить через курсы других валют и временной индекс, но такая модель является объяснительной, а не торговым прогнозом.
            """
        ),
        md(
            """
            ## 1. Импорт библиотек и настройки

            Используются библиотеки из лекций: `pandas`, `numpy`, `matplotlib`, `seaborn`, `scipy`, `sklearn`, `statsmodels`.
            """
        ),
        code(
            """
            from pathlib import Path
            import sys
            import warnings

            import matplotlib.pyplot as plt
            import numpy as np
            import pandas as pd
            import seaborn as sns
            from IPython.display import display
            from scipy import stats
            from sklearn.cluster import KMeans
            from sklearn.linear_model import LinearRegression
            from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
            from sklearn.model_selection import train_test_split
            from sklearn.preprocessing import StandardScaler
            import statsmodels.api as sm
            from statsmodels.stats.outliers_influence import variance_inflation_factor

            warnings.filterwarnings("ignore")

            PROJECT_ROOT = Path.cwd()
            if not (PROJECT_ROOT / "src").exists():
                PROJECT_ROOT = PROJECT_ROOT.parent

            DATA_RAW = PROJECT_ROOT / "data" / "raw"
            DATA_PROCESSED = PROJECT_ROOT / "data" / "processed"
            FIGURES = PROJECT_ROOT / "reports" / "figures"
            FIGURES.mkdir(parents=True, exist_ok=True)

            sys.path.append(str(PROJECT_ROOT / "src"))

            sns.set_theme(style="whitegrid", palette="Set2")
            plt.rcParams["figure.figsize"] = (12, 6)
            plt.rcParams["axes.titlesize"] = 14
            plt.rcParams["axes.labelsize"] = 11
            plt.rcParams["legend.fontsize"] = 10
            pd.set_option("display.max_columns", 80)
            pd.set_option("display.float_format", "{:,.3f}".format)
            """
        ),
        md(
            """
            ## 2. Сбор данных

            Данные не скачивались вручную CSV-файлом. Сбор автоматизирован в `src/collect_data.py`.

            Используются три запроса:

            - справочник валют ЦБ РФ: `https://www.cbr.ru/scripts/XML_valFull.asp`;
            - исторические курсы по каждой валюте: XML-сервис ЦБ РФ; пример запроса для USD/RUB — `https://www.cbr.ru/scripts/XML_dynamic.asp?date_req1=01%2F01%2F2014&date_req2=12%2F06%2F2026&VAL_NM_RQ=R01235`;
            - макроиндикаторы Всемирного банка; пример запроса по инфляции РФ — `https://api.worldbank.org/v2/country/RUS/indicator/FP.CPI.TOTL.ZG?format=json&per_page=200`.

            Для повторной загрузки данных можно переключить `RUN_DATA_COLLECTION = True`.
            """
        ),
        code(
            """
            from collect_data import main as collect_data

            RUN_DATA_COLLECTION = False

            required_files = [
                DATA_RAW / "cbr_currency_rates_raw.csv",
                DATA_RAW / "cbr_currency_dictionary.csv",
                DATA_RAW / "world_bank_macro_raw.csv",
                DATA_PROCESSED / "cbr_currency_rates_processed.csv",
                DATA_PROCESSED / "annual_currency_summary.csv",
                DATA_PROCESSED / "world_bank_macro_processed.csv",
            ]

            if RUN_DATA_COLLECTION or not all(path.exists() for path in required_files):
                collect_data()
            else:
                print("Локальные данные уже собраны. Для обновления включите RUN_DATA_COLLECTION = True.")
            """
        ),
        md(
            """
            ## 3. Загрузка подготовленных таблиц

            Основная таблица — дневные курсы валют. Дополнительно используются справочник валют, годовая агрегация и макропоказатели.
            """
        ),
        code(
            """
            rates_raw = pd.read_csv(DATA_RAW / "cbr_currency_rates_raw.csv", parse_dates=["date"])
            rates = pd.read_csv(DATA_PROCESSED / "cbr_currency_rates_processed.csv", parse_dates=["date"])
            annual = pd.read_csv(DATA_PROCESSED / "annual_currency_summary.csv")
            macro = pd.read_csv(DATA_PROCESSED / "world_bank_macro_processed.csv")

            overview = pd.DataFrame(
                {
                    "table": ["rates_raw", "rates", "annual", "macro"],
                    "rows": [len(rates_raw), len(rates), len(annual), len(macro)],
                    "columns": [rates_raw.shape[1], rates.shape[1], annual.shape[1], macro.shape[1]],
                }
            )

            print(f"Период наблюдений: {rates['date'].min().date()} - {rates['date'].max().date()}")
            print(f"Количество валют: {rates['char_code'].nunique()}")
            display(overview)

            currency_list = (
                rates[["char_code", "currency_name", "nominal"]]
                .drop_duplicates()
                .sort_values("char_code")
            )
            display(currency_list)
            """
        ),
        md(
            """
            ## 4. Качество данных и предобработка

            В исходных XML-данных значения приходят в виде строк с запятой в качестве десятичного разделителя. В скрипте они приведены к числовому типу, даты преобразованы в `datetime`, а значения для валют с номиналом 10 или 100 пересчитаны в курс за одну единицу валюты.

            Дополнительно созданы признаки:

            - дневное процентное изменение;
            - логарифмическая доходность;
            - 30-дневная скользящая средняя;
            - 30-дневная годовая волатильность;
            - индекс курса от стартового значения 2014 года;
            - год, месяц, квартал и период;
            - флаг экстремального дневного изменения по Z-score.
            """
        ),
        code(
            """
            missing_report = (
                rates.isna()
                .sum()
                .to_frame("missing_count")
                .assign(missing_pct=lambda x: x["missing_count"] / len(rates) * 100)
                .sort_values("missing_pct", ascending=False)
            )

            quality_checks = pd.DataFrame(
                {
                    "metric": [
                        "Дубликаты по date + char_code",
                        "Неположительные курсы",
                        "Минимальная дата",
                        "Максимальная дата",
                    ],
                    "value": [
                        rates.duplicated(["date", "char_code"]).sum(),
                        int((rates["rate_rub"] <= 0).sum()),
                        rates["date"].min().date(),
                        rates["date"].max().date(),
                    ],
                }
            )

            display(quality_checks)
            display(missing_report.head(10))
            display(rates.dtypes.to_frame("dtype").T)
            """
        ),
        md(
            """
            Пропуски в расчетных признаках ожидаемы: для первой даты каждой валюты невозможно посчитать изменение к предыдущему дню, а для скользящих показателей нужны первые наблюдения окна. Такие пропуски не заполняются искусственно, потому что они отражают математическую природу признака.
            """
        ),
        code(
            """
            extreme_by_currency = (
                rates.groupby(["char_code", "currency_name"])
                .agg(
                    observations=("rate_rub", "size"),
                    extreme_days=("extreme_return", "sum"),
                    share_extreme_pct=("extreme_return", lambda x: x.mean() * 100),
                    max_abs_daily_return_pct=("daily_return_pct", lambda x: x.abs().max()),
                )
                .reset_index()
                .sort_values("extreme_days", ascending=False)
            )

            display(extreme_by_currency)

            top_extreme_days = (
                rates.loc[rates["extreme_return"]]
                .assign(abs_return_pct=lambda x: x["daily_return_pct"].abs())
                .sort_values("abs_return_pct", ascending=False)
                [["date", "char_code", "currency_name", "rate_rub", "daily_return_pct", "period"]]
                .head(12)
            )
            display(top_extreme_days)
            """
        ),
        md(
            """
            Экстремальные изменения не удаляются: для валютных рядов они являются реальными рыночными событиями, а не техническими ошибками. Поэтому они помечены отдельным флагом и используются в интерпретации.
            """
        ),
        md(
            """
            ## 5. Общая динамика валют

            Чтобы сравнивать валюты с разными номиналами и масштабами, построим индекс: значение каждой валюты на первой доступной дате 2014 года равно 100.
            """
        ),
        code(
            """
            fig, ax = plt.subplots(figsize=(13, 7))
            sns.lineplot(
                data=rates,
                x="date",
                y="rate_index_2014",
                hue="char_code",
                linewidth=1.6,
                ax=ax,
            )
            ax.axhline(100, color="gray", linestyle="--", linewidth=1)
            ax.set_title("Индекс курса к рублю: 2014 = 100")
            ax.set_xlabel("Дата")
            ax.set_ylabel("Индекс курса")
            ax.legend(title="Валюта", ncol=4)
            fig.tight_layout()
            fig.savefig(FIGURES / "fig01_currency_index.png", dpi=200, bbox_inches="tight")
            plt.show()

            latest_index = (
                rates.loc[rates.groupby("char_code")["date"].idxmax()]
                [["char_code", "currency_name", "date", "rate_rub", "rate_index_2014"]]
                .sort_values("rate_index_2014", ascending=False)
            )
            display(latest_index)
            """
        ),
        md(
            """
            На графике видно, что валюты разделились на несколько траекторий. CHF, USD, CNY, EUR и GBP укрепились к рублю относительно начала 2014 года. TRY и KZT, наоборот, сильно снизились относительно рубля, потому что их собственная девальвация была сильнее рублевой.
            """
        ),
        md(
            """
            ## 6. Годовая динамика и волатильность

            Сравним годы по доходности, диапазону движения и годовой волатильности.
            """
        ),
        code(
            """
            annual_top_volatility = (
                annual.sort_values("annualized_volatility_pct", ascending=False)
                [[
                    "char_code",
                    "year",
                    "annualized_volatility_pct",
                    "annual_return_pct",
                    "rate_range_pct",
                    "extreme_return_days",
                ]]
                .head(12)
            )
            display(annual_top_volatility)

            annual_volatility_pivot = annual.pivot_table(
                index="year",
                columns="char_code",
                values="annualized_volatility_pct",
                aggfunc="mean",
            )

            fig, ax = plt.subplots(figsize=(13, 7))
            sns.heatmap(
                annual_volatility_pivot,
                cmap="YlOrRd",
                linewidths=0.4,
                linecolor="white",
                cbar_kws={"label": "Годовая волатильность, %"},
                ax=ax,
            )
            ax.set_title("Годовая волатильность валютных курсов")
            ax.set_xlabel("Валюта")
            ax.set_ylabel("Год")
            fig.tight_layout()
            fig.savefig(FIGURES / "fig02_annual_volatility_heatmap.png", dpi=200, bbox_inches="tight")
            plt.show()
            """
        ),
        code(
            """
            fig, ax = plt.subplots(figsize=(13, 6))
            sns.boxplot(
                data=rates.dropna(subset=["daily_return_pct"]),
                x="char_code",
                y="daily_return_pct",
                order=sorted(rates["char_code"].unique()),
                showfliers=False,
                ax=ax,
            )
            ax.axhline(0, color="gray", linewidth=1)
            ax.set_title("Распределение дневных процентных изменений")
            ax.set_xlabel("Валюта")
            ax.set_ylabel("Дневное изменение, %")
            fig.tight_layout()
            fig.savefig(FIGURES / "fig03_daily_return_boxplot.png", dpi=200, bbox_inches="tight")
            plt.show()
            """
        ),
        md(
            """
            Период 2022 года выделяется почти по всем валютам: в этот год наблюдаются самые высокие значения годовой волатильности. Это подтверждает, что экстремальные значения не являются случайным шумом отдельной валюты, а отражают общий рыночный шок.
            """
        ),
        md(
            """
            ## 7. Корреляции дневных изменений

            Для корреляционного анализа используем логарифмические доходности, а не сами уровни курсов. Уровни временных рядов часто имеют общий тренд, который может завышать корреляцию.
            """
        ),
        code(
            """
            returns_wide = rates.pivot(index="date", columns="char_code", values="log_return").dropna()
            corr_spearman = returns_wide.corr(method="spearman")

            fig, ax = plt.subplots(figsize=(10, 8))
            sns.heatmap(
                corr_spearman,
                annot=True,
                fmt=".2f",
                cmap="coolwarm",
                center=0,
                linewidths=0.5,
                cbar_kws={"label": "Коэффициент Спирмена"},
                ax=ax,
            )
            ax.set_title("Корреляция дневных лог-изменений валют")
            ax.set_xlabel("Валюта")
            ax.set_ylabel("Валюта")
            fig.tight_layout()
            fig.savefig(FIGURES / "fig04_return_correlation_heatmap.png", dpi=200, bbox_inches="tight")
            plt.show()
            """
        ),
        code(
            """
            pairs = [("USD", "EUR"), ("USD", "CNY"), ("USD", "TRY"), ("EUR", "GBP")]
            corr_tests = []

            for left, right in pairs:
                x = returns_wide[left]
                y = returns_wide[right]
                pearson_r, pearson_p = stats.pearsonr(x, y)
                spearman_r, spearman_p = stats.spearmanr(x, y)
                corr_tests.append(
                    {
                        "pair": f"{left}-{right}",
                        "pearson_r": pearson_r,
                        "pearson_p_value": pearson_p,
                        "spearman_r": spearman_r,
                        "spearman_p_value": spearman_p,
                    }
                )

            corr_tests = pd.DataFrame(corr_tests)
            display(corr_tests)

            usd_eur = corr_tests.query("pair == 'USD-EUR'").iloc[0]
            print(
                "Вывод по H1: связь USD/RUB и EUR/RUB положительная и статистически значимая; "
                f"Spearman r = {usd_eur['spearman_r']:.3f}, p-value = {usd_eur['spearman_p_value']:.3g}."
            )
            """
        ),
        md(
            """
            Гипотеза H1 подтверждается: дневные движения USD/RUB и EUR/RUB сильно и статистически значимо связаны. Это логично, потому что обе валюты измеряют движение рубля относительно крупных внешних валют.
            """
        ),
        md(
            """
            ## 8. Проверка гипотезы о росте волатильности USD/RUB

            Сравним абсолютные дневные изменения USD/RUB в двух периодах:

            - 2017-2019: относительно спокойный период;
            - 2022-2023: период резкого рыночного шока и адаптации.

            Перед выбором теста проверим нормальность распределений тестом Шапиро-Уилка на подвыборке.
            """
        ),
        code(
            """
            usd_returns = rates.query("char_code == 'USD'").dropna(subset=["daily_return_pct"]).copy()
            usd_returns["abs_daily_return_pct"] = usd_returns["daily_return_pct"].abs()

            calm = usd_returns.query("2017 <= year <= 2019")["abs_daily_return_pct"]
            shock = usd_returns.query("2022 <= year <= 2023")["abs_daily_return_pct"]

            calm_sample = calm.sample(min(500, len(calm)), random_state=42)
            shock_sample = shock.sample(min(500, len(shock)), random_state=42)

            shapiro_calm = stats.shapiro(calm_sample)
            shapiro_shock = stats.shapiro(shock_sample)
            mannwhitney = stats.mannwhitneyu(shock, calm, alternative="greater")

            volatility_test = pd.DataFrame(
                {
                    "period": ["2017-2019", "2022-2023"],
                    "n": [len(calm), len(shock)],
                    "mean_abs_daily_return_pct": [calm.mean(), shock.mean()],
                    "median_abs_daily_return_pct": [calm.median(), shock.median()],
                    "shapiro_p_value": [shapiro_calm.pvalue, shapiro_shock.pvalue],
                }
            )
            display(volatility_test)
            print(
                "Mann-Whitney U: "
                f"statistic = {mannwhitney.statistic:.0f}, p-value = {mannwhitney.pvalue:.3g}"
            )

            fig, ax = plt.subplots(figsize=(10, 6))
            sns.histplot(calm, bins=40, stat="density", alpha=0.55, label="2017-2019", ax=ax)
            sns.histplot(shock, bins=40, stat="density", alpha=0.55, label="2022-2023", ax=ax)
            ax.set_title("Абсолютные дневные изменения USD/RUB")
            ax.set_xlabel("Абсолютное дневное изменение, %")
            ax.set_ylabel("Плотность")
            ax.legend(title="Период")
            fig.tight_layout()
            fig.savefig(FIGURES / "fig05_usd_volatility_periods.png", dpi=200, bbox_inches="tight")
            plt.show()
            """
        ),
        md(
            """
            Оба распределения не похожи на нормальные, поэтому вместо t-теста используется непараметрический критерий Манна-Уитни. Гипотеза H2 подтверждается: в 2022-2023 годах абсолютные дневные изменения USD/RUB статистически выше, чем в 2017-2019 годах.
            """
        ),
        md(
            """
            ## 9. Макрообогащение годовой сводки

            Из World Bank API добавлены годовая инфляция, рост ВВП и официальный среднегодовой курс. Эти данные не являются дневными факторами, но помогают связать валютную динамику с макроэкономическим контекстом.
            """
        ),
        code(
            """
            usd_annual = annual.query("char_code == 'USD'").copy()
            usd_annual = usd_annual.dropna(
                subset=["inflation_consumer_prices_pct", "gdp_growth_pct"]
            )

            macro_view = usd_annual[
                [
                    "year",
                    "mean_rate_rub",
                    "annual_return_pct",
                    "annualized_volatility_pct",
                    "inflation_consumer_prices_pct",
                    "gdp_growth_pct",
                    "official_exchange_rate_lcu_per_usd",
                ]
            ].sort_values("year")
            display(macro_view)

            macro_corr = macro_view[
                [
                    "mean_rate_rub",
                    "annual_return_pct",
                    "annualized_volatility_pct",
                    "inflation_consumer_prices_pct",
                    "gdp_growth_pct",
                    "official_exchange_rate_lcu_per_usd",
                ]
            ].corr(method="spearman")
            display(macro_corr)

            fig, ax = plt.subplots(figsize=(10, 6))
            sns.regplot(
                data=macro_view,
                x="inflation_consumer_prices_pct",
                y="mean_rate_rub",
                scatter_kws={"s": 70},
                ax=ax,
            )
            for _, row in macro_view.iterrows():
                ax.text(row["inflation_consumer_prices_pct"], row["mean_rate_rub"], int(row["year"]), fontsize=9)
            ax.set_title("Средний USD/RUB и инфляция РФ по годам")
            ax.set_xlabel("Инфляция, % год к году")
            ax.set_ylabel("Средний курс USD/RUB")
            fig.tight_layout()
            fig.savefig(FIGURES / "fig06_macro_usd_inflation.png", dpi=200, bbox_inches="tight")
            plt.show()
            """
        ),
        md(
            """
            Макроданные дают осторожную интерпретацию: на малом числе годовых наблюдений нельзя доказывать причинность, но можно увидеть контекст. Годы с высокой инфляцией и высокой валютной волатильностью совпадают с периодами крупных внешних шоков.
            """
        ),
        md(
            """
            ## 10. Регрессионная модель для USD/RUB

            Построим объяснительную линейную модель. Целевая переменная — курс USD/RUB, признаки — курсы других валют и временной индекс. Разбиение делается хронологически: последние 20% наблюдений остаются тестовой выборкой.

            Важно: это не торговая прогнозная модель, потому что признаки берутся за тот же день. Ее задача — показать, насколько USD/RUB объясняется общей структурой валютных курсов.
            """
        ),
        code(
            """
            wide_rates = rates.pivot(index="date", columns="char_code", values="rate_rub").dropna()
            wide_rates["time_index"] = np.arange(len(wide_rates))

            target = wide_rates["USD"]
            features = wide_rates[["EUR", "CNY", "GBP", "CHF", "JPY", "KZT", "TRY", "time_index"]]

            X_train, X_test, y_train, y_test = train_test_split(
                features,
                target,
                test_size=0.2,
                shuffle=False,
            )

            scaler = StandardScaler()
            X_train_scaled = scaler.fit_transform(X_train)
            X_test_scaled = scaler.transform(X_test)

            regression = LinearRegression()
            regression.fit(X_train_scaled, y_train)
            y_pred = regression.predict(X_test_scaled)

            regression_metrics = pd.DataFrame(
                {
                    "metric": ["MAE", "RMSE", "R2"],
                    "value": [
                        mean_absolute_error(y_test, y_pred),
                        np.sqrt(mean_squared_error(y_test, y_pred)),
                        r2_score(y_test, y_pred),
                    ],
                }
            )
            display(regression_metrics)

            coefficients = (
                pd.DataFrame(
                    {
                        "feature": features.columns,
                        "scaled_coefficient": regression.coef_,
                    }
                )
                .assign(abs_coef=lambda x: x["scaled_coefficient"].abs())
                .sort_values("abs_coef", ascending=False)
                .drop(columns="abs_coef")
            )
            display(coefficients)

            prediction_frame = pd.DataFrame(
                {
                    "date": y_test.index,
                    "actual_usd_rub": y_test.values,
                    "predicted_usd_rub": y_pred,
                }
            )

            fig, ax = plt.subplots(figsize=(13, 6))
            ax.plot(prediction_frame["date"], prediction_frame["actual_usd_rub"], label="Факт", linewidth=2)
            ax.plot(prediction_frame["date"], prediction_frame["predicted_usd_rub"], label="Модель", linewidth=2)
            ax.set_title("USD/RUB: фактические и модельные значения на тестовой выборке")
            ax.set_xlabel("Дата")
            ax.set_ylabel("Курс USD/RUB")
            ax.legend()
            fig.tight_layout()
            fig.savefig(FIGURES / "fig07_regression_actual_predicted.png", dpi=200, bbox_inches="tight")
            plt.show()
            """
        ),
        code(
            """
            vif_table = pd.DataFrame(
                {
                    "feature": features.columns,
                    "VIF": [
                        variance_inflation_factor(features.values, i)
                        for i in range(features.shape[1])
                    ],
                }
            ).sort_values("VIF", ascending=False)
            display(vif_table)

            X_train_for_ols = sm.add_constant(X_train)
            ols_model = sm.OLS(y_train, X_train_for_ols).fit()
            ols_table = pd.DataFrame(
                {
                    "coef": ols_model.params,
                    "p_value": ols_model.pvalues,
                    "ci_low": ols_model.conf_int()[0],
                    "ci_high": ols_model.conf_int()[1],
                }
            )
            display(ols_table)
            """
        ),
        md(
            """
            Модель показывает умеренное качество на отложенном периоде. При этом VIF у ряда признаков высокий: валютные курсы движутся вместе, поэтому признаки мультиколлинеарны. Это важно для интерпретации коэффициентов: модель полезна как объяснительная демонстрация общей валютной структуры, но коэффициенты нельзя читать как независимое влияние каждой валюты.
            """
        ),
        md(
            """
            ## 11. Кластеризация валют по поведению

            Для кластеризации создадим таблицу признаков по каждой валюте:

            - итоговое изменение курса с 2014 года;
            - средняя абсолютная дневная доходность;
            - годовая волатильность;
            - доля экстремальных дней;
            - корреляция дневных изменений с USD/RUB.
            """
        ),
        code(
            """
            currency_features = (
                rates.groupby(["char_code", "currency_name"])
                .agg(
                    start_rate=("rate_rub", "first"),
                    end_rate=("rate_rub", "last"),
                    mean_abs_daily_return_pct=("daily_return_pct", lambda x: x.abs().mean()),
                    annualized_volatility_pct=("log_return", lambda x: x.dropna().std() * np.sqrt(252) * 100),
                    extreme_share_pct=("extreme_return", lambda x: x.mean() * 100),
                )
                .reset_index()
            )
            currency_features["total_return_pct"] = (
                currency_features["end_rate"] / currency_features["start_rate"] - 1
            ) * 100

            usd_correlations = returns_wide.corr(method="spearman")["USD"].rename("spearman_corr_with_usd")
            currency_features = currency_features.merge(
                usd_correlations.reset_index().rename(columns={"index": "char_code"}),
                on="char_code",
                how="left",
            )

            cluster_columns = [
                "total_return_pct",
                "mean_abs_daily_return_pct",
                "annualized_volatility_pct",
                "extreme_share_pct",
                "spearman_corr_with_usd",
            ]

            X_cluster = currency_features[cluster_columns].fillna(0)
            cluster_scaler = StandardScaler()
            X_cluster_scaled = cluster_scaler.fit_transform(X_cluster)

            inertias = []
            k_values = range(1, 6)
            for k in k_values:
                km = KMeans(n_clusters=k, random_state=42, n_init=10)
                km.fit(X_cluster_scaled)
                inertias.append(km.inertia_)

            fig, ax = plt.subplots(figsize=(8, 5))
            ax.plot(list(k_values), inertias, marker="o")
            ax.set_title("Метод локтя для выбора числа кластеров")
            ax.set_xlabel("Количество кластеров")
            ax.set_ylabel("Inertia")
            fig.tight_layout()
            fig.savefig(FIGURES / "fig08_kmeans_elbow.png", dpi=200, bbox_inches="tight")
            plt.show()

            kmeans = KMeans(n_clusters=3, random_state=42, n_init=10)
            currency_features["cluster"] = kmeans.fit_predict(X_cluster_scaled)

            display(
                currency_features.sort_values(["cluster", "total_return_pct"])[
                    ["char_code", "currency_name", "cluster"] + cluster_columns
                ]
            )

            fig, ax = plt.subplots(figsize=(10, 6))
            sns.scatterplot(
                data=currency_features,
                x="total_return_pct",
                y="annualized_volatility_pct",
                hue="cluster",
                style="char_code",
                s=140,
                palette="Set2",
                ax=ax,
            )
            for _, row in currency_features.iterrows():
                ax.text(row["total_return_pct"] + 1, row["annualized_volatility_pct"], row["char_code"])
            ax.set_title("Кластеры валют по доходности и волатильности")
            ax.set_xlabel("Итоговое изменение курса с 2014 года, %")
            ax.set_ylabel("Годовая волатильность, %")
            ax.legend(title="Кластер")
            fig.tight_layout()
            fig.savefig(FIGURES / "fig09_currency_clusters.png", dpi=200, bbox_inches="tight")
            plt.show()
            """
        ),
        md(
            """
            Кластеризация показывает, что валюты с похожей реакцией на рублевые шоки группируются вместе, а TRY и KZT выделяются из-за сильной собственной девальвации. Это хороший пример того, почему анализировать только USD/RUB недостаточно: разные валюты отражают не только состояние рубля, но и собственные страновые факторы.
            """
        ),
        md(
            """
            ## 12. Итоговые выводы

            1. За период 2014-2026 годов большинство выбранных валют укрепились к рублю. Наиболее заметный рост индекса показали CHF и USD; TRY и KZT, наоборот, снизились относительно рубля из-за собственной девальвации.

            2. Самый волатильный общий период — 2022 год. Это видно по годовой волатильности, экстремальным дневным изменениям и распределению дневных доходностей.

            3. Дневные изменения USD/RUB и EUR/RUB положительно и статистически значимо связаны. Это подтверждает гипотезу о сильной общей рублевой компоненте в движении крупных валют.

            4. Абсолютные дневные изменения USD/RUB в 2022-2023 годах статистически выше, чем в 2017-2019 годах. Для проверки использован непараметрический тест Манна-Уитни, потому что распределения не являются нормальными.

            5. Линейная модель частично объясняет USD/RUB через другие валютные курсы и временной индекс, но высокая мультиколлинеарность ограничивает интерпретацию отдельных коэффициентов.

            6. Кластеризация валют показывает разные типы поведения: крупные резервные валюты, валюты с сильной собственной девальвацией и промежуточные случаи.

            Практическая ценность анализа состоит в том, что он помогает не только описать изменение курса, но и оценить риск: какие валюты движутся синхронно, где были всплески волатильности и почему валютная корзина дает больше информации, чем один курс USD/RUB.
            """
        ),
    ]

    return notebook


def main() -> None:
    NOTEBOOK_PATH.parent.mkdir(parents=True, exist_ok=True)
    notebook = build_notebook()
    nbf.write(notebook, NOTEBOOK_PATH)
    print(f"Notebook written to {NOTEBOOK_PATH}")


if __name__ == "__main__":
    main()
