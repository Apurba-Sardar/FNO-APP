package com.fno.trading.ui.screens

import androidx.compose.animation.*
import androidx.compose.animation.core.*
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material.icons.outlined.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.scale
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
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
            .padding(horizontal = 14.dp),
        verticalArrangement = Arrangement.spacedBy(14.dp),
        contentPadding = PaddingValues(top = 14.dp, bottom = 80.dp)
    ) {
        // ── 1. Balance Hero Card ──────────────────────────────────────
        item {
            AccountBalanceCard(
                state         = state,
                onRefresh     = { viewModel.loadData() },
                onSendTestAlert = { viewModel.sendTestAlert() }
            )
        }

        // ── 2. Alerts ─────────────────────────────────────────────────
        val blocked = state.status?.runtimeState == "blocked" ||
                state.status?.circuitBreaker == "open" ||
                state.errorMessage != null
        if (blocked) {
            item { SafetyAlertCard(state = state, onReset = { viewModel.resetCircuit() }) }
        }

        val freeCash = state.account?.availableBalance ?: 100.0
        if (freeCash < 5.0 && openPositions.isNotEmpty()) {
            item { MarginNoticeCard(state = state, freeCash = freeCash) }
        }

        // ── 3. Engine Controls ────────────────────────────────────────
        item {
            EngineStatusStrip(
                state              = state,
                onToggleAutoTrading = { viewModel.toggleAutoTrading() },
                onPunchScalp       = { sym, side, qty -> viewModel.punch3xScalp(sym, side, qty) }
            )
        }

        // ── 4. Loading indicator ──────────────────────────────────────
        if (state.isLoading) {
            item {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.Center
                ) {
                    CircularProgressIndicator(
                        color       = EmeraldPrimary,
                        strokeWidth = 2.dp,
                        modifier    = Modifier.size(22.dp)
                    )
                    Spacer(modifier = Modifier.width(8.dp))
                    Text(
                        text      = state.statusMessage,
                        color     = TextSecondary,
                        fontSize  = 12.sp,
                        maxLines  = 1,
                        overflow  = TextOverflow.Ellipsis
                    )
                }
            }
        }

        // ── 5. Open Positions ─────────────────────────────────────────
        item {
            Row(
                modifier  = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Text(
                        text       = "Open Positions",
                        color      = TextPrimary,
                        fontSize   = 17.sp,
                        fontWeight = FontWeight.ExtraBold
                    )
                    Spacer(modifier = Modifier.width(8.dp))
                    AnimatedContent(targetState = openPositions.size, label = "cnt") { cnt ->
                        Surface(
                            shape   = RoundedCornerShape(20.dp),
                            color   = if (cnt > 0) EmeraldPrimary.copy(alpha = 0.18f) else DarkElevatedSurface
                        ) {
                            Text(
                                text       = "$cnt Active",
                                color      = if (cnt > 0) EmeraldPrimary else TextMuted,
                                fontSize   = 11.sp,
                                fontWeight = FontWeight.Bold,
                                modifier   = Modifier.padding(horizontal = 8.dp, vertical = 3.dp)
                            )
                        }
                    }
                }
                TextButton(onClick = { viewModel.loadData() }) {
                    Icon(Icons.Default.Sync, contentDescription = null, tint = CyanAccent, modifier = Modifier.size(14.dp))
                    Spacer(modifier = Modifier.width(3.dp))
                    Text("Sync", color = CyanAccent, fontSize = 11.sp)
                }
            }
        }

        if (openPositions.isEmpty()) {
            item {
                EmptyPositionsCard()
            }
        } else {
            items(openPositions, key = { it.positionId ?: it.pair }) { pos ->
                PositionCard(
                    position = pos,
                    onExit   = { id, pair -> viewModel.exitPosition(id, pair) }
                )
            }
        }
    }
}

// ─── Account Balance Hero ─────────────────────────────────────────────────────

