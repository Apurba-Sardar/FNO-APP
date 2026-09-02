"""One real-market, zero-real-order Phase 1-9 paper scalp orchestration test."""

import argparse
import asyncio
import json
import sys
from datetime import UTC, datetime
from uuid import uuid4

import structlog

from app.config import get_settings
from app.execution.coindcx_executor import CoinDCXTradeExecutor
from app.main import app, lifespan
from app.paper_trading.execution import PaperTradeExecutor
from app.paper_trading.models import PaperPositionStatus
from app.paper_trading.reconciliation import reconcile
from app.services.coindcx.authenticated_client import AuthenticatedCoinDCXClient


class PaperE2EFailure(RuntimeError):
    pass


def event(log, name: str, correlation_id: str, **values) -> None:
    log.info(name, correlation_id=correlation_id, paper_e2e=True, **values)
    print(f"[{correlation_id}] {name}", flush=True)


def top_diagnostics(application) -> list[dict]:
    opportunities = sorted(
        application.state.opportunity_runtime.state.opportunities.values(),
        key=lambda item: (item.current_rank or 10**9, -item.opportunity_score, item.symbol),
    )[:5]
    strategy_state = application.state.strategy_runtime.state
    risk_state = application.state.risk_runtime.state
    rows = []
    for item in opportunities:
        strategy_analysis = strategy_state.analyses.get(item.symbol)
        risk_analysis = risk_state.analyses.get(item.symbol)
        strategies = {}
        if strategy_analysis:
            for name, result in strategy_analysis.results.items():
                decision = risk_analysis.decisions.get(name) if risk_analysis else None
                strategies[name.value] = {
                    "status": result.status.value,
                    "direction": result.direction.value,
                    "setup_quality": result.setup_quality_score,
                    "failed_conditions": result.conditions_failed,
                    "warnings": result.warnings,
                    "risk_allowed": None if decision is None else decision.allowed,
                    "risk_rejections": [] if decision is None else decision.rejection_reasons,
                }
        rows.append({
            "symbol": item.symbol,
            "rank": item.current_rank,
            "score": item.opportunity_score,
            "eligible": item.eligible,
            "hard_gate_reasons": item.hard_gate_reasons,
            "warnings": item.warnings,
            "strategies": strategies,
        })
    return rows


def verify_closed_state(runtime, trade, starting_equity: float) -> dict:
    state = runtime.state
    entry_orders = [row for row in state.orders if row.order_type == "market" and row.setup_id == next(p.setup_id for p in state.positions if p.position_id == trade.position_id)]
    positions = [row for row in state.positions if row.position_id == trade.position_id]
    journal = [row for row in state.trades if row.trade_id == trade.trade_id]
    pending = [row for row in state.orders if row.setup_id == positions[0].setup_id and row.status.value in {"created", "pending", "partially_filled"}]
    checks = {
        "orders": len(entry_orders) == 1 and entry_orders[0].status.value == "filled",
        "fills": len(entry_orders) == 1 and entry_orders[0].executed_price == positions[0].entry_price,
        "position": len(positions) == 1 and positions[0].status == PaperPositionStatus.CLOSED,
        "protection": positions[0].protection_status == "protected" and not pending,
        "accounting": abs(state.account.equity - (starting_equity + trade.net_pnl)) <= 1e-6,
        "journal": len(journal) == 1 and journal[0].position_id == positions[0].position_id,
        "no_duplicates": len({row.order_id for row in state.orders}) == len(state.orders)
        and len({row.trade_id for row in state.trades}) == len(state.trades),
        "no_orphans": not reconcile(state),
    }
    if not all(checks.values()):
        raise PaperE2EFailure(f"paper reconciliation failed: {checks}")
    return checks


