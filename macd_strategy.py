"""
东方财富掘金量化（gm.api）策略骨架。

此文件仅提供项目结构示例，不包含任何交易逻辑。
"""

from gm.api import get_constituents, subscribe

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
    context.window = 35

    # 股票池订阅：统一 frequency 与 window，后续再按该结构补充指标与交易逻辑。
    subscribe(
        symbols=context.universe,
        frequency=context.frequency,
        count=context.window,
    )


def on_bar(context, bars):
    """仅打印结构信息，先搭框架再追加交易逻辑。"""
    # 为什么先搭结构再加交易：先确认股票池与行情流畅，再逐步加入指标与下单。
    now = getattr(context, "now", None)
    first_symbol = bars[0].symbol if bars else "N/A"
    print(
        f"{now} | universe={len(context.universe)} | bars={len(bars)} | "
        f"first_symbol={first_symbol}"
    )


def main():
    """策略入口函数占位。"""
    pass


if __name__ == "__main__":
    main()