@Composable
fun AccountBalanceCard(
    state: TradingUiState,
    onRefresh: () -> Unit,
    onSendTestAlert: () -> Unit
) {
    val account  = state.account
    val dailyPnl = account?.dailyPnl ?: 0.0
    val target   = state.status?.dailyProfitTarget ?: 6.0
    val progress = (dailyPnl / target).coerceIn(0.0, 1.0).toFloat()
    val isProfit = dailyPnl >= 0
    val goalHit  = dailyPnl >= target

    val animProgress by animateFloatAsState(
        targetValue    = progress,
        animationSpec  = tween(800, easing = EaseOutQuart),
        label          = "progress"
    )

    Card(
        modifier = Modifier
            .fillMaxWidth()
            .border(
                1.dp,
                Brush.linearGradient(listOf(EmeraldPrimary.copy(0.4f), CyanAccent.copy(0.2f), BorderColor.copy(0.3f))),
                RoundedCornerShape(22.dp)
            ),
        colors = CardDefaults.cardColors(containerColor = DarkCardSurface),
        shape  = RoundedCornerShape(22.dp),
        elevation = CardDefaults.cardElevation(defaultElevation = 0.dp)
    ) {
        Column(modifier = Modifier.padding(18.dp)) {

            // Header row
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    PulsingLiveDot(color = EmeraldPrimary)
                    Spacer(modifier = Modifier.width(6.dp))
                    Text(
                        text          = "COINDCX FUTURES LIVE",
                        color         = EmeraldPrimary,
                        fontSize      = 10.sp,
                        fontWeight    = FontWeight.Black,
                        letterSpacing = 1.2.sp
                    )
                }
                Row {
                    IconButton(onClick = onSendTestAlert, modifier = Modifier.size(34.dp)) {
                        Icon(Icons.Outlined.Notifications, null, tint = CyanAccent, modifier = Modifier.size(18.dp))
                    }
                    IconButton(onClick = onRefresh, modifier = Modifier.size(34.dp)) {
                        Icon(Icons.Default.Refresh, null, tint = TextMuted, modifier = Modifier.size(18.dp))
                    }
                }
            }

            Spacer(modifier = Modifier.height(12.dp))

            // Equity
            Text("Total Equity", color = TextMuted, fontSize = 11.sp)
            Text(
                text       = "$${String.format("%,.2f", account?.equity ?: 0.0)} USDT",
                color      = TextPrimary,
                fontSize   = 36.sp,
                fontWeight = FontWeight.Black,
                fontFamily = FontFamily.Monospace
            )

            Spacer(modifier = Modifier.height(14.dp))

            // Free Cash & Margin
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .clip(RoundedCornerShape(14.dp))
                    .background(DarkElevatedSurface)
                    .padding(12.dp),
                horizontalArrangement = Arrangement.SpaceBetween
            ) {
                Column {
                    Text("Free Cash", color = TextMuted, fontSize = 10.sp)
                    Text(
                        text       = "$${String.format("%,.2f", account?.availableBalance ?: 0.0)}",
                        color      = TextPrimary,
                        fontSize   = 16.sp,
                        fontWeight = FontWeight.Bold,
                        fontFamily = FontFamily.Monospace
                    )
                }
                Box(
                    modifier = Modifier
                        .width(1.dp)
                        .height(38.dp)
                        .background(BorderColor.copy(0.5f))
                )
                Column(horizontalAlignment = Alignment.End) {
                    Text("Margin Locked", color = TextMuted, fontSize = 10.sp)
                    Text(
                        text       = "$${String.format("%,.2f", account?.marginUsed ?: 0.0)}",
                        color      = AmberWarning,
                        fontSize   = 16.sp,
                        fontWeight = FontWeight.Bold,
                        fontFamily = FontFamily.Monospace
                    )
                }
            }

            Spacer(modifier = Modifier.height(14.dp))

            // Daily Goal Progress
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .clip(RoundedCornerShape(14.dp))
                    .background(DarkElevatedSurface)
                    .padding(12.dp)
            ) {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Text(
                        text       = if (goalHit) "🏆 DAILY GOAL REACHED!" else "Daily P&L Target",
                        color      = if (goalHit) GoldAccent else TextSecondary,
                        fontSize   = 11.sp,
                        fontWeight = FontWeight.Bold
                    )
                    Text(
                        text       = "${if (isProfit) "+" else ""}$${String.format("%.2f", dailyPnl)} / $${String.format("%.2f", target)}",
                        color      = if (isProfit) ProfitGreen else LossRed,
                        fontSize   = 12.sp,
                        fontWeight = FontWeight.Black,
                        fontFamily = FontFamily.Monospace
                    )
                }

                Spacer(modifier = Modifier.height(8.dp))

                LinearProgressIndicator(
                    progress      = { animProgress },
                    modifier      = Modifier.fillMaxWidth().height(10.dp).clip(RoundedCornerShape(5.dp)),
                    color         = if (goalHit) GoldAccent else EmeraldPrimary,
                    trackColor    = BorderColor,
                    strokeCap     = StrokeCap.Round
                )

                if (!goalHit) {
                    Spacer(modifier = Modifier.height(5.dp))
                    Text(
                        text   = "Scalp target: ≥ +$1.00/trade • 4x Leverage • $25 Margin",
                        color  = TextMuted,
                        fontSize = 10.sp
                    )
                } else {
                    Spacer(modifier = Modifier.height(5.dp))
                    Text(
                        text       = "🎉 Profits locked. Auto-engine paused until tomorrow.",
                        color      = GoldAccent,
                        fontSize   = 10.sp,
                        fontWeight = FontWeight.Bold
                    )
                }
            }
        }
    }
}

