package com.fno.trading.ui.screens

import androidx.compose.animation.AnimatedVisibility
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.fno.trading.data.model.PositionItem
import com.fno.trading.ui.TradingUiState
import com.fno.trading.ui.TradingViewModel
import com.fno.trading.ui.theme.*

@Composable
fun LivePortfolioScreen(
    viewModel: TradingViewModel,
    modifier: Modifier = Modifier
) {
    val state by viewModel.uiState.collectAsState()
    val openPositions = remember(state.positions) {
        state.positions.filter { it.status == "open" }
    }

    LazyColumn(
        modifier = modifier
            .fillMaxSize()
            .background(AmoledBackground)
            .padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(16.dp)
    ) {
        // 1. Header Balance & Daily Goal Card
        item {
            AccountBalanceCard(
                state = state,
                onRefresh = { viewModel.loadData() },
                onSendTestAlert = { viewModel.sendTestAlert() }
            )
        }

        // Safety Circuit Alert if blocked
        if (state.status?.runtimeState == "blocked" || state.status?.circuitBreaker == "open" || state.errorMessage != null) {
            item {
                Card(
                    modifier = Modifier
                        .fillMaxWidth()
                        .border(1.dp, AmberWarning, RoundedCornerShape(14.dp)),
                    colors = CardDefaults.cardColors(containerColor = AmberWarning.copy(alpha = 0.12f)),
                    shape = RoundedCornerShape(14.dp)
                ) {
                    Column(modifier = Modifier.padding(14.dp)) {
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Icon(Icons.Default.Warning, contentDescription = null, tint = AmberWarning, modifier = Modifier.size(18.dp))
                            Spacer(modifier = Modifier.width(8.dp))
                            Text(
                                text = "Safety Alert: ${state.status?.lastApiError ?: state.errorMessage ?: "Engine Blocked"}",
                                color = AmberWarning,
                                fontSize = 12.sp,
                                fontWeight = FontWeight.Bold
                            )
                        }
                        Spacer(modifier = Modifier.height(8.dp))
                        Button(
                            onClick = { viewModel.resetCircuit() },
                            colors = ButtonDefaults.buttonColors(containerColor = AmberWarning),
                            shape = RoundedCornerShape(8.dp),
                            modifier = Modifier.fillMaxWidth()
                        ) {
                            Text(text = "Unblock & Reconcile Engine", color = Color.Black, fontWeight = FontWeight.Bold, fontSize = 12.sp)
                        }
                    }
                }
            }
        }

        // Margin Notice Banner if cash < $5
        val freeCash = state.account?.availableBalance ?: 100.0
        if (freeCash < 5.0 && openPositions.isNotEmpty()) {
            item {
                Card(
                    modifier = Modifier
                        .fillMaxWidth()
                        .border(1.dp, CyanAccent.copy(alpha = 0.4f), RoundedCornerShape(14.dp)),
                    colors = CardDefaults.cardColors(containerColor = DarkElevatedSurface),
                    shape = RoundedCornerShape(14.dp)
                ) {
                    Row(
                        modifier = Modifier.padding(12.dp),
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Icon(Icons.Default.Info, contentDescription = null, tint = CyanAccent, modifier = Modifier.size(20.dp))
                        Spacer(modifier = Modifier.width(10.dp))
                        Column {
                            Text(
                                text = "Margin Locked ($${String.format("%,.2f", state.account?.marginUsed ?: 0.0)})",
                                color = CyanAccent,
                                fontSize = 12.sp,
                                fontWeight = FontWeight.Bold
                            )
                            Text(
                                text = "Cash available is $${String.format("%,.2f", freeCash)}. Close any open position below to release margin immediately for new 3x scalps.",
                                color = TextSecondary,
                                fontSize = 11.sp
                            )
                        }
                    }
                }
            }
        }

        // 2. Scalp Controls & Status Strip
        item {
            EngineStatusStrip(
                state = state,
                onToggleAutoTrading = { viewModel.toggleAutoTrading() },
                onPunchScalp = { symbol, side, qty -> viewModel.punch3xScalp(symbol, side, qty) }
            )
        }

        // 3. Open Positions Header
        item {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Text(
                        text = "Open Positions",
                        color = TextPrimary,
                        fontSize = 18.sp,
                        fontWeight = FontWeight.Bold
                    )
                    Spacer(modifier = Modifier.width(8.dp))
                    Box(
                        modifier = Modifier
                            .clip(CircleShape)
                            .background(EmeraldPrimary.copy(alpha = 0.2f))
                            .padding(horizontal = 8.dp, vertical = 2.dp)
                    ) {
                        Text(
                            text = "${openPositions.size} Active",
                            color = EmeraldPrimary,
                            fontSize = 12.sp,
                            fontWeight = FontWeight.Bold
                        )
                    }
                }
            }
        }

        // 4. Position Cards
        if (openPositions.isEmpty()) {
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
                            imageVector = Icons.Default.Shield,
                            contentDescription = null,
                            tint = TextMuted,
                            modifier = Modifier.size(40.dp)
                        )
                        Spacer(modifier = Modifier.height(12.dp))
                        Text(
                            text = "No open positions currently",
                            color = TextSecondary,
                            fontSize = 14.sp
                        )
                        Text(
                            text = "Auto-Engine is scanning high-probability 3x scalps",
                            color = TextMuted,
                            fontSize = 12.sp
                        )
                    }
                }
            }
        } else {
            items(openPositions) { pos ->
                PositionCard(
                    position = pos,
                    onExit = { id, pair -> viewModel.exitPosition(id, pair) }
                )
            }
        }

        // Bottom Padding for navigation bar
        item {
            Spacer(modifier = Modifier.height(60.dp))
        }
    }
}

