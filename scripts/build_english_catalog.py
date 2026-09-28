"""Recover original English UI copy and generate the inline localization catalog."""

from __future__ import annotations

import ast
import pprint
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE_COMMIT = "97ac53b"
FILES = ("app.py", "steppegrid/app/components.py", "steppegrid/app/planner.py", "steppegrid/app/sites.py")


def is_loc(node: ast.AST) -> bool:
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "loc"
        and len(node.args) >= 2
        and isinstance(node.args[0], ast.Constant)
        and isinstance(node.args[0].value, str)
    )


def recover(current: ast.AST, original: ast.AST, catalog: dict[str, str]) -> None:
    if is_loc(current) and isinstance(original, ast.Constant) and isinstance(original.value, str):
        catalog[current.args[0].value] = original.value
        return
    if type(current) is not type(original):
        return
    for field in current._fields:
        current_value = getattr(current, field)
        original_value = getattr(original, field)
        if isinstance(current_value, list) and isinstance(original_value, list):
            for left, right in zip(current_value, original_value, strict=False):
                if isinstance(left, ast.AST) and isinstance(right, ast.AST):
                    recover(left, right, catalog)
        elif isinstance(current_value, ast.AST) and isinstance(original_value, ast.AST):
            recover(current_value, original_value, catalog)


catalog: dict[str, str] = {}
static_keys: set[str] = set()
for relative in FILES:
    current = ast.parse((ROOT / relative).read_text(encoding="utf-8"))
    original = ast.parse(subprocess.check_output(["git", "show", f"{BASE_COMMIT}:{relative}"], cwd=ROOT).decode())
    current_functions = {node.name: node for node in current.body if isinstance(node, ast.FunctionDef)}
    original_functions = {node.name: node for node in original.body if isinstance(node, ast.FunctionDef)}
    for name in current_functions.keys() & original_functions.keys():
        recover(current_functions[name], original_functions[name], catalog)
    static_keys.update(node.args[0].value for node in ast.walk(current) if is_loc(node))