// ─── Safety Alert ─────────────────────────────────────────────────────────────

@Composable
fun SafetyAlertCard(state: TradingUiState, onReset: () -> Unit) {
    Card(
        modifier = Modifier
            .fillMaxWidth()
            .border(1.dp, LossRed.copy(0.5f), RoundedCornerShape(16.dp)),
        colors = CardDefaults.cardColors(containerColor = LossRed.copy(0.08f)),
        shape  = RoundedCornerShape(16.dp)
    ) {
        Column(modifier = Modifier.padding(14.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Icon(Icons.Default.Warning, null, tint = LossRed, modifier = Modifier.size(18.dp))
                Spacer(modifier = Modifier.width(8.dp))
                Text(
                    text       = "Safety Alert: ${state.status?.lastApiError ?: state.errorMessage ?: "Engine Blocked"}",
                    color      = LossRed,
                    fontSize   = 12.sp,
                    fontWeight = FontWeight.Bold,
                    maxLines   = 2,
                    overflow   = TextOverflow.Ellipsis
                )
            }
            Spacer(modifier = Modifier.height(10.dp))
            Button(
                onClick = onReset,
                colors  = ButtonDefaults.buttonColors(containerColor = LossRed),
                shape   = RoundedCornerShape(10.dp),
                modifier = Modifier.fillMaxWidth()
            ) {
                Icon(Icons.Default.RestartAlt, null, tint = Color.White, modifier = Modifier.size(16.dp))
                Spacer(modifier = Modifier.width(6.dp))
                Text("Unblock & Reconcile Engine", color = Color.White, fontWeight = FontWeight.Black, fontSize = 12.sp)
            }
        }
    }
}

// ─── Margin Notice ────────────────────────────────────────────────────────────

