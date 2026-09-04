package com.fno.trading.data.model

import com.google.gson.annotations.SerializedName

data class LiveStatusResponse(
    @SerializedName("runtime_state") val runtimeState: String? = "unknown",
    @SerializedName("circuit_breaker") val circuitBreaker: String? = "closed",
    @SerializedName("last_api_error") val lastApiError: String? = null,
    @SerializedName("stage_name") val stageName: String? = null,
    @SerializedName("auto_execution") val autoExecution: Boolean = false,
    @SerializedName("auto_close_active") val autoCloseActive: Boolean = true,
    @SerializedName("enforced_leverage") val enforcedLeverage: Int = 3,
    @SerializedName("daily_profit_target") val dailyProfitTarget: Double = 6.0
)

data class LiveAccountResponse(
    @SerializedName("equity") val equity: Double? = 0.0,
    @SerializedName("available_balance") val availableBalance: Double? = 0.0,
    @SerializedName("margin_used") val marginUsed: Double? = 0.0,
    @SerializedName("daily_pnl") val dailyPnl: Double? = 0.0,
    @SerializedName("currency") val currency: String? = "USDT"
)

data class PositionsResponse(
    @SerializedName("items") val items: List<PositionItem>? = emptyList()
)

data class PositionItem(
    @SerializedName("position_id") val positionId: String? = "",
    @SerializedName("exchange_position_id") val exchangePositionId: String? = "",
    @SerializedName("pair") val pair: String = "",
    @SerializedName("direction") val direction: String = "long",
    @SerializedName("quantity") val quantity: Double = 0.0,
    @SerializedName("average_price") val averagePrice: Double = 0.0,
    @SerializedName("mark_price") val markPrice: Double? = 0.0,
    @SerializedName("target") val target: Double? = null,
    @SerializedName("stop") val stop: Double? = null,
    @SerializedName("margin") val margin: Double? = 0.0,
    @SerializedName("leverage") val leverage: Int? = 3,
    @SerializedName("unrealized_pnl") val unrealizedPnl: Double = 0.0,
    @SerializedName("protection_status") val protectionStatus: String? = "protected",
    @SerializedName("status") val status: String? = "open",
    @SerializedName("created_at") val createdAt: String? = null
)

data class OrdersResponse(
    @SerializedName("items") val items: List<OrderItem>? = emptyList()
)

data class OrderItem(
    @SerializedName("order_id") val orderId: String = "",
    @SerializedName("pair") val pair: String = "",
    @SerializedName("side") val side: String = "buy",
    @SerializedName("price") val price: Double = 0.0,
    @SerializedName("filled_quantity") val filledQuantity: Double = 0.0,
    @SerializedName("requested_quantity") val requestedQuantity: Double = 0.0,
    @SerializedName("order_type") val orderType: String = "market_order",
    @SerializedName("status") val status: String = "filled",
    @SerializedName("created_at") val createdAt: String? = null
)

data class OpportunitiesResponse(
    @SerializedName("items") val items: List<OpportunityItem>? = emptyList()
)

data class OpportunityItem(
    @SerializedName("symbol") val symbol: String = "",
    @SerializedName("opportunity_score") val score: Double = 0.0,
    @SerializedName("dominant_direction") val direction: String = "bullish",
    @SerializedName("tier") val tier: String = "A",
    @SerializedName("estimated_structural_rr") val riskReward: Double? = 2.0,
    @SerializedName("eligible") val eligible: Boolean = true
)

data class ResearchFeedResponse(
    @SerializedName("evaluations") val evaluations: List<EvaluationItem>? = emptyList(),
    @SerializedName("evaluated_at_ist") val evaluatedAtIst: String? = null,
    @SerializedName("last_scan_at") val lastScanAt: String? = null
)

data class EvaluationItem(
    @SerializedName("symbol") val symbol: String = "",
    @SerializedName("score") val score: Double = 0.0,
    @SerializedName("current_price") val currentPrice: Double = 0.0,
    @SerializedName("strategy") val strategy: String? = "breakout",
    @SerializedName("status") val status: String? = "watching",
    @SerializedName("direction") val direction: String? = "neutral",
    @SerializedName("signal") val signal: String? = "BUY",
    @SerializedName("signal_label") val signalLabel: String? = "BUY (LONG)",
    @SerializedName("recommended_side") val recommendedSide: String? = "buy",
    @SerializedName("punch_area") val punchArea: String? = null,
    @SerializedName("punch_zone_low") val punchZoneLow: Double? = null,
    @SerializedName("punch_zone_high") val punchZoneHigh: Double? = null,
    @SerializedName("target_price") val targetPrice: Double? = null,
    @SerializedName("target_pct") val targetPct: Double? = 1.8,
    @SerializedName("stop_price") val stopPrice: Double? = null,
    @SerializedName("stop_pct") val stopPct: Double? = -1.2,
    @SerializedName("risk_reward") val riskReward: String? = "1 : 1.50",
    @SerializedName("reason") val reason: String? = null,
    @SerializedName("drivers") val drivers: List<String>? = emptyList(),
    @SerializedName("action_guidance") val actionGuidance: String? = null,
    @SerializedName("long_score") val longScore: Double? = 50.0,
    @SerializedName("short_score") val shortScore: Double? = 50.0,
    @SerializedName("evaluated_at_ist") val evaluatedAtIst: String? = null
)

data class InstantScalpRequest(
    @SerializedName("symbol") val symbol: String,
    @SerializedName("side") val side: String = "buy",
    @SerializedName("target_margin") val targetMargin: Double = 20.0
)

data class TestTradeRequest(
    @SerializedName("symbol") val symbol: String,
    @SerializedName("side") val side: String = "buy",
    @SerializedName("quantity") val quantity: Double,
    @SerializedName("leverage") val leverage: Int = 3,
    @SerializedName("confirmation_phrase") val confirmationPhrase: String = "EXECUTE REAL TRADE"
)

data class ExitPositionRequest(
    @SerializedName("position_id") val positionId: String,
    @SerializedName("confirmation_phrase") val confirmationPhrase: String = "EXIT REAL POSITION"
)

data class SimpleActionResponse(
    @SerializedName("status") val status: String? = "success",
    @SerializedName("detail") val detail: String? = null
)
