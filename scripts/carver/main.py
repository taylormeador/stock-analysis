import pandas as pd
from datetime import date
import os
from sqlalchemy import create_engine, text

STOCK_ANALYSIS_DB = os.getenv('STOCK_ANALYSIS_DB')

INSTRUMENTS = {
    "MES=F": {"multiplier": 0.5,    "label": "/MES"},  # /MES is 0.5 because it is $5 per point but 1/10th of /ES
    "ZN=F": {"multiplier": 1000, "label": "/ZN"},
    "MGC=F": {"multiplier": 10,   "label": "/MGC"},
    "CL=F": {"multiplier": 100,   "label": "/MCL"},  # /MCL is not available on yfinance
}

TODAY = date.today()
LOOKBACK_DAYS = 120  # enough for EWMA to stabilize


def get_prices(conn, symbol: str) -> pd.DataFrame:
    sql = """
        SELECT date, close
        FROM futures_prices
        WHERE symbol = %s
          AND date >= CURRENT_DATE - INTERVAL '%s days'
        ORDER BY date ASC
    """
    return pd.read_sql(sql, conn, params=(symbol, LOOKBACK_DAYS), parse_dates=["date"])


def get_forecasts(conn, symbol: str, as_of: date) -> pd.Series:
    sql = """
        SELECT rule_name, scaled_value
        FROM forecasts
        WHERE symbol = %s
          AND date = %s
    """
    df = pd.read_sql(sql, conn, params=(symbol, as_of))
    return df.set_index("rule_name")["scaled_value"]


def calc_ewma_vol(prices: pd.Series) -> float:
    returns = prices.pct_change()
    variance = returns.pow(2).ewm(span=36, adjust=False).mean()
    return variance.pow(0.5).iloc[-1]


def calc_instrument_value_volatility(current_price: float, ewma_vol: float, multiplier: float) -> float:
    block_value = current_price * 0.01 * multiplier
    return block_value * ewma_vol * 100


def write_portfolio_calculations(conn, rows: list[dict]) -> None:
    sql = text("""
        INSERT INTO portfolio_calculations (
            symbol, date,
            trading_capital, volatility_target_pct,
            current_price,
            ewma_vol, block_value, instrument_value_volatility,
            annualized_cash_vol_target, daily_cash_vol_target, vol_scalar,
            combined_forecast,
            subsystem_position, instrument_weight, idm,
            portfolio_position, desired_position
        ) VALUES (
            :symbol, :date,
            :trading_capital, :volatility_target_pct,
            :current_price,
            :ewma_vol, :block_value, :ivv,
            :annualized_cash_vol_target, :daily_cash_vol_target, :vol_scalar,
            :combined_forecast,
            :subsystem_position, :instrument_weight, :idm,
            :portfolio_position, :desired_position
        )
        ON CONFLICT (symbol, date) DO UPDATE SET
            trading_capital             = EXCLUDED.trading_capital,
            volatility_target_pct       = EXCLUDED.volatility_target_pct,
            current_price               = EXCLUDED.current_price,
            ewma_vol                    = EXCLUDED.ewma_vol,
            block_value                 = EXCLUDED.block_value,
            instrument_value_volatility = EXCLUDED.instrument_value_volatility,
            annualized_cash_vol_target  = EXCLUDED.annualized_cash_vol_target,
            daily_cash_vol_target       = EXCLUDED.daily_cash_vol_target,
            vol_scalar                  = EXCLUDED.vol_scalar,
            combined_forecast           = EXCLUDED.combined_forecast,
            subsystem_position          = EXCLUDED.subsystem_position,
            instrument_weight           = EXCLUDED.instrument_weight,
            idm                         = EXCLUDED.idm,
            portfolio_position          = EXCLUDED.portfolio_position,
            desired_position            = EXCLUDED.desired_position
    """)
    conn.execute(sql, rows)
    conn.commit()

def main():
    # 1. Account value
    trading_capital = 70000  # TODO pull from table

    # 2. Volatility target
    volatility_target_pct = 0.20
    annualized_cash_vol_target = trading_capital * volatility_target_pct
    daily_cash_vol_target = annualized_cash_vol_target / 16

    engine = create_engine(STOCK_ANALYSIS_DB)
    conn = engine.connect()

    rows_to_write = []

    for symbol, config in INSTRUMENTS.items():
        print(f"\nProcessing {config['label']} ({symbol})")

        # 3. Prices
        prices_df = get_prices(conn, symbol)
        if prices_df.empty:
            print("  No price data found, skipping")
            continue
        current_price = prices_df["close"].iloc[-1]

        # 5. Price volatility
        ewma_vol = calc_ewma_vol(prices_df["close"])
        block_value = current_price * 0.01 * config["multiplier"]
        ivv = calc_instrument_value_volatility(current_price, ewma_vol, config["multiplier"])

        # 6 & 7. Forecasts — average all rules for this instrument on today's date
        forecasts = get_forecasts(conn, symbol, TODAY)
        if forecasts.empty:
            print(f"  No forecasts found for {TODAY}, skipping")
            continue
        combined_forecast = forecasts.mean()

        # 8. Volatility scalar
        vol_scalar = daily_cash_vol_target / ivv

        # 9. Subsystem position
        subsystem_position = combined_forecast * vol_scalar / 10

        # 10. Portfolio instrument position
        instrument_weight = 1 / len(INSTRUMENTS)  # equal weight for now
        idm = 1.2  # TODO derive from correlation table, use Carver's lookup for now
        portfolio_position = subsystem_position * instrument_weight * idm

        # 11. Rounded target position
        desired_position = round(portfolio_position)

        print(f"  Price:             {current_price:.2f}")
        print(f"  EWMA vol:          {ewma_vol:.4f}")
        print(f"  IVV:               {ivv:.2f}")
        print(f"  Combined forecast: {combined_forecast:.2f}")
        print(f"  Subsystem pos:     {subsystem_position:.2f}")
        print(f"  Target position:   {desired_position} contracts")

        rows_to_write.append({
            "symbol":                     symbol,
            "date":                       TODAY,
            "trading_capital":            trading_capital,
            "volatility_target_pct":      volatility_target_pct,
            "current_price":              float(current_price),
            "ewma_vol":                   float(ewma_vol),
            "block_value":                float(block_value),
            "ivv":                        float(ivv),
            "annualized_cash_vol_target": annualized_cash_vol_target,
            "daily_cash_vol_target":      daily_cash_vol_target,
            "vol_scalar":                 float(vol_scalar),
            "combined_forecast":          float(combined_forecast),
            "subsystem_position":         float(subsystem_position),
            "instrument_weight":          instrument_weight,
            "idm":                        idm,
            "portfolio_position":         float(portfolio_position),
            "desired_position":           desired_position,
        })

    if rows_to_write:
        write_portfolio_calculations(conn, rows_to_write)
        print(f"\nWrote {len(rows_to_write)} rows to portfolio_calculations")

    conn.close()
    # TODO if the portfolio doesn't hit the bvol target (because some contracts were rounded down or to 0) we might need to recalculate at the end?

    
    # 12. TODO: compare desired_position vs actual positions table, generate trade list


if __name__ == "__main__":
    main()