@Composable
fun MarginNoticeCard(state: TradingUiState, freeCash: Double) {
    Card(
        modifier = Modifier
            .fillMaxWidth()
            .border(1.dp, CyanAccent.copy(0.4f), RoundedCornerShape(14.dp)),
        colors = CardDefaults.cardColors(containerColor = CyanDim),
        shape  = RoundedCornerShape(14.dp)
    ) {
        Row(
            modifier = Modifier.padding(12.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            Icon(Icons.Default.Info, null, tint = CyanAccent, modifier = Modifier.size(20.dp))
            Spacer(modifier = Modifier.width(10.dp))
            Column {
                Text(
                    text       = "Margin Locked ($${String.format("%,.2f", state.account?.marginUsed ?: 0.0)})",
                    color      = CyanAccent,
                    fontSize   = 12.sp,
                    fontWeight = FontWeight.Bold
                )
                Text(
                    text    = "Free cash $${String.format("%,.2f", freeCash)} — close a position to release margin for new scalps.",
                    color   = TextSecondary,
                    fontSize = 11.sp
                )
            }
        }
    }
}

// ─── Engine Controls ──────────────────────────────────────────────────────────

@Composable
fun EngineStatusStrip(
    state: TradingUiState,
    onToggleAutoTrading: () -> Unit,
    onPunchScalp: (String, String, Double) -> Unit
) {
    val autoActive = state.status?.autoExecution == true
    var selectedSide by remember { mutableStateOf("buy") }
    val isBuy = selectedSide == "buy"

    Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {

        // Auto-Pilot Toggle Card
        Card(
            modifier = Modifier
                .fillMaxWidth()
                .border(
                    1.dp,
                    if (autoActive) EmeraldPrimary.copy(0.5f) else BorderColor,
                    RoundedCornerShape(18.dp)
                ),
            colors = CardDefaults.cardColors(
                containerColor = if (autoActive) EmeraldPrimary.copy(0.07f) else DarkCardSurface
            ),
            shape = RoundedCornerShape(18.dp)
        ) {
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 16.dp, vertical = 13.dp),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Column(modifier = Modifier.weight(1f)) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        if (autoActive) PulsingLiveDot(EmeraldPrimary)
                        else Box(Modifier.size(7.dp).clip(CircleShape).background(TextMuted))
                        Spacer(modifier = Modifier.width(7.dp))
                        Text(
                            text          = if (autoActive) "AUTO-PILOT RUNNING" else "AUTO-PILOT STANDBY",
                            color         = if (autoActive) EmeraldPrimary else TextMuted,
                            fontSize      = 10.sp,
                            fontWeight    = FontWeight.Black,
                            letterSpacing = 0.6.sp
                        )
                    }
                    Spacer(modifier = Modifier.height(2.dp))
                    Text(
                        text       = "Research → Entry → Auto-Exit",
                        color      = TextPrimary,
                        fontSize   = 14.sp,
                        fontWeight = FontWeight.ExtraBold
                    )
                    Text(
                        text    = "500ms scan • Breakeven lock @ +$0.50 • Target ≥ $1.00",
                        color   = TextSecondary,
                        fontSize = 11.sp
                    )
                }
                Switch(
                    checked  = autoActive,
                    onCheckedChange = { onToggleAutoTrading() },
                    colors   = SwitchDefaults.colors(
                        checkedThumbColor   = EmeraldPrimary,
                        checkedTrackColor   = EmeraldPrimary.copy(0.30f),
                        uncheckedThumbColor = TextMuted,
                        uncheckedTrackColor = DarkElevatedSurface
                    )
                )
            }
        }

        // Info Badge Row
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.spacedBy(8.dp)
        ) {
            InfoBadge("Target",   "+$1.00+ USDT", ProfitGreen,   Modifier.weight(1f))
            InfoBadge("Leverage", "4× @ $25",     CyanAccent,    Modifier.weight(1f))
            InfoBadge("Breakeven","$0 Risk",       AmberWarning,  Modifier.weight(1f))
        }

        // Side Toggle + Label
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically
        ) {
            Text("⚡ 1-Tap Scalp", color = TextPrimary, fontSize = 13.sp, fontWeight = FontWeight.ExtraBold)

            Row(
                modifier = Modifier
                    .clip(RoundedCornerShape(10.dp))
                    .background(DarkElevatedSurface)
                    .border(1.dp, BorderColor, RoundedCornerShape(10.dp))
                    .padding(3.dp)
            ) {
                listOf("buy" to "BUY", "sell" to "SELL").forEach { (id, label) ->
                    val isMe = selectedSide == id
                    Box(
                        modifier = Modifier
                            .clip(RoundedCornerShape(8.dp))
                            .background(
                                if (isMe) {
                                    if (id == "buy") EmeraldPrimary else LossRed
                                } else Color.Transparent
                            )
                            .clickable { selectedSide = id }
                            .padding(horizontal = 10.dp, vertical = 5.dp)
                    ) {
                        Text(
                            text       = label,
                            color      = if (isMe) Color.Black else TextSecondary,
                            fontSize   = 11.sp,
                            fontWeight = FontWeight.Black
                        )
                    }
                }
            }
        }

        // Quick Scalp Buttons
        Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            QuickScalpButton("XRP",  "B-XRP_USDT",  15.0,  isBuy, onPunchScalp, Modifier.weight(1f))
            QuickScalpButton("DOGE", "B-DOGE_USDT", 100.0, isBuy, onPunchScalp, Modifier.weight(1f))
        }
        Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            QuickScalpButton("SOL",  "B-SOL_USDT",  1.0,   isBuy, onPunchScalp, Modifier.weight(1f))
            QuickScalpButton("ETH",  "B-ETH_USDT",  0.01,  isBuy, onPunchScalp, Modifier.weight(1f))
        }
    }
}

@Composable
fun QuickScalpButton(
    label: String,
    symbol: String,
    qty: Double,
    isBuy: Boolean,
    onPunch: (String, String, Double) -> Unit,
    modifier: Modifier = Modifier
) {
    val side = if (isBuy) "buy" else "sell"
    val color = if (isBuy) EmeraldPrimary else LossRed
    Button(
        onClick = { onPunch(symbol, side, qty) },
        colors  = ButtonDefaults.buttonColors(containerColor = color.copy(alpha = 0.12f)),
        shape   = RoundedCornerShape(12.dp),
        modifier = modifier.border(1.dp, color, RoundedCornerShape(12.dp)),
        contentPadding = PaddingValues(horizontal = 8.dp, vertical = 10.dp)
    ) {
        Text(
            text       = "${if (isBuy) "▲" else "▼"} $label 4×",
            color      = color,
            fontSize   = 12.sp,
            fontWeight = FontWeight.Black
        )
    }
}

