package com.fno.trading.ui.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ElectricBolt
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material.icons.filled.TrendingDown
import androidx.compose.material.icons.filled.TrendingUp
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.fno.trading.data.model.EvaluationItem
import com.fno.trading.ui.TradingViewModel
import com.fno.trading.ui.theme.*

@Composable
fun OpportunitiesScreen(
    viewModel: TradingViewModel,
    modifier: Modifier = Modifier
) {
    val state by viewModel.uiState.collectAsState()

    LazyColumn(
        modifier = modifier
            .fillMaxSize()
            .background(AmoledBackground)
            .padding(horizontal = 14.dp),
        verticalArrangement = Arrangement.spacedBy(14.dp),
        contentPadding = PaddingValues(top = 14.dp, bottom = 80.dp)
    ) {
        // ── Header ────────────────────────────────────────────────────
        item {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Column {
                    Text(
                        text       = "🎯 Scalp Signals",
                        color      = TextPrimary,
                        fontSize   = 22.sp,
                        fontWeight = FontWeight.Black
                    )
                    Text(
                        text    = "Algorithmic conviction scores & entry zones",
                        color   = TextSecondary,
                        fontSize = 12.sp
                    )
                }

                Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    // Count badge
                    if (state.evaluations.isNotEmpty()) {
                        Box(
                            modifier = Modifier
                                .clip(RoundedCornerShape(8.dp))
                                .background(CyanAccent.copy(0.12f))
                                .border(1.dp, CyanAccent.copy(0.3f), RoundedCornerShape(8.dp))
                                .padding(horizontal = 10.dp, vertical = 5.dp)
                        ) {
                            Text(
                                text       = "${state.evaluations.size} signals",
                                color      = CyanAccent,
                                fontSize   = 11.sp,
                                fontWeight = FontWeight.Bold
                            )
                        }
                    }

                    // Timestamp
                    Box(
                        modifier = Modifier
                            .clip(RoundedCornerShape(8.dp))
                            .background(DarkElevatedSurface)
                            .border(1.dp, BorderColor, RoundedCornerShape(8.dp))
                            .padding(horizontal = 8.dp, vertical = 5.dp)
                    ) {
                        Text(
                            text       = state.evaluatedAtIst ?: "Live IST",
                            color      = EmeraldPrimary,
                            fontSize   = 10.sp,
                            fontWeight = FontWeight.Bold,
                            fontFamily = FontFamily.Monospace
                        )
                    }
                }
            }
        }

        // ── Strategy Summary Chips ─────────────────────────────────────
        if (state.evaluations.isNotEmpty()) {
            item {
                val buyCount  = state.evaluations.count { it.signal.equals("BUY", ignoreCase = true) }
                val sellCount = state.evaluations.size - buyCount
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    Box(
                        modifier = Modifier
                            .clip(RoundedCornerShape(10.dp))
                            .background(ProfitGreen.copy(0.12f))
                            .border(1.dp, ProfitGreen.copy(0.3f), RoundedCornerShape(10.dp))
                            .padding(horizontal = 12.dp, vertical = 6.dp)
                    ) {
                        Text("▲ $buyCount BUY", color = ProfitGreen, fontSize = 12.sp, fontWeight = FontWeight.Black)
                    }
                    Box(
                        modifier = Modifier
                            .clip(RoundedCornerShape(10.dp))
                            .background(LossRed.copy(0.12f))
                            .border(1.dp, LossRed.copy(0.3f), RoundedCornerShape(10.dp))
                            .padding(horizontal = 12.dp, vertical = 6.dp)
                    ) {
                        Text("▼ $sellCount SELL", color = LossRed, fontSize = 12.sp, fontWeight = FontWeight.Black)
                    }
                }
            }
        }

        // ── Signal Cards ──────────────────────────────────────────────
        if (state.evaluations.isEmpty()) {
            item {
                Card(
                    modifier = Modifier.fillMaxWidth(),
                    colors   = CardDefaults.cardColors(containerColor = DarkCardSurface),
                    shape    = RoundedCornerShape(18.dp)
                ) {
                    Column(
                        modifier = Modifier.fillMaxWidth().padding(36.dp),
                        horizontalAlignment = Alignment.CenterHorizontally
                    ) {
                        CircularProgressIndicator(color = EmeraldPrimary, strokeWidth = 3.dp, modifier = Modifier.size(36.dp))
                        Spacer(modifier = Modifier.height(14.dp))
                        Text("Scanning 499 CoinDCX markets...", color = TextSecondary, fontSize = 14.sp)
                        Spacer(modifier = Modifier.height(4.dp))
                        Text("Looking for high-probability 4× scalp setups", color = TextMuted, fontSize = 12.sp)
                    }
                }
            }
        } else {
            items(state.evaluations, key = { it.symbol }) { item ->
                SignalEvaluationCard(
                    item    = item,
                    onPunch = { symbol, side -> viewModel.punch3xScalp(symbol, side) }
                )
            }
        }
    }
}

