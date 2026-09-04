package com.fno.trading.ui.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Bolt
import androidx.compose.material.icons.filled.TrendingUp
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.fno.trading.data.model.OpportunityItem
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
        verticalArrangement = Arrangement.spacedBy(14.dp)
    ) {
        item {
            Column {
                Text(
                    text = "Breakout Opportunity Radar",
                    color = TextPrimary,
                    fontSize = 20.sp,
                    fontWeight = FontWeight.Bold
                )
                Text(
                    text = "High-probability algorithmic breakout and trend pullback setups",
                    color = TextSecondary,
                    fontSize = 12.sp
                )
            }
        }

        if (state.opportunities.isEmpty()) {
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
                            text = "Scanning crypto markets...",
                            color = TextSecondary,
                            fontSize = 14.sp
                        )
                    }
                }
            }
        } else {
            items(state.opportunities) { opp ->
                OpportunityCard(
                    opp = opp,
                    onTrade = { symbol -> viewModel.punch3xScalp(symbol, "buy", 15.0) }
                )
            }
        }

        item {
            Spacer(modifier = Modifier.height(60.dp))
        }
    }
}

@Composable
fun OpportunityCard(
    opp: OpportunityItem,
    onTrade: (String) -> Unit
) {
    val isBullish = opp.direction.lowercase() == "bullish" || opp.direction.lowercase() == "long"
    val scoreInt = opp.score.toInt()

    Card(
        modifier = Modifier
            .fillMaxWidth()
            .border(1.dp, BorderColor, RoundedCornerShape(16.dp)),
        colors = CardDefaults.cardColors(containerColor = DarkCardSurface),
        shape = RoundedCornerShape(16.dp)
    ) {
        Column(modifier = Modifier.padding(16.dp)) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Text(
                        text = opp.symbol.replace("B-", "").replace("_USDT", ""),
                        color = TextPrimary,
                        fontSize = 18.sp,
                        fontWeight = FontWeight.Black
                    )
                    Spacer(modifier = Modifier.width(8.dp))
                    Box(
                        modifier = Modifier
                            .clip(RoundedCornerShape(6.dp))
                            .background(if (isBullish) ProfitGreenBg else LossRedBg)
                            .padding(horizontal = 6.dp, vertical = 2.dp)
                    ) {
                        Text(
                            text = opp.direction.uppercase(),
                            color = if (isBullish) ProfitGreen else LossRed,
                            fontSize = 10.sp,
                            fontWeight = FontWeight.Bold
                        )
                    }
                }

                // Score Badge
                Box(
                    modifier = Modifier
                        .clip(CircleShape)
                        .background(
                            if (scoreInt >= 75) EmeraldPrimary.copy(alpha = 0.2f) else DarkElevatedSurface
                        )
                        .padding(horizontal = 10.dp, vertical = 4.dp)
                ) {
                    Text(
                        text = "$scoreInt/100",
                        color = if (scoreInt >= 75) EmeraldPrimary else TextSecondary,
                        fontSize = 13.sp,
                        fontWeight = FontWeight.Bold
                    )
                }
            }

            Spacer(modifier = Modifier.height(10.dp))

            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Text(
                    text = "Tier: ${opp.tier} • Risk:Reward 1:${String.format("%.1f", opp.riskReward ?: 2.0)}",
                    color = TextSecondary,
                    fontSize = 12.sp
                )

                Button(
                    onClick = { onTrade(opp.symbol) },
                    colors = ButtonDefaults.buttonColors(containerColor = CyanAccent.copy(alpha = 0.2f)),
                    shape = RoundedCornerShape(8.dp),
                    contentPadding = PaddingValues(horizontal = 12.dp, vertical = 4.dp),
                    modifier = Modifier.border(1.dp, CyanAccent.copy(alpha = 0.5f), RoundedCornerShape(8.dp))
                ) {
                    Text(text = "Trade 3x", color = CyanAccent, fontSize = 11.sp, fontWeight = FontWeight.Bold)
                }
            }
        }
    }
}