@Composable
fun InfoBadge(label: String, value: String, color: Color, modifier: Modifier = Modifier) {
    Column(
        modifier = modifier
            .clip(RoundedCornerShape(12.dp))
            .background(color.copy(0.09f))
            .border(1.dp, color.copy(0.25f), RoundedCornerShape(12.dp))
            .padding(vertical = 8.dp, horizontal = 6.dp),
        horizontalAlignment = Alignment.CenterHorizontally
    ) {
        Text(label, color = TextMuted, fontSize = 9.sp, fontWeight = FontWeight.Bold)
        Spacer(modifier = Modifier.height(2.dp))
        Text(value,  color = color,     fontSize = 11.sp, fontWeight = FontWeight.Black)
    }
}

// ─── Empty State ──────────────────────────────────────────────────────────────

@Composable
fun EmptyPositionsCard() {
    Card(
        modifier = Modifier.fillMaxWidth(),
        colors   = CardDefaults.cardColors(containerColor = DarkCardSurface),
        shape    = RoundedCornerShape(18.dp)
    ) {
        Column(
            modifier = Modifier.fillMaxWidth().padding(36.dp),
            horizontalAlignment = Alignment.CenterHorizontally
        ) {
            Icon(Icons.Default.Shield, null, tint = EmeraldPrimary.copy(0.4f), modifier = Modifier.size(48.dp))
            Spacer(modifier = Modifier.height(14.dp))
            Text("No open positions", color = TextSecondary, fontSize = 15.sp, fontWeight = FontWeight.Bold)
            Spacer(modifier = Modifier.height(4.dp))
            Text(
                text      = "Auto-engine is scanning 499 markets every 60s for high-probability 4× scalps",
                color     = TextMuted,
                fontSize  = 12.sp,
                textAlign = androidx.compose.ui.text.style.TextAlign.Center
            )
        }
    }
}

// ─── Position Card ────────────────────────────────────────────────────────────