def report(application, scan_stats, position, trade, starting_equity, checks, restart_ok, correlation_id):
    strategy_analysis = application.state.strategy_runtime.state.analyses.get(position.symbol)
    setup = strategy_analysis.results[position.strategy] if strategy_analysis else None
    risk_analysis = application.state.risk_runtime.state.analyses.get(position.symbol)
    decision = risk_analysis.decisions.get(position.strategy) if risk_analysis else None
    account = application.state.paper_runtime.state.account
    result = {
        "correlation_id": correlation_id,
        "overall_result": "PASS" if all(checks.values()) and restart_ok else "FAIL",
        "safety": {
            "trading_mode": "paper", "real_orders": "disabled",
            "executor": "PaperTradeExecutor", "safety_gate": "PASS",
        },
        "market_scan": {
            "pairs_scanned": scan_stats.total_markets,
            "eligible_pairs": scan_stats.eligible_markets,
            "selected_symbol": position.symbol,
            "opportunity_score": position.opportunity_score,
        },
        "strategy": {
            "name": position.strategy.value, "direction": position.direction.value,
            "status": None if setup is None else setup.status.value,
            "setup_quality": position.setup_score,
            "evaluation_time": position.factor_snapshot.get("evaluation_time"),
            "timeframes": position.factor_snapshot.get("market_context", {}).get("timeframe_trends", {}),
            "entry_zone": None if setup is None or setup.entry_zone is None else setup.entry_zone.model_dump(mode="json"),
            "trigger": None if setup is None else setup.trigger_price,
            "explanation": position.factor_snapshot.get("strategy_explanation", []),
        },
        "entry": {
            "planned": position.factor_snapshot.get("planned_entry"),
            "requested": position.factor_snapshot.get("requested_entry"),
            "actual": position.entry_price, "quantity": position.quantity,
            "notional": position.notional, "fee": position.entry_fee,
            "slippage": position.factor_snapshot.get("entry_slippage"),
            "order_lifecycle": position.factor_snapshot.get("order_lifecycle"),
        },
        "risk": {
            "decision": None if decision is None else decision.status.value,
            "risk_amount": position.factor_snapshot.get("risk_amount"),
            "risk_percent": position.factor_snapshot.get("risk_percent"),
            "stop": position.stop_price, "target": position.target_price,
            "risk_reward": None if setup is None else setup.risk_reward,
            "quantity": position.quantity, "leverage": position.leverage,
            "maximum_loss": None if decision is None else decision.maximum_loss,
            "required_margin": None if decision is None else decision.required_margin,
            "risk_lock": application.state.risk_runtime.state.risk_state.trading_lock.value,
        },
        "position": {
            "entry_time": position.entry_timestamp, "exit_time": position.exit_timestamp,
            "holding_minutes": trade.duration_minutes, "exit_reason": trade.exit_reason.value,
            "protection_status": position.protection_status,
            "protection_lifecycle": position.protection_lifecycle,
        },
        "performance": {
            "gross_pnl": trade.gross_pnl, "fees": trade.fees,
            "slippage": trade.slippage, "net_pnl": trade.net_pnl,
            "r_multiple": trade.r_multiple, "starting_equity": starting_equity,
            "ending_equity": account.equity, "daily_pnl": account.daily_pnl,
            "drawdown": account.drawdown,
        },
        "reconciliation": checks | {"restart_recovery": restart_ok},
        "journal": trade.model_dump(mode="json"),
    }
    print("=" * 48)
    print("PAPER SCALP E2E TEST")
    print("=" * 48)
    print(json.dumps(result, indent=2, default=str))
    return result