@Composable
fun AccountBalanceCard(
    state: TradingUiState,
    onRefresh: () -> Unit,
    onSendTestAlert: () -> Unit
) {
    val account = state.account
    val dailyPnl = account?.dailyPnl ?: 0.0
    val target = state.status?.dailyProfitTarget ?: 10.0
    val progress = (dailyPnl / target).coerceIn(0.0, 1.0).toFloat()
    val isProfit = dailyPnl >= 0

    Card(
        modifier = Modifier
            .fillMaxWidth()
            .border(1.dp, BorderColor, RoundedCornerShape(20.dp)),
        colors = CardDefaults.cardColors(containerColor = DarkCardSurface),
        shape = RoundedCornerShape(20.dp)
    ) {
        Column(modifier = Modifier.padding(18.dp)) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Box(
                        modifier = Modifier
                            .size(10.dp)
                            .clip(CircleShape)
                            .background(EmeraldPrimary)
                    )
                    Spacer(modifier = Modifier.width(8.dp))
                    Text(
                        text = "COINDCX FUTURES LIVE",
                        color = EmeraldPrimary,
                        fontSize = 11.sp,
                        fontWeight = FontWeight.Bold,
                        letterSpacing = 1.sp
                    )
                }

                Row {
                    IconButton(onClick = onSendTestAlert, modifier = Modifier.size(32.dp)) {
                        Icon(
                            imageVector = Icons.Default.Notifications,
                            contentDescription = "Test Notification",
                            tint = CyanAccent
                        )
                    }
                    Spacer(modifier = Modifier.width(4.dp))
                    IconButton(onClick = onRefresh, modifier = Modifier.size(32.dp)) {
                        Icon(
                            imageVector = Icons.Default.Refresh,
                            contentDescription = "Refresh",
                            tint = TextSecondary
                        )
                    }
                }
            }

            Spacer(modifier = Modifier.height(14.dp))

            Text(
                text = "Total Account Equity",
                color = TextSecondary,
                fontSize = 12.sp
            )
            Text(
                text = "$${String.format("%,.2f", account?.equity ?: 1059.07)} USDT",
                color = TextPrimary,
                fontSize = 32.sp,
                fontWeight = FontWeight.Black
            )

            Spacer(modifier = Modifier.height(14.dp))

            // Free Cash & Margin row
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween
            ) {
                Column {
                    Text(text = "Available Cash", color = TextMuted, fontSize = 11.sp)
                    Text(
                        text = "$${String.format("%,.2f", account?.availableBalance ?: 1000.0)}",
                        color = TextPrimary,
                        fontSize = 15.sp,
                        fontWeight = FontWeight.Bold
                    )
                }
                Column(horizontalAlignment = Alignment.End) {
                    Text(text = "Margin Locked", color = TextMuted, fontSize = 11.sp)
                    Text(
                        text = "$${String.format("%,.2f", account?.marginUsed ?: 0.0)}",
                        color = TextPrimary,
                        fontSize = 15.sp,
                        fontWeight = FontWeight.Bold
                    )
                }
            }

            Spacer(modifier = Modifier.height(16.dp))

            // Daily Profit Target Progress Bar ($10 Cap)
            Box(
                modifier = Modifier
                    .fillMaxWidth()
                    .clip(RoundedCornerShape(12.dp))
                    .background(DarkElevatedSurface)
                    .padding(12.dp)
            ) {
                Column {
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween
                    ) {
                        Text(
                            text = "Daily Goal ($10.00 Cap)",
                            color = TextSecondary,
                            fontSize = 12.sp,
                            fontWeight = FontWeight.Medium
                        )
                        Text(
                            text = "${if (isProfit) "+" else ""}$${String.format("%.2f", dailyPnl)} / $${String.format("%.2f", target)}",
                            color = if (isProfit) ProfitGreen else LossRed,
                            fontSize = 12.sp,
                            fontWeight = FontWeight.Bold
                        )
                    }

                    Spacer(modifier = Modifier.height(8.dp))

                    LinearProgressIndicator(
                        progress = { progress },
                        modifier = Modifier
                            .fillMaxWidth()
                            .height(8.dp)
                            .clip(RoundedCornerShape(4.dp)),
                        color = if (dailyPnl >= target) AmberWarning else EmeraldPrimary,
                        trackColor = Color(0xFF334155)
                    )

                    if (dailyPnl >= target) {
                        Spacer(modifier = Modifier.height(6.dp))
                        Text(
                            text = "🏆 GOAL REACHED! Profits Locked for Today.",
                            color = AmberWarning,
                            fontSize = 11.sp,
                            fontWeight = FontWeight.Bold
                        )
                    }
                }
            }
        }
    }
}

