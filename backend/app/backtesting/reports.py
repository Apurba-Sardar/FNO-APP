from html import escape

from .models import BacktestResult


def html_report(result: BacktestResult) -> str:
    performance = result.performance
    rows = "".join(
        "<tr>"
        f"<td>{escape(item.exit_time.isoformat())}</td><td>{escape(item.symbol)}</td>"
        f"<td>{escape(item.strategy.value)}</td><td>{escape(item.direction.value)}</td>"
        f"<td>{item.net_pnl:.2f}</td><td>{item.r_multiple:.2f}</td>"
        f"<td>{escape(item.exit_reason.value)}</td></tr>"
        for item in result.trades
    )
    warnings = "".join(f"<li>{escape(item)}</li>" for item in result.warnings)
    return f"""<!doctype html><html><head><meta charset='utf-8'><title>Backtest {result.backtest_id}</title>
<style>body{{font:14px system-ui;max-width:1100px;margin:40px auto;color:#18202b}}table{{border-collapse:collapse;width:100%}}td,th{{border:1px solid #ccd4df;padding:7px;text-align:left}}.warning{{color:#9a3412}}</style></head>
<body><h1>Historical strategy validation</h1><p>Backtest ID: {result.backtest_id}</p>
<h2>Data validation</h2><p>Candles checked: {result.data_quality.candles_checked}; valid: {result.data_quality.valid}; missing-series groups: {len(result.data_quality.missing_periods)}.</p>
<h2>Strategy validation</h2><p>Setups detected: {result.counters.setups_detected}; simulated entries: {result.counters.entries_filled}.</p>
<h2>Risk validation</h2><p>Approved setups: {result.counters.risk_approved_setups}; rejected setups: {result.counters.risk_rejected_setups}.</p>
<h2>Results</h2><p>Final equity: {performance.final_equity if performance else 'unavailable'} · Net P&amp;L: {performance.net_pnl if performance else 'unavailable'} · Maximum drawdown: {performance.maximum_drawdown if performance else 'unavailable'}</p>
<h2>Execution assumptions</h2><p>Intrabar policy: {result.configuration.intrabar_policy.value}; funding included: {result.configuration.funding_included}; slippage: {result.configuration.slippage_model.kind.value}.</p>
<h2>Warnings</h2><ul class='warning'>{warnings}</ul><h2>Trades</h2><table><thead><tr><th>Exit</th><th>Symbol</th><th>Strategy</th><th>Direction</th><th>Net P&amp;L</th><th>R</th><th>Reason</th></tr></thead><tbody>{rows}</tbody></table></body></html>"""