# Copy added during localization, alignment corrections, and dynamic loc(*pair) values.
catalog.update({
    "95% годовой энергии": "95% annual served-energy target",
    "99% годовой энергии": "99% annual served-energy target",
    "Цель надёжности": "Reliability target",
    "Жилой профиль": "Residential-like",
    "Равномерно внутри месяца": "Flat within month",
    "Общественные объекты": "Community facility-like",
    "Восстановленный профиль нагрузки": "Reconstructed load profile",
    "Цель: {target:.0%} годовой энергии": "Target: {target:.0%} annual served energy",
    "Для конфигурации 99% ЧДД выше на {change:.1f}%, а годовая необеспеченная энергия ниже на {energy} при заданных допущениях Родины.": "The 99% design carries {change:.1f}% more NPC while reducing annual unmet energy by {energy} under the frozen Rodina assumptions.",
    "Первая неделя": "First week",
    "Неделя максимального ограничения": "Highest-curtailment week",
    "Свой интервал": "Custom range",
    "Интервал": "Window",
    "Количество оборудования и правила диспетчеризации зафиксированы. Этот раздел не запускает оптимизацию.": "Equipment counts and dispatch rules are frozen. This page does not rerun optimization.",
    "КОНФИГУРАЦИЯ {target:.0%}": "{target:.0%} DESIGN",
    "Обеспечено {served} годового спроса. Дефицит возникает в течение {loss} ч, самый длинный непрерывный дефицит длится {longest} ч.": "Serves {served} of annual demand. Deficits occur during {loss} h, with a longest continuous deficit of {longest} h.",
    "Экономика конфигурации {target:.0%}": "{target:.0%} design economics",
    "Цель 99% увеличивает моделируемую ЧДД жизненного цикла на {change:.1f}% относительно цели 95% при зафиксированных допущениях.": "The 99% target increases modeled lifetime NPC by {change:.1f}% relative to the 95% target under the frozen assumptions.",
    "Номинальная конфигурация {target:.0%} допускает лишь около +{headroom:.2f}% дополнительного годового спроса.": "The nominal {target:.0%} design tolerates only about +{headroom:.2f}% additional annual demand.",
    "Сценарии чувствительности — детерминированные исследовательские возмущения, а не вероятностные прогнозы.": "Sensitivity cases are deterministic research perturbations, not probabilistic forecasts.",
    "{solar} показывает наибольшую солнечную выработку, а {wind} — наибольший репрезентативный ветровой ресурс в сопоставимой группе.": "{solar} has the highest solar yield, while {wind} has the strongest representative wind resource in the comparable group.",
    "Почасовая нагрузка восстановлена из опубликованных месячных значений и не является измеренным почасовым рядом.": "Hourly demand is reconstructed from published monthly values and is not a measured hourly trace.",
    "Кэш Open-Meteo ERA5 для {lat:.6f}, {lon:.6f}; при навигации сетевые запросы не выполняются.": "Cached Open-Meteo ERA5 for {lat:.6f}, {lon:.6f}; navigation makes no network requests.",
    "{count} ФЭ-блоков": "{count} PV blocks",
    "Мощность заряда/разряда: {value}": "Charge/discharge power: {value}",
    "Пользовательский интервал дат": "Custom date range",
    "Показан период: {start:%d.%m.%Y} — {end:%d.%m.%Y}": "Showing: {start:%d.%m.%Y} — {end:%d.%m.%Y}",
    "Показать почасовые данные": "Show hourly data",
    "Сохранённая конфигурация покрывает {served} моделируемого годового спроса. Самый длинный непрерывный дефицит — {hours} ч.": "The saved design serves {served} of modeled annual demand. Its longest continuous deficit is {hours} h.",
    "Выберите начальную и конечную даты.": "Choose both a start and end date.",
    "Межсельский вывод": "Cross-village finding",
    "Минимальный нормированный ЧДД при 95%": "Lowest normalized NPC at 95%",
    "Наибольший рост ЧДД 95%→99%": "Largest NPC increase 95%→99%",
    "Моё село · сохранённая система 95%": "My Village · saved 95% system",
    "Нагрузка": "Load",
    "Потоки энергии от ветра и солнца через аккумулятор к электрической нагрузке села": "Energy flows from wind and solar generation through battery storage to village electricity demand",
    "Схема энергетических потоков сельской микросети": "Village microgrid energy-flow schematic",
    "Показатель": "Measure",
    "Изменение": "Change",
    "Энергопланирование сёл Казахстана": "Village energy planning for Kazakhstan",
    "Спроектируйте устойчивую сельскую микросеть": "Plan a resilient village microgrid",
    "Изучите, как почасовой спрос и местная погода определяют ветер, солнце, накопители, надёжность и стоимость жизненного цикла.": "Explore how hourly demand and local weather shape wind, solar, storage, reliability, and lifetime cost.",
    "Нагрузка села": "Village load",
    "Почасовая генерация → диспетчеризация накопителя → нагрузка села": "Hourly renewable generation → storage dispatch → village load",
    "возобновляемой генерации": "renewable generation",
    "Почасовая диспетчеризация + накопитель": "Hourly dispatch + storage",
    "обслуженной нагрузки": "load served",
    "Годовой баланс": "Annual balance",
    "ограничено": "curtailed",
    "дефицит": "unmet",
    "Площадка: {site} · Спрос: {demand} · Каталог: {catalog} · Экономика: {economics} · рассмотрено: {wind} ветровых, {pv} ФЭМ и {battery} аккумуляторных вариантов.": "Site: {site} · Demand: {demand} · Catalog: {catalog} · Economics: {economics} · options considered: {wind} wind, {pv} PV, {battery} battery.",
    "Основа спроса: {source} · {confidence}. Модель включает {wind:,.1f} кВт ветра, {pv:,.1f} кВт ФЭМ и {battery:,.1f} кВт·ч полезной ёмкости, обеспечивая {served} смоделированной годовой энергии.": "Demand basis: {source} · {confidence}. The modeled system provides {wind:,.1f} kW wind, {pv:,.1f} kWac PV, and {battery:,.1f} kWh usable storage to serve {served} of modeled annual energy.",
    "Период диспетчеризации": "Dispatch window",
    "Годовой спрос: {value}": "Annual demand: {value}",
    "Фильтр включает {wind} моделей ветротурбин, {pv} конфигураций ФЭМ и {battery} аккумуляторных систем.": "The explicit filter includes {wind} wind models, {pv} PV configurations, and {battery} battery systems.",
    "Сценарий планирования: {name}": "{name} planning scenario",
    "Скачать результат JSON": "Download result JSON",
    "Скачать результат CSV": "Download result CSV",
    "Эталонная площадка Родина": "Rodina benchmark site",
    "временная пользовательская": "temporary custom",
    "входные данные сценария": "scenario input",
    "ID сценария: `{scenario}` · SHA-256 входных данных: `{hash}`": "Scenario ID: `{scenario}` · input SHA-256: `{hash}`",
    "Пользовательские координаты": "Custom coordinates",
    "Экспортировать JSON площадки": "Export site JSON",
    "Расположение и электроэнергия": "Location & electricity",
    "Возобновляемые ресурсы": "Renewable resources",
    "Выбранные системы": "Selected systems",
    "Сохранённые результаты показаны напрямую; недоступные цели не выводятся.": "Saved results are shown directly; unavailable targets are not inferred.",
    "Стоимость системы": "System cost",
    "Надёжность": "Reliability",
    "Ограничение": "Curtailment",
    "Нормированные показатели учитывают спрос села. Надёжность — доля обслуженной годовой энергии, а не время безотказной работы.": "Normalized metrics account for village demand. Reliability is annual energy served, not uptime.",
    "Почасовое покрытие": "Hourly coverage",
    "8 760 часов": "8,760 hours",
    "Моделируемая выработка ФЭ": "Modeled PV yield",
    "Парное сравнение": "Pairwise comparison",
    "Выберите два сохранённых результата для прямого сравнения.": "Select two saved results for a direct comparison.",
    "Для этой цели нет сохранённых межсельских результатов.": "No saved cross-village results are available for this target.",
    "Регион": "Region",
    "Годовой спрос (ГВт·ч/год)": "Annual demand (GWh/year)",
    "Результат 95%": "95% result",
    "Результат 99%": "99% result",
    "Первое село": "First village",
    "Второе село": "Second village",
    "ГВт·ч/год": "GWh/year",
    "Готово": "Ready",
    "Доступен": "Available",
    "Нет": "No",
    "Моё село": "My Village",
    "Эталон Родина {target:.0%} доступен в разделе конфигурации системы.": "The Rodina {target:.0%} benchmark is available on the System Design page.",
    "Легенда карты": "Map legend",
    "Зарегистрированное село": "Registered village",
    "Наведите для подробностей · выберите для увеличения": "Hover for details · select to zoom",
    "Результат планирования {target:.0%} недоступен.": "No {target:.0%} planning result is available.",
    "### Система {target:.0%}": "### {target:.0%} system",
    "Ветер {wind} · Солнце {solar} AC · Накопитель {storage}": "Wind {wind} · Solar {solar} AC · Storage {storage}",
    "Обслужено {served} годовой энергии · {lolh:,} ч дефицита · ЧДД {npc}": "{served} annual energy served · {lolh:,} loss-of-load hours · NPC {npc}",
    "Тип": "Type",
    "Годовой спрос": "Annual demand",
    "Население": "Population",
    "В кэше · 2025": "Cached · 2025",
    "Моделируемый КИУМ ветра": "Modeled wind CF",
    "<b>{{name}}</b><br>{{region}}<br>{{identity}}<br>Спрос: {{annual_demand}}<br>Погода: {{weather}}<br>Результат 95%: {{result_95}}<br>Результат 99%: {{result_99}}": "<b>{{name}}</b><br>{{region}}<br>{{identity}}<br>Demand: {{annual_demand}}<br>Weather: {{weather}}<br>95% result: {{result_95}}<br>99% result: {{result_99}}",
    # Dynamic planner option labels.
    "Существующий зарегистрированный набор данных": "Existing registered demand dataset",
    "Эталонный спрос Родины": "Rodina benchmark demand",
    "Оценка годового спроса": "Estimated annual demand",
    "Оценка месячного спроса": "Estimated monthly demand",
    "Загрузка почасового спроса": "Hourly demand upload",
    "Неделя с наибольшим дефицитом": "Highest-unmet week",
    "Неделя с наибольшим ограничением": "Highest-curtailment week",
    # Dynamic glossary copy.
    "Доля обеспеченного годового спроса на электроэнергию. Это не процент часов непрерывной работы.": "Share of annual electricity demand supplied. It is not the percentage of uninterrupted hours.",
    "Энергетическая вероятность потери питания: недоотпущенная годовая энергия, делённая на годовой спрос.": "Energy-based loss of power supply probability: unmet annual energy divided by annual demand.",
    "Часы потери нагрузки: часы с любым смоделированным дефицитом электроэнергии.": "Loss-of-load hours: hours containing any modeled unmet electricity demand.",
    "Чистая приведённая стоимость: дисконтированные затраты жизненного цикла при фиксированных экономических предпосылках.": "Net present cost: discounted lifetime planning cost under the frozen economic assumptions.",
    "Эквивалентная годовая стоимость: годовой эквивалент чистой приведённой стоимости.": "Equivalent annual cost: the annualized value of net present cost.",
    "Доступная возобновляемая энергия, не использованная нагрузкой и не принятая накопителем.": "Renewable energy available but neither used by load nor accepted by storage.",
    "Годовая энергия, делённая на номинальную мощность и число часов в году.": "Annual energy divided by rated power multiplied by all hours in the year.",
    "Солнечное излучение в плоскости смоделированной наклонной поверхности ФЭМ.": "Plane-of-array solar irradiation incident on the modeled tilted PV surface.",
    "Восстановленный профиль нагрузки с наименьшей долей обслуженной энергии для выбранного устойчивого проекта.": "Reconstructed load shape with the lowest served-energy fraction for the selected robust design.",
})

missing = sorted(static_keys - catalog.keys())
if missing:
    raise SystemExit(f"Missing English strings: {missing}")

target = ROOT / "steppegrid/app/english_catalog.py"
target.write_text(
    '"""Generated original-English catalog for inline Russian/Kazakh UI copy."""\n\n'
    "ENGLISH_INLINE: dict[str, str] = "
    + pprint.pformat(dict(sorted(catalog.items())), width=120, sort_dicts=True)
    + "\n",
    encoding="utf-8",
)
print(f"Wrote {len(catalog)} English strings to {target.relative_to(ROOT)}")
