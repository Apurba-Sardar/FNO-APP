package com.fno.trading

import android.Manifest
import android.content.pm.PackageManager
import android.os.Build
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.activity.viewModels
import androidx.compose.animation.AnimatedContent
import androidx.compose.animation.core.*
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.*
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
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.core.content.ContextCompat
import com.fno.trading.ui.TradingViewModel
import com.fno.trading.ui.screens.ChartScreen
import com.fno.trading.ui.screens.LivePortfolioScreen
import com.fno.trading.ui.screens.OpportunitiesScreen
import com.fno.trading.ui.screens.OrderHistoryScreen
import com.fno.trading.ui.theme.*

data class NavItem(
    val screen: Screen,
    val selectedIcon: ImageVector,
    val unselectedIcon: ImageVector,
    val label: String,
    val badgeCount: Int = 0
)

enum class Screen { LIVE, CHARTS, SETUPS, ORDERS }

class MainActivity : ComponentActivity() {

    private val viewModel: TradingViewModel by viewModels()

    private val requestNotificationPermission =
        registerForActivityResult(ActivityResultContracts.RequestPermission()) { }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            if (ContextCompat.checkSelfPermission(this, Manifest.permission.POST_NOTIFICATIONS)
                != PackageManager.PERMISSION_GRANTED
            ) {
                requestNotificationPermission.launch(Manifest.permission.POST_NOTIFICATIONS)
            }
        }

        setContent {
            FnoTradingTheme {
                FnoTradingApp(viewModel)
            }
        }
    }
}

@Composable
fun FnoTradingApp(viewModel: TradingViewModel) {
    var currentScreen by remember { mutableStateOf(Screen.LIVE) }
    val state by viewModel.uiState.collectAsState()

    val openCount = state.positions.count { it.status == "open" }
    val isAutoOn  = state.status?.autoExecution == true
    val hasAlert  = state.errorMessage != null || state.status?.runtimeState == "blocked"

    val navItems = listOf(
        NavItem(Screen.LIVE,   Icons.Filled.ShowChart,      Icons.Outlined.ShowChart,      "Live",   if (openCount > 0) openCount else 0),
        NavItem(Screen.CHARTS, Icons.Filled.CandlestickChart, Icons.Outlined.CandlestickChart, "Charts"),
        NavItem(Screen.SETUPS, Icons.Filled.Bolt,            Icons.Outlined.Bolt,            "Signals",state.evaluations.size.coerceAtMost(9)),
        NavItem(Screen.ORDERS, Icons.Filled.ReceiptLong,    Icons.Outlined.ReceiptLong,    "History")
    )

    Scaffold(
        containerColor = AmoledBackground,
        bottomBar = {
            PremiumBottomNav(
                navItems     = navItems,
                currentScreen = currentScreen,
                isAutoOn     = isAutoOn,
                hasAlert     = hasAlert,
                statusMsg    = state.statusMessage,
                onSelect     = { currentScreen = it }
            )
        }
    ) { inner ->
        Box(
            modifier = Modifier
                .fillMaxSize()
                .background(AmoledBackground)
                .padding(inner)
        ) {
            AnimatedContent(targetState = currentScreen, label = "screen_nav") { screen ->
                when (screen) {
                    Screen.LIVE   -> LivePortfolioScreen(viewModel = viewModel)
                    Screen.CHARTS -> ChartScreen()
                    Screen.SETUPS -> OpportunitiesScreen(viewModel = viewModel)
                    Screen.ORDERS -> OrderHistoryScreen(viewModel = viewModel)
                }
            }
        }
    }
}