// ─── Signal Card ──────────────────────────────────────────────────────────────

@Composable
fun SignalEvaluationCard(
    item: EvaluationItem,
    onPunch: (String, String) -> Unit
) {
    val isBuy = item.signal.equals("BUY", ignoreCase = true) ||
            item.direction?.lowercase() in listOf("long", "buy") ||
            item.recommendedSide?.lowercase() == "buy"

    val primaryColor = if (isBuy) EmeraldPrimary else LossRed
    val accentGrad   = if (isBuy) {
        Brush.horizontalGradient(listOf(EmeraldPrimary, CyanAccent))
    } else {
        Brush.horizontalGradient(listOf(LossRed, OrangeAlert))
    }

    val punchLow   = item.punchZoneLow   ?: if (isBuy) item.currentPrice * 0.998 else item.currentPrice * 0.996
    val punchHigh  = item.punchZoneHigh  ?: if (isBuy) item.currentPrice * 1.004 else item.currentPrice * 1.002
    val targetPrice= item.targetPrice    ?: if (isBuy) item.currentPrice * 1.018 else item.currentPrice * 0.982
    val stopPrice  = item.stopPrice      ?: if (isBuy) item.currentPrice * 0.988 else item.currentPrice * 1.012
    val punchText  = item.punchArea      ?: String.format("$%,.4g – $%,.4g", punchLow, punchHigh)

    Card(
        modifier = Modifier
            .fillMaxWidth()
            .border(1.dp, primaryColor.copy(0.28f), RoundedCornerShape(18.dp)),
        colors   = CardDefaults.cardColors(containerColor = DarkCardSurface),
        shape    = RoundedCornerShape(18.dp)
    ) {
        Column(modifier = Modifier.padding(16.dp)) {

            // Accent stripe
            Box(
                modifier = Modifier
                    .fillMaxWidth()
                    .height(3.dp)
                    .clip(RoundedCornerShape(2.dp))
                    .background(accentGrad)
            )

            Spacer(modifier = Modifier.height(12.dp))

            // Header: Symbol + Signal + Score
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Column {
                    Row(
                        verticalAlignment = Alignment.CenterVertically,
                        horizontalArrangement = Arrangement.spacedBy(7.dp)
                    ) {
                        Text(
                            text       = item.symbol.replace("B-", "").replace("_USDT", ""),
                            color      = TextPrimary,
                            fontSize   = 20.sp,
                            fontWeight = FontWeight.Black
                        )
                        if (item.isTopGainer == true) {
                            val chg = item.change24hPct ?: 0.0
                            Box(
                                modifier = Modifier
                                    .clip(RoundedCornerShape(6.dp))
                                    .background(EmeraldPrimary.copy(0.18f))
                                    .border(1.dp, EmeraldPrimary.copy(0.5f), RoundedCornerShape(6.dp))
                                    .padding(horizontal = 6.dp, vertical = 2.dp)
                            ) {
                                Text(
                                    text       = "🔥 +${String.format("%.1f", chg)}%",
                                    color      = EmeraldPrimary,
                                    fontSize   = 10.sp,
                                    fontWeight = FontWeight.Black
                                )
                            }
                        }
                    }
                    Row(
                        verticalAlignment = Alignment.CenterVertically,
                        horizontalArrangement = Arrangement.spacedBy(8.dp)
                    ) {
                        Text(
                            text       = String.format("$%,.5g", item.currentPrice),
                            color      = CyanAccent,
                            fontSize   = 14.sp,
                            fontWeight = FontWeight.Bold,
                            fontFamily = FontFamily.Monospace
                        )
                        item.volume24hUsdt?.let { vol ->
                            Text(
                                text    = "Vol: $${String.format("%.1f", vol / 1_000_000)}M",
                                color   = TextMuted,
                                fontSize = 11.sp,
                                fontFamily = FontFamily.Monospace
                            )
                        }
                    }
                }

                Row(
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.spacedBy(6.dp)
                ) {
                    // Signal badge
                    Box(
                        modifier = Modifier
                            .clip(RoundedCornerShape(9.dp))
                            .background(primaryColor.copy(0.14f))
                            .border(1.dp, primaryColor, RoundedCornerShape(9.dp))
                            .padding(horizontal = 8.dp, vertical = 5.dp)
                    ) {
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Icon(
                                imageVector = if (isBuy) Icons.Default.TrendingUp else Icons.Default.TrendingDown,
                                contentDescription = null,
                                tint   = primaryColor,
                                modifier = Modifier.size(14.dp)
                            )
                            Spacer(modifier = Modifier.width(4.dp))
                            Text(
                                text       = if (isBuy) "BUY" else "SELL",
                                color      = primaryColor,
                                fontSize   = 12.sp,
                                fontWeight = FontWeight.Black
                            )
                        }
                    }

                    // Score ring
                    ScoreBadge(score = item.score.toInt())
                }
            }

            Spacer(modifier = Modifier.height(12.dp))

            // Conviction reason box
            Box(
                modifier = Modifier
                    .fillMaxWidth()
                    .clip(RoundedCornerShape(12.dp))
                    .background(DarkElevatedSurface)
                    .border(1.dp, BorderColor.copy(0.6f), RoundedCornerShape(12.dp))
                    .padding(12.dp)
            ) {
                Column {
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Text(
                            text       = "💡 PRO TRADER CONVICTION",
                            color      = AmberWarning,
                            fontSize   = 9.sp,
                            fontWeight = FontWeight.Black,
                            letterSpacing = 0.5.sp
                        )
                        if (item.claudeScore != null) {
                            Text(
                                text       = "🧠 AI: ${item.claudeScore}/100",
                                color      = VioletAccent,
                                fontSize   = 9.sp,
                                fontWeight = FontWeight.Bold
                            )
                        }
                    }
                    Spacer(modifier = Modifier.height(5.dp))
                    Text(
                        text = item.reason ?: if (isBuy)
                            "Bullish Momentum: Price consolidating above key support ($${String.format("%,.4g", punchLow)}) with buyer bid absorption. Favorable 4× long entry on breakout."
                        else
                            "Bearish Pressure: Overhead resistance rejecting rallies near $${String.format("%,.4g", punchHigh)}. Distribution indicates 4× short scalp breakdown.",
                        color     = TextPrimary,
                        fontSize  = 12.sp,
                        lineHeight = 17.sp,
                        maxLines  = 4,
                        overflow  = TextOverflow.Ellipsis
                    )

                    Spacer(modifier = Modifier.height(8.dp))

                    // Driver chips
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.spacedBy(6.dp)
                    ) {
                        val drivers = item.drivers?.takeIf { it.isNotEmpty() } ?: listOf(
                            if (isBuy) "Trend: Bullish" else "Trend: Bearish",
                            if (isBuy) "Bid Skew" else "Ask Wall",
                            "ATR Scalp"
                        )
                        drivers.take(3).forEach { driver ->
                            Box(
                                modifier = Modifier
                                    .clip(RoundedCornerShape(6.dp))
                                    .background(Color.White.copy(0.05f))
                                    .border(1.dp, BorderColorDim, RoundedCornerShape(6.dp))
                                    .padding(horizontal = 7.dp, vertical = 3.dp)
                            ) {
                                Text(
                                    text       = driver,
                                    color      = TextSecondary,
                                    fontSize   = 10.sp,
                                    fontFamily = FontFamily.Monospace,
                                    maxLines   = 1
                                )
                            }
                        }
                    }
                }
            }

            Spacer(modifier = Modifier.height(12.dp))

            // Trade Matrix: 4 cells
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(6.dp)
            ) {
                TradeMatrixCell("📍 ENTRY ZONE", punchText,    "Punch Area",   CyanAccent,   Modifier.weight(1.5f))
                TradeMatrixCell("🎯 TARGET",     "$${String.format("%,.4g", targetPrice)}", "+${item.targetPct}% TP", ProfitGreen, Modifier.weight(1f))
                TradeMatrixCell("🛑 STOP",       "$${String.format("%,.4g", stopPrice)}",   "${item.stopPct}% SL",  LossRed,     Modifier.weight(1f))
                TradeMatrixCell("⚖ R:R",         item.riskReward ?: "1:1.5",  "Ratio",       AmberWarning, Modifier.weight(0.85f))
            }

            Spacer(modifier = Modifier.height(14.dp))

            // Action buttons
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(8.dp),
                verticalAlignment = Alignment.CenterVertically
            ) {
                Button(
                    onClick  = { onPunch(item.symbol, if (isBuy) "buy" else "sell") },
                    colors   = ButtonDefaults.buttonColors(containerColor = primaryColor),
                    shape    = RoundedCornerShape(12.dp),
                    modifier = Modifier.weight(1f),
                    contentPadding = PaddingValues(vertical = 12.dp)
                ) {
                    Icon(Icons.Default.ElectricBolt, null, tint = Color.Black, modifier = Modifier.size(16.dp))
                    Spacer(modifier = Modifier.width(6.dp))
                    Text(
                        text       = if (isBuy) "PUNCH BUY 4×" else "PUNCH SELL 4×",
                        color      = Color.Black,
                        fontSize   = 13.sp,
                        fontWeight = FontWeight.Black
                    )
                }

                OutlinedButton(
                    onClick = { onPunch(item.symbol, if (isBuy) "sell" else "buy") },
                    shape   = RoundedCornerShape(12.dp),
                    colors  = ButtonDefaults.outlinedButtonColors(
                        contentColor = if (isBuy) LossRed else EmeraldPrimary
                    ),
                    border  = androidx.compose.foundation.BorderStroke(
                        1.dp, if (isBuy) LossRed.copy(0.5f) else EmeraldPrimary.copy(0.5f)
                    ),
                    modifier = Modifier.width(72.dp),
                    contentPadding = PaddingValues(vertical = 12.dp)
                ) {
                    Text(
                        text       = if (isBuy) "Short" else "Long",
                        fontSize   = 12.sp,
                        fontWeight = FontWeight.Black
                    )
                }
            }
        }
    }
}