async def run(args) -> int:
    settings = get_settings()
    correlation_id = f"PAPER-E2E-{datetime.now(UTC).strftime('%Y%m%dT%H%M%S')}-{uuid4().hex[:6]}"
    log = structlog.get_logger()
    private_calls: list[str] = []
    original_signed_request = AuthenticatedCoinDCXClient._signed_request

    async def forbidden_private_call(_self, _method, path, *_args, **_kwargs):
        private_calls.append(path)
        raise PaperE2EFailure(f"private CoinDCX endpoint reached in paper test: {path}")

    AuthenticatedCoinDCXClient._signed_request = forbidden_private_call
    starting_trade_ids = set()
    scan_stats = None
    captured_position = None
    captured_trade = None
    starting_equity = 0.0
    try:
        if settings.trading_mode != "paper":
            raise PaperE2EFailure("TRADING_MODE is not paper")
        event(log, "PAPER_TEST_SAFETY_CHECK_PASSED", correlation_id)
        event(log, "REAL_ORDER_EXECUTION_DISABLED", correlation_id)
        async with lifespan(app):
            paper = app.state.paper_runtime
            if not isinstance(paper.executor, PaperTradeExecutor):
                raise PaperE2EFailure("executor is not PaperTradeExecutor")
            if isinstance(paper.executor, CoinDCXTradeExecutor):
                raise PaperE2EFailure("CoinDCXTradeExecutor selected in paper mode")
            if app.state.live_runtime.executor is not None or app.state.live_runtime.client is not None:
                raise PaperE2EFailure("live executor/client was instantiated in paper mode")
            if any(item.status == PaperPositionStatus.OPEN for item in paper.state.positions):
                raise PaperE2EFailure("an existing paper position prevents an isolated one-trade test")
            starting_trade_ids = {item.trade_id for item in paper.state.trades}
            starting_equity = paper.state.account.equity
            await paper.start()
            event(log, "SCAN_STARTED", correlation_id)
            while True:
                scan_stats = await app.state.scanner_runtime.run_once()
                new_open = [
                    item for item in paper.state.positions
                    if item.status == PaperPositionStatus.OPEN
                    and not any(t.position_id == item.position_id for t in paper.state.trades)
                ]
                if new_open:
                    if len(new_open) != 1:
                        raise PaperE2EFailure("more than one paper position opened")
                    captured_position = new_open[0]
                    event(log, "OPPORTUNITY_SELECTED", correlation_id, symbol=captured_position.symbol)
                    event(log, "STRATEGY_TRIGGERED", correlation_id, strategy=captured_position.strategy.value)
                    event(log, "RISK_APPROVED", correlation_id)
                    event(log, "PAPER_ENTRY_FILLED", correlation_id, price=captured_position.entry_price)
                    event(log, "PROTECTION_CREATED", correlation_id)
                    break
                diagnostics = top_diagnostics(app)
                print("NO VALID PAPER TRADE SETUP")
                print(json.dumps({
                    "pairs_scanned": scan_stats.total_markets,
                    "eligible_pairs": scan_stats.eligible_markets,
                    "top_5": diagnostics,
                }, indent=2, default=str))
                if not args.wait_for_setup:
                    await paper.stop()
                    return 0
                event(log, "WAITING_FOR_VALID_SETUP", correlation_id, seconds=args.poll_seconds)
                await asyncio.sleep(args.poll_seconds)

            event(log, "POSITION_MONITORING", correlation_id, position_id=str(captured_position.position_id))
            next_scan = asyncio.get_running_loop().time() + args.poll_seconds
            while captured_position.status == PaperPositionStatus.OPEN:
                await asyncio.sleep(1)
                if private_calls:
                    raise PaperE2EFailure("private exchange call tripwire triggered")
                if asyncio.get_running_loop().time() >= next_scan:
                    await app.state.scanner_runtime.run_once()
                    next_scan = asyncio.get_running_loop().time() + args.poll_seconds
            new_trades = [item for item in paper.state.trades if item.trade_id not in starting_trade_ids]
            if len(new_trades) != 1:
                raise PaperE2EFailure(f"expected exactly one new journal record, found {len(new_trades)}")
            captured_trade = new_trades[0]
            event(log, f"{captured_trade.exit_reason.value.upper()}_HIT", correlation_id)
            event(log, "POSITION_CLOSED", correlation_id)
            checks = verify_closed_state(paper, captured_trade, starting_equity)
            event(log, "ACCOUNT_RECONCILED", correlation_id)
            final_equity = paper.state.account.equity
            trade_id = captured_trade.trade_id
            await paper.stop()

        async with lifespan(app):
            restored = app.state.paper_runtime.state
            restart_ok = (
                not any(item.status == PaperPositionStatus.OPEN for item in restored.positions)
                and not any(item.status.value in {"created", "pending", "partially_filled"} for item in restored.orders)
                and any(item.trade_id == trade_id for item in restored.trades)
                and abs(restored.account.equity - final_equity) <= 1e-6
            )
            if not restart_ok:
                raise PaperE2EFailure("restart recovery did not preserve the closed trade state")
            result = report(
                app, scan_stats, captured_position, captured_trade,
                starting_equity, checks, restart_ok, correlation_id,
            )
            event(log, "TEST_COMPLETE", correlation_id, result=result["overall_result"])
        if private_calls:
            raise PaperE2EFailure(f"private endpoint calls detected: {private_calls}")
        return 0
    except KeyboardInterrupt:
        raise
    except Exception as exc:  # noqa: BLE001 - report every end-to-end failure uniformly
        print(json.dumps({
            "correlation_id": correlation_id, "overall_result": "FAIL",
            "failure": str(exc), "private_endpoint_calls": private_calls,
        }, indent=2), file=sys.stderr)
        return 1
    finally:
        AuthenticatedCoinDCXClient._signed_request = original_signed_request


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--wait-for-setup", action="store_true")
    parser.add_argument("--poll-seconds", type=int, default=300)
    return parser.parse_args()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(run(parse_args())))
