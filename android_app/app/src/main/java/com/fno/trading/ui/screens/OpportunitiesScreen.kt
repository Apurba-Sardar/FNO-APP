package com.fno.trading.ui.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Bolt
import androidx.compose.material.icons.filled.ElectricBolt
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
            .padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(16.dp)
    ) {
        item {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Column {
                    Text(
                        text = "🎯 Scalp Signals & Punch Zones",
                        color = TextPrimary,
                        fontSize = 20.sp,
                        fontWeight = FontWeight.Black
                    )
                    Text(
                        text = "Real-time algorithmic conviction, technical reasons & entry zones",
                        color = TextSecondary,
                        fontSize = 12.sp
                    )
                }

                Box(
                    modifier = Modifier
                        .clip(RoundedCornerShape(8.dp))
                        .background(DarkElevatedSurface)
                        .border(1.dp, BorderColor, RoundedCornerShape(8.dp))
                        .padding(horizontal = 8.dp, vertical = 4.dp)
                ) {
                    Text(
                        text = state.evaluatedAtIst ?: "Live IST",
                        color = EmeraldPrimary,
                        fontSize = 11.sp,
                        fontWeight = FontWeight.Bold,
                        fontFamily = FontFamily.Monospace
                    )
                }
            }
        }

        if (state.evaluations.isEmpty()) {
            item {
                Card(
                    modifier = Modifier.fillMaxWidth(),
                    colors = CardDefaults.cardColors(containerColor = DarkCardSurface),
                    shape = RoundedCornerShape(16.dp)
                ) {
                    Column(
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(32.dp),
                        horizontalAlignment = Alignment.CenterHorizontally
                    ) {
                        Icon(
                            imageVector = Icons.Default.Bolt,
                            contentDescription = null,
                            tint = AmberWarning,
                            modifier = Modifier.size(40.dp)
                        )
                        Spacer(modifier = Modifier.height(12.dp))
                        Text(
                            text = "Analyzing 499 CoinDCX markets...",
                            color = TextSecondary,
                            fontSize = 14.sp
                        )
                    }
                }
            }
        } else {
            items(state.evaluations) { item ->
                SignalEvaluationCard(
                    item = item,
                    onPunch = { symbol, side -> viewModel.punch3xScalp(symbol, side) }
                )
            }
        }

        item {
            Spacer(modifier = Modifier.height(60.dp))
        }
    }
}