@Composable
fun EngineStatusStrip(
    state: TradingUiState,
    onToggleAutoTrading: () -> Unit,
    onPunchScalp: (String, String, Double) -> Unit
) {
    val autoActive = state.status?.autoExecution == true

    Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
        // Badges Row
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.spacedBy(8.dp)
        ) {
            BadgeChip(
                label = "Auto-Close",
                subLabel = "+1.8% / -1.2%",
                color = ProfitGreen,
                modifier = Modifier.weight(1f)
            )
            BadgeChip(
                label = "3x Isolated",
                subLabel = "Enforced",
                color = CyanAccent,
                modifier = Modifier.weight(1f)
            )
        }

        // Scalp Action Buttons Row
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.spacedBy(8.dp)
        ) {
            Button(
                onClick = { onPunchScalp("B-XRP_USDT", "buy", 15.0) },
                colors = ButtonDefaults.buttonColors(containerColor = DarkElevatedSurface),
                shape = RoundedCornerShape(12.dp),
                modifier = Modifier
                    .weight(1f)
                    .border(1.dp, CyanAccent.copy(alpha = 0.4f), RoundedCornerShape(12.dp))
            ) {
                Text(text = "⚡ XRP 3x Scalp", color = CyanAccent, fontSize = 12.sp, fontWeight = FontWeight.Bold)
            }

            Button(
                onClick = { onPunchScalp("B-DOGE_USDT", "buy", 100.0) },
                colors = ButtonDefaults.buttonColors(containerColor = DarkElevatedSurface),
                shape = RoundedCornerShape(12.dp),
                modifier = Modifier
                    .weight(1f)
                    .border(1.dp, AmberWarning.copy(alpha = 0.4f), RoundedCornerShape(12.dp))
            ) {
                Text(text = "⚡ DOGE 3x Scalp", color = AmberWarning, fontSize = 12.sp, fontWeight = FontWeight.Bold)
            }
        }
    }
}

@Composable
fun BadgeChip(label: String, subLabel: String, color: Color, modifier: Modifier = Modifier) {
    Box(
        modifier = modifier
            .clip(RoundedCornerShape(10.dp))
            .background(color.copy(alpha = 0.12f))
            .border(1.dp, color.copy(alpha = 0.3f), RoundedCornerShape(10.dp))
            .padding(vertical = 8.dp, horizontal = 10.dp),
        contentAlignment = Alignment.Center
    ) {
        Column(horizontalAlignment = Alignment.CenterHorizontally) {
            Text(text = label, color = color, fontSize = 11.sp, fontWeight = FontWeight.Bold)
            Text(text = subLabel, color = TextSecondary, fontSize = 10.sp)
        }
    }
}