// ─── Score Badge ──────────────────────────────────────────────────────────────

@Composable
fun ScoreBadge(score: Int) {
    val color = when {
        score >= 80 -> EmeraldPrimary
        score >= 65 -> AmberWarning
        else        -> TextMuted
    }
    Column(
        modifier = Modifier
            .clip(RoundedCornerShape(8.dp))
            .background(color.copy(0.12f))
            .padding(horizontal = 8.dp, vertical = 5.dp),
        horizontalAlignment = Alignment.CenterHorizontally
    ) {
        Text(
            text       = "$score",
            color      = color,
            fontSize   = 16.sp,
            fontWeight = FontWeight.Black,
            fontFamily = FontFamily.Monospace
        )
        Text("score", color = TextMuted, fontSize = 8.sp)
    }
}

// ─── Trade Matrix Cell ────────────────────────────────────────────────────────

@Composable
fun TradeMatrixCell(
    title: String,
    value: String,
    subtitle: String,
    color: Color,
    modifier: Modifier = Modifier
) {
    Box(
        modifier = modifier
            .clip(RoundedCornerShape(10.dp))
            .background(color.copy(0.07f))
            .border(1.dp, color.copy(0.22f), RoundedCornerShape(10.dp))
            .padding(horizontal = 5.dp, vertical = 8.dp),
        contentAlignment = Alignment.Center
    ) {
        Column(horizontalAlignment = Alignment.CenterHorizontally) {
            Text(
                text       = title,
                color      = color,
                fontSize   = 8.sp,
                fontWeight = FontWeight.Black,
                maxLines   = 1,
                overflow   = TextOverflow.Ellipsis
            )
            Spacer(modifier = Modifier.height(3.dp))
            Text(
                text       = value,
                color      = TextPrimary,
                fontSize   = 10.sp,
                fontWeight = FontWeight.Bold,
                fontFamily = FontFamily.Monospace,
                maxLines   = 1,
                overflow   = TextOverflow.Ellipsis
            )
            Text(subtitle, color = TextMuted, fontSize = 8.sp)
        }
    }
}
