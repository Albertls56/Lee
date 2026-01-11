"""
东方财富掘金量化（gm.api）策略骨架。

此文件仅提供项目结构示例，不包含任何交易逻辑。
"""

from gm.api import *
import pandas as pd

# TODO: 在此处填写你的 token 与 strategy_id
GM_TOKEN = ""
STRATEGY_ID = ""


def init(context):
    """初始化策略与股票池订阅。"""
    context.index_symbol = "SHSE.000300"
    # 指数成分股获取：优先用 df=True 拿到 symbol 列，失败再降级解析原始结构。
    constituents_df = get_constituents(
        index=context.index_symbol,
        fields="symbol",
        df=True,
    )
    if constituents_df is not None and not constituents_df.empty:
        context.universe = constituents_df["symbol"].tolist()
    else:
        constituents_data = get_constituents(index=context.index_symbol)
        if isinstance(constituents_data, dict) and "constituents" in constituents_data:
            raw_list = constituents_data["constituents"]
        else:
            raw_list = constituents_data or []
        context.universe = [
            item["symbol"]
            for item in raw_list
            if isinstance(item, dict) and "symbol" in item
        ]

    context.max_positions = 10
    context.max_new_positions_per_day = 3
    context.target_weight = 1.0 / context.max_positions
    context.frequency = "1d"
    context.window = 200

    # 股票池订阅：统一 frequency 与 window，后续再按该结构补充指标与交易逻辑。
    subscribe(
        symbols=context.universe,
        frequency=context.frequency,
        count=context.window,
    )


def calc_macd(close_series, fast=12, slow=26, signal=9):
    """计算 MACD 指标，返回 DIF 与 DEA（白线/黄线）。"""
    close = pd.Series(close_series).astype(float)
    ema_fast = close.ewm(span=fast, adjust=False).mean()
    ema_slow = close.ewm(span=slow, adjust=False).mean()
    dif = ema_fast - ema_slow
    dea = dif.ewm(span=signal, adjust=False).mean()
    return dif, dea


def is_golden_cross(dif, dea):
    """判断 DIF 上穿 DEA（金叉）。"""
    if len(dif) < 2 or len(dea) < 2:
        return False
    return dif.iloc[-2] <= dea.iloc[-2] and dif.iloc[-1] > dea.iloc[-1]


def is_dead_cross(dif, dea):
    """判断 DIF 下穿 DEA（死叉）。"""
    if len(dif) < 2 or len(dea) < 2:
        return False
    return dif.iloc[-2] >= dea.iloc[-2] and dif.iloc[-1] < dea.iloc[-1]


def on_bar(context, bars):
    """扫描 MACD 信号但不下单，先验证逻辑再进入交易流程。"""
    # 先扫描信号不下单：先验逻辑验证指标与数据质量，确认信号稳定再做交易决策。
    # DIF/DEA 代表快慢 EMA 之差及其平滑线，0 轴代表多空分界，DIF>0 表示偏多。
    now = getattr(context, "now", None)
    entry_candidates = []
    exit_candidates = []
    computed_count = 0

    for symbol in context.universe:
        data = context.data(
            symbol,
            frequency=context.frequency,
            count=context.window,
            fields="close",
        )
        if data is None or len(data) < context.window:
            continue
        close_series = data["close"] if isinstance(data, pd.DataFrame) else data
        dif, dea = calc_macd(close_series)
        computed_count += 1
        if dif.iloc[-1] > 0 and is_golden_cross(dif, dea):
            entry_candidates.append((symbol, dif.iloc[-1]))
        if is_dead_cross(dif, dea):
            exit_candidates.append(symbol)

    entry_candidates.sort(key=lambda item: item[1], reverse=True)
    top_entry_symbols = [symbol for symbol, _ in entry_candidates[:10]]
    top_exit_symbols = exit_candidates[:10]

    print(f"{now} | universe={len(context.universe)} | macd={computed_count}")
    print(f"符合进场={len(entry_candidates)} | top10={top_entry_symbols}")
    print(f"符合出场={len(exit_candidates)} | top10={top_exit_symbols}")


def main():
    """策略入口函数占位。"""
    pass


if __name__ == "__main__":
    main()
