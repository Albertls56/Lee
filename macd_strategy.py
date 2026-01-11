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


def get_long_positions(context):
    """获取当前多头持仓的 symbol 集合，兼容不同账户对象结构。"""
    account = None
    if hasattr(context, "account"):
        try:
            account = context.account()
        except Exception:
            account = None
    if account is None and hasattr(context, "accounts"):
        try:
            accounts = context.accounts()
            if accounts:
                account = accounts[0]
        except Exception:
            account = None
    if account is None:
        print("未能获取账户对象，返回空持仓集合。")
        return set()

    positions_data = None
    for attr_name in ("positions", "position"):
        if hasattr(account, attr_name):
            attr = getattr(account, attr_name)
            try:
                positions_data = attr()
            except Exception:
                positions_data = attr
            if positions_data is not None:
                break
    if positions_data is None and hasattr(context, "positions"):
        try:
            positions_data = context.positions()
        except Exception:
            positions_data = None
    if positions_data is None:
        print("未能获取持仓列表，返回空持仓集合。")
        return set()

    def is_long_side(side_value):
        if side_value is None:
            return True
        if side_value == PositionSide_Long:
            return True
        return str(side_value).lower() in {
            "long",
            "positionside_long",
            "position_side_long",
            "positionside.long",
        }

    def extract_symbol(position):
        if isinstance(position, dict):
            return position.get("symbol") or position.get("security") or position.get("code")
        return getattr(position, "symbol", None) or getattr(position, "security", None)

    symbols = set()
    if isinstance(positions_data, dict):
        iterable = positions_data.values()
    elif isinstance(positions_data, (list, tuple, set)):
        iterable = positions_data
    else:
        iterable = [positions_data]
    for position in iterable:
        side_value = None
        if isinstance(position, dict):
            side_value = position.get("position_side") or position.get("side")
        else:
            side_value = getattr(position, "position_side", None) or getattr(position, "side", None)
        if not is_long_side(side_value):
            continue
        symbol = extract_symbol(position)
        if symbol:
            symbols.add(symbol)
    return symbols


def on_bar(context, bars):
    """执行可交易的沪深300 MACD 组合策略。"""
    # on_bar 可能同一时刻收到多条 bars 推送，同一交易日只运行一次，避免重复下单。
    now = getattr(context, "now", None)
    if now is None and bars:
        bar = bars[0]
        now = getattr(bar, "eob", None) or getattr(bar, "datetime", None) or getattr(bar, "time", None)
    trade_date = now.date() if hasattr(now, "date") else now
    if trade_date is not None:
        if getattr(context, "last_trade_date", None) == trade_date:
            return
        context.last_trade_date = trade_date

    # 先卖后买：先释放资金与持仓名额，再用最新空位挑选新的进场标的。
    held = get_long_positions(context)
    sell_list = []

    for symbol in list(held):
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
        if is_dead_cross(dif, dea):
            order_target_percent(
                symbol,
                0.0,
                position_side=PositionSide_Long,
                order_type=OrderType_Market,
            )
            sell_list.append(symbol)

    held = held.difference(sell_list)
    current_positions = len(held)

    # 等权 + 持仓上限：每个持仓 target_weight 等权分配，最多 max_positions 只。
    entry_candidates = []
    for symbol in context.universe:
        if symbol in held:
            continue
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
        if dif.iloc[-1] > 0 and is_golden_cross(dif, dea):
            entry_candidates.append((symbol, dif.iloc[-1]))

    entry_candidates.sort(key=lambda item: item[1], reverse=True)
    capacity = max(context.max_positions - current_positions, 0)
    buy_quota = min(capacity, context.max_new_positions_per_day)
    buy_list = []
    for symbol, _ in entry_candidates[:buy_quota]:
        order_target_percent(
            symbol,
            context.target_weight,
            position_side=PositionSide_Long,
            order_type=OrderType_Market,
        )
        buy_list.append(symbol)

    final_positions = current_positions + len(buy_list)
    print(
        f"{trade_date} | 卖出={len(sell_list)} {sell_list} | "
        f"买入={len(buy_list)} {buy_list} | 持仓={final_positions}"
    )


def main():
    """策略入口函数占位。"""
    pass


if __name__ == "__main__":
    main()