@Composable
fun PremiumBottomNav(
    navItems: List<NavItem>,
    currentScreen: Screen,
    isAutoOn: Boolean,
    hasAlert: Boolean,
    statusMsg: String,
    onSelect: (Screen) -> Unit
) {
    Column(modifier = Modifier.fillMaxWidth()) {
        // ── Thin status strip ──────────────────────────────────────────
        Box(
            modifier = Modifier
                .fillMaxWidth()
                .background(
                    Brush.horizontalGradient(
                        listOf(DarkCardSurface, DarkElevatedSurface, DarkCardSurface)
                    )
                )
                .border(
                    width = 0.5.dp,
                    color = if (hasAlert) LossRed.copy(alpha = 0.6f) else BorderColor.copy(alpha = 0.5f),
                    shape = RoundedCornerShape(0.dp)
                )
                .padding(horizontal = 14.dp, vertical = 5.dp)
        ) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.SpaceBetween
            ) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    // Pulsing engine dot
                    PulsingDot(color = if (hasAlert) LossRed else if (isAutoOn) EmeraldPrimary else TextMuted)
                    Spacer(modifier = Modifier.width(6.dp))
                    Text(
                        text = if (hasAlert) "⚠ ENGINE ALERT" else if (isAutoOn) "AUTO-PILOT LIVE" else "ENGINE STANDBY",
                        color = if (hasAlert) LossRed else if (isAutoOn) EmeraldPrimary else TextMuted,
                        fontSize = 9.sp,
                        fontWeight = FontWeight.Black,
                        letterSpacing = 0.8.sp
                    )
                }
                Text(
                    text = statusMsg,
                    color = TextMuted,
                    fontSize = 9.sp,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                    modifier = Modifier.widthIn(max = 200.dp)
                )
            }
        }

        // ── Bottom Navigation Bar ──────────────────────────────────────
        NavigationBar(
            containerColor = DarkCardSurface,
            tonalElevation = 0.dp,
            modifier = Modifier.fillMaxWidth()
        ) {
            navItems.forEach { item ->
                val isSelected = currentScreen == item.screen
                NavigationBarItem(
                    selected    = isSelected,
                    onClick     = { onSelect(item.screen) },
                    icon = {
                        BadgedBox(
                            badge = {
                                if (item.badgeCount > 0) {
                                    Badge(
                                        containerColor = if (item.screen == Screen.LIVE) EmeraldPrimary else CyanAccent,
                                        contentColor   = AmoledBackground
                                    ) {
                                        Text(
                                            text       = "${item.badgeCount}",
                                            fontSize   = 8.sp,
                                            fontWeight = FontWeight.Black
                                        )
                                    }
                                }
                            }
                        ) {
                            Icon(
                                imageVector     = if (isSelected) item.selectedIcon else item.unselectedIcon,
                                contentDescription = item.label,
                                tint            = if (isSelected) EmeraldPrimary else TextMuted,
                                modifier        = Modifier.size(24.dp)
                            )
                        }
                    },
                    label = {
                        Text(
                            text       = item.label,
                            fontSize   = 10.sp,
                            fontWeight = if (isSelected) FontWeight.Bold else FontWeight.Normal,
                            color      = if (isSelected) EmeraldPrimary else TextMuted
                        )
                    },
                    colors = NavigationBarItemDefaults.colors(
                        selectedIconColor   = EmeraldPrimary,
                        selectedTextColor   = EmeraldPrimary,
                        unselectedIconColor = TextMuted,
                        unselectedTextColor = TextMuted,
                        indicatorColor      = EmeraldPrimary.copy(alpha = 0.14f)
                    )
                )
            }
        }
    }
}

@Composable
fun PulsingDot(color: Color, modifier: Modifier = Modifier) {
    val infiniteTransition = rememberInfiniteTransition(label = "pulse")
    val scale by infiniteTransition.animateFloat(
        initialValue   = 0.7f,
        targetValue    = 1.3f,
        animationSpec  = infiniteRepeatable(
            animation  = tween(700, easing = FastOutSlowInEasing),
            repeatMode = RepeatMode.Reverse
        ),
        label = "scale"
    )
    Box(
        modifier = modifier
            .size(7.dp)
            .scale(scale)
            .clip(CircleShape)
            .background(color)
    )
}
