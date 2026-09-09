package com.fno.trading.ui.screens

import androidx.compose.animation.AnimatedContent
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material.icons.outlined.ReceiptLong
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.fno.trading.data.model.OrderItem
import com.fno.trading.ui.TradingViewModel
import com.fno.trading.ui.theme.*

@Composable
fun OrderHistoryScreen(
    viewModel: TradingViewModel,
    modifier: Modifier = Modifier
) {
    val state by viewModel.uiState.collectAsState()
    val orders = state.orders

    LazyColumn(
        modifier = modifier
            .fillMaxSize()
            .background(AmoledBackground)
            .padding(horizontal = 14.dp),
        verticalArrangement = Arrangement.spacedBy(10.dp),
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
                        text       = "Execution Log",
                        color      = TextPrimary,
                        fontSize   = 22.sp,
                        fontWeight = FontWeight.Black
                    )
                    Text(
                        text    = "Real-time order history synced with CoinDCX (IST)",
                        color   = TextSecondary,
                        fontSize = 12.sp
                    )
                }

                Box(
                    modifier = Modifier
                        .clip(RoundedCornerShape(10.dp))
                        .background(DarkElevatedSurface)
                        .border(1.dp, BorderColor, RoundedCornerShape(10.dp))
                        .padding(horizontal = 10.dp, vertical = 6.dp)
                ) {
                    Text(
                        text       = "${orders.size} orders",
                        color      = TextSecondary,
                        fontSize   = 11.sp,
                        fontWeight = FontWeight.Bold
                    )
                }
            }
        }

        // ── Summary Stats Row ─────────────────────────────────────────
        if (orders.isNotEmpty()) {
            item {
                val buyCount  = orders.count { it.side.lowercase() == "buy" }
                val sellCount = orders.size - buyCount

                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(8.dp)
                ) {
                    StatSummaryChip("Total",  "${orders.size}",   TextSecondary, Modifier.weight(1f))
                    StatSummaryChip("Buys",   "$buyCount",        ProfitGreen,   Modifier.weight(1f))
                    StatSummaryChip("Sells",  "$sellCount",       LossRed,       Modifier.weight(1f))
                    StatSummaryChip("Filled", "${orders.count { it.status.lowercase() == "filled" }}", EmeraldPrimary, Modifier.weight(1f))
                }
            }
        }

        // ── Empty State ───────────────────────────────────────────────
        if (orders.isEmpty()) {
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
                        Icon(
                            imageVector = Icons.Outlined.ReceiptLong,
                            contentDescription = null,
                            tint   = TextMuted,
                            modifier = Modifier.size(48.dp)
                        )
                        Spacer(modifier = Modifier.height(14.dp))
                        Text("No orders yet", color = TextSecondary, fontSize = 15.sp, fontWeight = FontWeight.Bold)
                        Spacer(modifier = Modifier.height(4.dp))
                        Text(
                            "Orders will appear here as the auto-engine executes scalps",
                            color     = TextMuted,
                            fontSize  = 12.sp,
                            textAlign = androidx.compose.ui.text.style.TextAlign.Center
                        )
                    }
                }
            }
        } else {
            itemsIndexed(orders, key = { _, ord -> "${ord.orderId}_${ord.pair}_${ord.createdAt}" }) { idx, ord ->
                OrderCard(order = ord, index = idx)
            }
        }
    }
}

@Composable
fun StatSummaryChip(label: String, value: String, valueColor: androidx.compose.ui.graphics.Color, modifier: Modifier = Modifier) {
    Column(
        modifier = modifier
            .clip(RoundedCornerShape(12.dp))
            .background(DarkCardSurface)
            .border(1.dp, BorderColor, RoundedCornerShape(12.dp))
            .padding(vertical = 10.dp),
        horizontalAlignment = Alignment.CenterHorizontally
    ) {
        Text(value, color = valueColor, fontSize = 18.sp, fontWeight = FontWeight.Black, fontFamily = FontFamily.Monospace)
        Text(label, color = TextMuted,  fontSize = 10.sp, fontWeight = FontWeight.Medium)
    }
}