@Composable
fun PositionCard(
    position: PositionItem,
    onExit: (String, String) -> Unit
) {
    val isLong = position.direction.lowercase() == "long" || position.direction.lowercase() == "buy"
    val pnl = position.unrealizedPnl
    val isProfit = pnl >= 0
    val entry = position.averagePrice
    val mark = position.markPrice ?: entry
    val diffPct = if (entry > 0) {
        if (isLong) ((mark - entry) / entry) * 100 else ((entry - mark) / entry) * 100
    } else 0.0
    val roePct = diffPct * (position.leverage ?: 3)

    Card(
        modifier = Modifier
            .fillMaxWidth()
            .border(1.dp, if (isProfit) ProfitGreen.copy(alpha = 0.4f) else LossRed.copy(alpha = 0.4f), RoundedCornerShape(16.dp)),
        colors = CardDefaults.cardColors(containerColor = DarkCardSurface),
        shape = RoundedCornerShape(16.dp)
    ) {
        Column(modifier = Modifier.padding(16.dp)) {
            // Top Row: Symbol, Side, Badge
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Text(
                        text = position.pair.replace("B-", "").replace("_USDT", ""),
                        color = TextPrimary,
                        fontSize = 18.sp,
                        fontWeight = FontWeight.Black
                    )
                    Spacer(modifier = Modifier.width(8.dp))
                    Box(
                        modifier = Modifier
                            .clip(RoundedCornerShape(6.dp))
                            .background(if (isLong) ProfitGreenBg else LossRedBg)
                            .padding(horizontal = 6.dp, vertical = 2.dp)
                    ) {
                        Text(
                            text = if (isLong) "BUY (LONG)" else "SELL (SHORT)",
                            color = if (isLong) ProfitGreen else LossRed,
                            fontSize = 10.sp,
                            fontWeight = FontWeight.Bold
                        )
                    }
                    Spacer(modifier = Modifier.width(6.dp))
                    Text(
                        text = "${position.leverage ?: 3}x",
                        color = CyanAccent,
                        fontSize = 11.sp,
                        fontWeight = FontWeight.Bold
                    )
                }

                Box(
                    modifier = Modifier
                        .clip(RoundedCornerShape(6.dp))
                        .background(EmeraldPrimary.copy(alpha = 0.15f))
                        .padding(horizontal = 6.dp, vertical = 2.dp)
                ) {
                    Text(
                        text = "🛡️ Auto-Close Active",
                        color = EmeraldPrimary,
                        fontSize = 10.sp,
                        fontWeight = FontWeight.Bold
                    )
                }
            }

            Spacer(modifier = Modifier.height(12.dp))

            // Main P&L Row
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.Bottom
            ) {
                Column {
                    Text(text = "Unrealized P&L", color = TextMuted, fontSize = 11.sp)
                    Text(
                        text = "${if (isProfit) "+" else ""}$${String.format("%.4f", pnl)} USDT",
                        color = if (isProfit) ProfitGreen else LossRed,
                        fontSize = 22.sp,
                        fontWeight = FontWeight.Black
                    )
                }

                Box(
                    modifier = Modifier
                        .clip(RoundedCornerShape(8.dp))
                        .background(if (isProfit) ProfitGreenBg else LossRedBg)
                        .padding(horizontal = 10.dp, vertical = 4.dp)
                ) {
                    Text(
                        text = "${if (roePct >= 0) "+" else ""}${String.format("%.2f", roePct)}% ROE",
                        color = if (isProfit) ProfitGreen else LossRed,
                        fontSize = 14.sp,
                        fontWeight = FontWeight.Bold
                    )
                }
            }

            Spacer(modifier = Modifier.height(14.dp))
            Divider(color = BorderColor.copy(alpha = 0.5f))
            Spacer(modifier = Modifier.height(12.dp))

            // Details Grid
            Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                Column {
                    Text(text = "Entry Price", color = TextMuted, fontSize = 11.sp)
                    Text(text = "$${String.format("%.5g", entry)}", color = TextPrimary, fontSize = 13.sp, fontWeight = FontWeight.Bold)
                }
                Column {
                    Text(text = "Current Mark", color = TextMuted, fontSize = 11.sp)
                    Text(text = "$${String.format("%.5g", mark)}", color = CyanAccent, fontSize = 13.sp, fontWeight = FontWeight.Bold)
                }
                Column(horizontalAlignment = Alignment.End) {
                    Text(text = "Target (+1.8%)", color = TextMuted, fontSize = 11.sp)
                    Text(text = "$${String.format("%.5g", position.target ?: (entry * 1.018))}", color = ProfitGreen, fontSize = 13.sp, fontWeight = FontWeight.Bold)
                }
            }

            Spacer(modifier = Modifier.height(14.dp))

            // Market Exit Button
            Button(
                onClick = { onExit(position.exchangePositionId ?: position.positionId ?: "", position.pair) },
                colors = ButtonDefaults.buttonColors(containerColor = LossRed.copy(alpha = 0.15f)),
                shape = RoundedCornerShape(10.dp),
                modifier = Modifier
                    .fillMaxWidth()
                    .border(1.dp, LossRed.copy(alpha = 0.4f), RoundedCornerShape(10.dp))
            ) {
                Icon(imageVector = Icons.Default.Close, contentDescription = null, tint = LossRed, modifier = Modifier.size(16.dp))
                Spacer(modifier = Modifier.width(6.dp))
                Text(text = "Exit Position at Market", color = LossRed, fontSize = 12.sp, fontWeight = FontWeight.Bold)
            }
        }
    }
}