@Composable
fun PositionCard(
    position: PositionItem,
    onExit: (String, String) -> Unit
) {
    val isLong  = position.direction.lowercase().let { it == "long" || it == "buy" }
    val pnl     = position.unrealizedPnl
    val isProfit= pnl >= 0
    val entry   = position.averagePrice
    val mark    = position.markPrice ?: entry
    val diffPct = if (entry > 0) {
        if (isLong) ((mark - entry) / entry) * 100 else ((entry - mark) / entry) * 100
    } else 0.0
    val roePct  = diffPct * (position.leverage ?: 4)
    val isBotManaged = position.botManaged == true || position.origin == "bot"
    val isBreakeven  = position.breakevenActivated == true

    val borderColor = when {
        isProfit && isBreakeven -> GoldAccent.copy(0.5f)
        isProfit                -> ProfitGreen.copy(0.4f)
        else                    -> LossRed.copy(0.35f)
    }

    val animatedPnl by animateFloatAsState(
        targetValue   = pnl.toFloat(),
        animationSpec = tween(600, easing = EaseOutQuart),
        label         = "pnl"
    )

    Card(
        modifier = Modifier
            .fillMaxWidth()
            .border(1.dp, borderColor, RoundedCornerShape(18.dp)),
        colors = CardDefaults.cardColors(containerColor = DarkCardSurface),
        shape  = RoundedCornerShape(18.dp)
    ) {
        Column(modifier = Modifier.padding(16.dp)) {

            // Top accent stripe
            Box(
                modifier = Modifier
                    .fillMaxWidth()
                    .height(3.dp)
                    .clip(RoundedCornerShape(2.dp))
                    .background(
                        Brush.horizontalGradient(
                            if (isProfit) listOf(ProfitGreen, EmeraldPrimary)
                            else listOf(LossRed, OrangeAlert)
                        )
                    )
            )

            Spacer(modifier = Modifier.height(12.dp))

            // Symbol header
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Text(
                        text       = position.pair.replace("B-", "").replace("_USDT", ""),
                        color      = TextPrimary,
                        fontSize   = 20.sp,
                        fontWeight = FontWeight.Black
                    )
                    Spacer(modifier = Modifier.width(8.dp))
                    Chip(
                        label = if (isLong) "LONG ▲" else "SHORT ▼",
                        color = if (isLong) ProfitGreen else LossRed
                    )
                    Spacer(modifier = Modifier.width(6.dp))
                    Chip(label = "${position.leverage ?: 4}×", color = CyanAccent)
                }

                // Bot / Manual badge
                if (isBotManaged) {
                    Chip(
                        label = if (isBreakeven) "🔒 Zero Risk" else "🤖 Bot",
                        color = if (isBreakeven) GoldAccent else EmeraldPrimary
                    )
                } else {
                    Chip(label = "🛡 Manual", color = VioletAccent)
                }
            }

            Spacer(modifier = Modifier.height(14.dp))

            // P&L + ROE row
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.Bottom
            ) {
                Column {
                    Text("Unrealized P&L", color = TextMuted, fontSize = 10.sp)
                    Text(
                        text       = "${if (isProfit) "+" else ""}$${String.format("%.4f", animatedPnl)} USDT",
                        color      = if (isProfit) ProfitGreenBright else LossRedBright,
                        fontSize   = 26.sp,
                        fontWeight = FontWeight.Black,
                        fontFamily = FontFamily.Monospace
                    )
                }
                Box(
                    modifier = Modifier
                        .clip(RoundedCornerShape(10.dp))
                        .background(if (isProfit) ProfitGreenBg else LossRedBg)
                        .padding(horizontal = 12.dp, vertical = 6.dp)
                ) {
                    Text(
                        text       = "${if (roePct >= 0) "+" else ""}${String.format("%.2f", roePct)}% ROE",
                        color      = if (isProfit) ProfitGreen else LossRed,
                        fontSize   = 15.sp,
                        fontWeight = FontWeight.Black,
                        fontFamily = FontFamily.Monospace
                    )
                }
            }

            Spacer(modifier = Modifier.height(14.dp))
            HorizontalDivider(color = BorderColor.copy(0.4f))
            Spacer(modifier = Modifier.height(12.dp))

            // Price grid
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween
            ) {
                PriceCell("Entry",   "$${String.format("%.5g", entry)}", TextPrimary)
                PriceCell("Current", "$${String.format("%.5g", mark)}",  CyanAccent)
                PriceCell("Target",  "$${String.format("%.5g", position.target ?: (entry * 1.018))}", ProfitGreen)
                PriceCell("Stop",    "$${String.format("%.5g", position.stop   ?: (entry * 0.990))}", LossRed)
            }

            Spacer(modifier = Modifier.height(14.dp))

            // Exit button
            Button(
                onClick = { onExit(position.exchangePositionId ?: position.positionId ?: "", position.pair) },
                colors  = ButtonDefaults.buttonColors(containerColor = LossRed.copy(0.12f)),
                shape   = RoundedCornerShape(12.dp),
                modifier = Modifier
                    .fillMaxWidth()
                    .border(1.dp, LossRed.copy(0.5f), RoundedCornerShape(12.dp)),
                contentPadding = PaddingValues(vertical = 12.dp)
            ) {
                Icon(Icons.Default.Close, null, tint = LossRed, modifier = Modifier.size(16.dp))
                Spacer(modifier = Modifier.width(6.dp))
                Text("Exit Position at Market", color = LossRed, fontSize = 12.sp, fontWeight = FontWeight.Black)
            }
        }
    }
}

// ─── Helpers ──────────────────────────────────────────────────────────────────

@Composable
fun PriceCell(label: String, value: String, valueColor: Color) {
    Column(horizontalAlignment = Alignment.CenterHorizontally) {
        Text(label, color = TextMuted, fontSize = 10.sp)
        Text(
            text       = value,
            color      = valueColor,
            fontSize   = 12.sp,
            fontWeight = FontWeight.Bold,
            fontFamily = FontFamily.Monospace,
            maxLines   = 1
        )
    }
}

@Composable
fun Chip(label: String, color: Color) {
    Box(
        modifier = Modifier
            .clip(RoundedCornerShape(6.dp))
            .background(color.copy(0.15f))
            .padding(horizontal = 6.dp, vertical = 2.dp)
    ) {
        Text(label, color = color, fontSize = 10.sp, fontWeight = FontWeight.Bold)
    }
}

@Composable
fun PulsingLiveDot(color: Color) {
    val inf = rememberInfiniteTransition(label = "dot")
    val scale by inf.animateFloat(
        0.6f, 1.4f,
        infiniteRepeatable(tween(600, easing = FastOutSlowInEasing), RepeatMode.Reverse),
        label = "ds"
    )
    Box(
        modifier = Modifier
            .size(8.dp)
            .scale(scale)
            .clip(CircleShape)
            .background(color)
    )
}