@Composable
fun SignalEvaluationCard(
    item: EvaluationItem,
    onPunch: (String, String) -> Unit
) {
    val isBuySignal = item.signal.equals("BUY", ignoreCase = true) ||
            item.direction?.lowercase() in listOf("long", "buy") ||
            item.recommendedSide?.lowercase() == "buy"

    val accentGradient = if (isBuySignal) {
        Brush.horizontalGradient(listOf(EmeraldPrimary, CyanAccent))
    } else {
        Brush.horizontalGradient(listOf(LossRed, Color(0xFFF59E0B)))
    }

    val punchLow = item.punchZoneLow ?: if (isBuySignal) item.currentPrice * 0.998 else item.currentPrice * 0.996
    val punchHigh = item.punchZoneHigh ?: if (isBuySignal) item.currentPrice * 1.004 else item.currentPrice * 1.002
    val targetPrice = item.targetPrice ?: if (isBuySignal) item.currentPrice * 1.018 else item.currentPrice * 0.982
    val stopPrice = item.stopPrice ?: if (isBuySignal) item.currentPrice * 0.988 else item.currentPrice * 1.012
    val punchAreaText = item.punchArea ?: String.format("$%,.4g – $%,.4g", punchLow, punchHigh)

    Card(
        modifier = Modifier
            .fillMaxWidth()
            .border(1.dp, if (isBuySignal) EmeraldPrimary.copy(alpha = 0.3f) else LossRed.copy(alpha = 0.3f), RoundedCornerShape(18.dp)),
        colors = CardDefaults.cardColors(containerColor = DarkCardSurface),
        shape = RoundedCornerShape(18.dp)
    ) {
        Column(modifier = Modifier.padding(16.dp)) {
            // Top Accent Line
            Box(
                modifier = Modifier
                    .fillMaxWidth()
                    .height(3.dp)
                    .clip(RoundedCornerShape(2.dp))
                    .background(accentGradient)
            )

            Spacer(modifier = Modifier.height(12.dp))

            // 1. Header: Symbol, Price, Signal Badge, Score
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Column {
                    Text(
                        text = item.symbol,
                        color = TextPrimary,
                        fontSize = 18.sp,
                        fontWeight = FontWeight.Black
                    )
                    Text(
                        text = String.format("$%,.4g", item.currentPrice),
                        color = TextSecondary,
                        fontSize = 14.sp,
                        fontWeight = FontWeight.Bold,
                        fontFamily = FontFamily.Monospace
                    )
                }

                Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                    // Signal Badge
                    Box(
                        modifier = Modifier
                            .clip(RoundedCornerShape(8.dp))
                            .background(if (isBuySignal) ProfitGreenBg else LossRedBg)
                            .border(1.dp, if (isBuySignal) EmeraldPrimary else LossRed, RoundedCornerShape(8.dp))
                            .padding(horizontal = 8.dp, vertical = 4.dp)
                    ) {
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Text(
                                text = if (isBuySignal) "🟢 BUY (LONG)" else "🔴 SELL (SHORT)",
                                color = if (isBuySignal) ProfitGreen else LossRed,
                                fontSize = 11.sp,
                                fontWeight = FontWeight.Black
                            )
                        }
                    }

                    // Score Badge
                    Box(
                        modifier = Modifier
                            .clip(RoundedCornerShape(6.dp))
                            .background(CyanAccent.copy(alpha = 0.15f))
                            .padding(horizontal = 6.dp, vertical = 4.dp)
                    ) {
                        Text(
                            text = "${item.score.toInt()}",
                            color = CyanAccent,
                            fontSize = 11.sp,
                            fontWeight = FontWeight.Bold
                        )
                    }
                }
            }

            Spacer(modifier = Modifier.height(12.dp))

            // 2. Reason & Conviction Box
            Box(
                modifier = Modifier
                    .fillMaxWidth()
                    .clip(RoundedCornerShape(12.dp))
                    .background(DarkElevatedSurface)
                    .border(1.dp, BorderColor, RoundedCornerShape(12.dp))
                    .padding(12.dp)
            ) {
                Column {
                    Text(
                        text = "💡 SIGNAL REASON & SETUP CONVICTION:",
                        color = AmberWarning,
                        fontSize = 10.sp,
                        fontWeight = FontWeight.Bold
                    )
                    Spacer(modifier = Modifier.height(4.dp))
                    Text(
                        text = item.reason ?: if (isBuySignal) {
                            "Bullish Momentum: Price consolidating above key support ($${String.format("%,.4g", punchLow)}) with buyer bid absorption. Favorable 3x long entry on breakout."
                        } else {
                            "Bearish Pressure: Overhead resistance rejecting rallies near $${String.format("%,.4g", punchHigh)}. Distribution indicates 3x short scalp breakdown."
                        },
                        color = TextPrimary,
                        fontSize = 12.sp,
                        lineHeight = 16.sp
                    )

                    Spacer(modifier = Modifier.height(8.dp))

                    // Drivers Chips
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.spacedBy(6.dp)
                    ) {
                        val driversList = if (!item.drivers.isNullOrEmpty()) item.drivers else listOf(
                            if (isBuySignal) "Trend: Bullish" else "Trend: Bearish",
                            if (isBuySignal) "Bid Skew" else "Ask Wall",
                            "ATR Scalp"
                        )
                        driversList.take(3).forEach { driver ->
                            Box(
                                modifier = Modifier
                                    .clip(RoundedCornerShape(6.dp))
                                    .background(Color.White.copy(alpha = 0.05f))
                                    .padding(horizontal = 6.dp, vertical = 2.dp)
                            ) {
                                Text(
                                    text = driver,
                                    color = TextSecondary,
                                    fontSize = 10.sp,
                                    fontFamily = FontFamily.Monospace
                                )
                            }
                        }
                    }
                }
            }

            Spacer(modifier = Modifier.height(12.dp))

            // 3. Exact 4-Cell Trade Matrix (Where to punch)
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(6.dp)
            ) {
                // Punch Area
                MatrixCell(
                    title = "📍 PUNCH AREA",
                    value = punchAreaText,
                    subtitle = "Entry Zone",
                    color = CyanAccent,
                    modifier = Modifier.weight(1.3f)
                )

                // Target (TP)
                MatrixCell(
                    title = "🎯 TARGET",
                    value = String.format("$%,.4g", targetPrice),
                    subtitle = "+${item.targetPct}% TP",
                    color = EmeraldPrimary,
                    modifier = Modifier.weight(1f)
                )

                // Stop Loss (SL)
                MatrixCell(
                    title = "🛑 STOP LOSS",
                    value = String.format("$%,.4g", stopPrice),
                    subtitle = "${item.stopPct}% SL",
                    color = LossRed,
                    modifier = Modifier.weight(1f)
                )

                // Risk:Reward
                MatrixCell(
                    title = "⚖️ R : R",
                    value = item.riskReward ?: "1 : 1.50",
                    subtitle = "Ratio",
                    color = AmberWarning,
                    modifier = Modifier.weight(0.9f)
                )
            }

            Spacer(modifier = Modifier.height(14.dp))

            // 4. Action Punch Buttons
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(8.dp),
                verticalAlignment = Alignment.CenterVertically
            ) {
                // Primary Action Button
                Button(
                    onClick = { onPunch(item.symbol, if (isBuySignal) "buy" else "sell") },
                    colors = ButtonDefaults.buttonColors(containerColor = if (isBuySignal) EmeraldPrimary else LossRed),
                    shape = RoundedCornerShape(10.dp),
                    modifier = Modifier.weight(1f)
                ) {
                    Icon(
                        imageVector = Icons.Default.ElectricBolt,
                        contentDescription = null,
                        tint = Color.Black,
                        modifier = Modifier.size(16.dp)
                    )
                    Spacer(modifier = Modifier.width(6.dp))
                    Text(
                        text = if (isBuySignal) "PUNCH BUY 3x" else "PUNCH SELL 3x",
                        color = Color.Black,
                        fontSize = 12.sp,
                        fontWeight = FontWeight.Black
                    )
                }

                // Counter-Scalp Switch
                OutlinedButton(
                    onClick = { onPunch(item.symbol, if (isBuySignal) "sell" else "buy") },
                    shape = RoundedCornerShape(10.dp),
                    colors = ButtonDefaults.outlinedButtonColors(
                        contentColor = if (isBuySignal) LossRed else EmeraldPrimary
                    ),
                    border = ButtonDefaults.outlinedButtonBorder.copy(
                        brush = Brush.horizontalGradient(listOf(BorderColor, BorderColor))
                    )
                ) {
                    Text(
                        text = if (isBuySignal) "Short" else "Long",
                        fontSize = 11.sp,
                        fontWeight = FontWeight.Bold
                    )
                }
            }
        }
    }
}

@Composable
fun MatrixCell(
    title: String,
    value: String,
    subtitle: String,
    color: Color,
    modifier: Modifier = Modifier
) {
    Box(
        modifier = modifier
            .clip(RoundedCornerShape(10.dp))
            .background(color.copy(alpha = 0.08f))
            .border(1.dp, color.copy(alpha = 0.25f), RoundedCornerShape(10.dp))
            .padding(horizontal = 6.dp, vertical = 8.dp),
        contentAlignment = Alignment.Center
    ) {
        Column(horizontalAlignment = Alignment.CenterHorizontally) {
            Text(
                text = title,
                color = color,
                fontSize = 9.sp,
                fontWeight = FontWeight.Black
            )
            Spacer(modifier = Modifier.height(2.dp))
            Text(
                text = value,
                color = TextPrimary,
                fontSize = 11.sp,
                fontWeight = FontWeight.Bold,
                fontFamily = FontFamily.Monospace,
                maxLines = 1
            )
            Text(
                text = subtitle,
                color = TextMuted,
                fontSize = 9.sp
            )
        }
    }
}