@Composable
fun OrderCard(order: OrderItem, index: Int = 0) {
    val isBuy    = order.side.lowercase() == "buy"
    val isFilled = order.status.lowercase() in listOf("filled", "executed", "completed")
    val isCancelled = order.status.lowercase() in listOf("cancelled", "canceled", "rejected")

    val statusColor = when {
        isFilled    -> EmeraldPrimary
        isCancelled -> LossRed
        else        -> AmberWarning
    }

    val sideColor = if (isBuy) ProfitGreen else LossRed

    Card(
        modifier = Modifier
            .fillMaxWidth()
            .border(1.dp, sideColor.copy(0.20f), RoundedCornerShape(16.dp)),
        colors = CardDefaults.cardColors(containerColor = DarkCardSurface),
        shape  = RoundedCornerShape(16.dp)
    ) {
        Row(modifier = Modifier.fillMaxWidth()) {
            // Left color stripe
            Box(
                modifier = Modifier
                    .width(4.dp)
                    .fillMaxHeight()
                    .background(
                        Brush.verticalGradient(
                            listOf(sideColor, sideColor.copy(0.3f))
                        )
                    )
            )

            Column(modifier = Modifier.padding(start = 14.dp, top = 14.dp, end = 14.dp, bottom = 14.dp).weight(1f)) {

                // Top Row
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Row(
                        verticalAlignment = Alignment.CenterVertically,
                        horizontalArrangement = Arrangement.spacedBy(8.dp)
                    ) {
                        // Order index circle
                        Box(
                            modifier = Modifier
                                .size(26.dp)
                                .clip(CircleShape)
                                .background(DarkElevatedSurface)
                                .border(1.dp, BorderColor, CircleShape),
                            contentAlignment = Alignment.Center
                        ) {
                            Text(
                                text       = "${index + 1}",
                                color      = TextMuted,
                                fontSize   = 9.sp,
                                fontWeight = FontWeight.Bold
                            )
                        }

                        Text(
                            text       = order.pair.replace("B-", "").replace("_USDT", ""),
                            color      = TextPrimary,
                            fontSize   = 17.sp,
                            fontWeight = FontWeight.Black
                        )

                        // Side badge
                        Box(
                            modifier = Modifier
                                .clip(RoundedCornerShape(6.dp))
                                .background(sideColor.copy(0.14f))
                                .padding(horizontal = 6.dp, vertical = 2.dp)
                        ) {
                            Text(
                                text       = if (isBuy) "▲ BUY" else "▼ SELL",
                                color      = sideColor,
                                fontSize   = 10.sp,
                                fontWeight = FontWeight.Black
                            )
                        }
                    }

                    // Status badge
                    Box(
                        modifier = Modifier
                            .clip(RoundedCornerShape(6.dp))
                            .background(statusColor.copy(0.13f))
                            .border(1.dp, statusColor.copy(0.35f), RoundedCornerShape(6.dp))
                            .padding(horizontal = 8.dp, vertical = 3.dp)
                    ) {
                        Text(
                            text       = order.status.uppercase(),
                            color      = statusColor,
                            fontSize   = 10.sp,
                            fontWeight = FontWeight.Black
                        )
                    }
                }

                Spacer(modifier = Modifier.height(10.dp))

                HorizontalDivider(color = BorderColor.copy(0.3f))
                Spacer(modifier = Modifier.height(10.dp))

                // Details grid
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween
                ) {
                    OrderDetailCell("Price",    "$${order.price} USDT", TextPrimary)
                    OrderDetailCell("Filled",   order.filledQuantity,   CyanAccent)
                    OrderDetailCell("Type",     order.orderType.replace("_"," ").uppercase(), AmberWarning)
                }

                // Optional: timestamp (if not null)
                if (!order.timestamp.isNullOrBlank()) {
                    Spacer(modifier = Modifier.height(8.dp))
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Icon(Icons.Default.AccessTime, null, tint = TextMuted, modifier = Modifier.size(11.dp))
                        Spacer(modifier = Modifier.width(4.dp))
                        Text(
                            text    = order.timestamp,
                            color   = TextMuted,
                            fontSize = 10.sp,
                            fontFamily = FontFamily.Monospace
                        )
                    }
                }
            }
        }
    }
}

@Composable
fun OrderDetailCell(label: String, value: String, valueColor: androidx.compose.ui.graphics.Color) {
    Column {
        Text(label, color = TextMuted, fontSize = 10.sp)
        Text(value, color = valueColor, fontSize = 12.sp, fontWeight = FontWeight.Bold, fontFamily = FontFamily.Monospace)
    }
}
