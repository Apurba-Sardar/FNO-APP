package com.fno.trading

import android.Manifest
import android.content.pm.PackageManager
import android.os.Build
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.activity.viewModels
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.core.content.ContextCompat
import com.fno.trading.ui.TradingViewModel
import com.fno.trading.ui.screens.ChartScreen
import com.fno.trading.ui.screens.LivePortfolioScreen
import com.fno.trading.ui.screens.OpportunitiesScreen
import com.fno.trading.ui.screens.OrderHistoryScreen
import com.fno.trading.ui.theme.AmoledBackground
import com.fno.trading.ui.theme.CyanAccent
import com.fno.trading.ui.theme.DarkCardSurface
import com.fno.trading.ui.theme.EmeraldPrimary
import com.fno.trading.ui.theme.FnoTradingTheme
import com.fno.trading.ui.theme.TextMuted
import com.fno.trading.ui.theme.TextPrimary

enum class Screen(val title: String, val icon: ImageVector) {
    LIVE("Live", Icons.Default.ShowChart),
    CHARTS("Charts", Icons.Default.CandlestickChart),
    SETUPS("Setups", Icons.Default.Bolt),
    ORDERS("Orders", Icons.Default.ReceiptLong)
}

class MainActivity : ComponentActivity() {

    private val viewModel: TradingViewModel by viewModels()

    private val requestNotificationPermission =
        registerForActivityResult(ActivityResultContracts.RequestPermission()) { isGranted ->
            // Permission granted or denied
        }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        // Request notification permission for S24 Ultra (Android 13+)
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            if (ContextCompat.checkSelfPermission(
                    this,
                    Manifest.permission.POST_NOTIFICATIONS
                ) != PackageManager.PERMISSION_GRANTED
            ) {
                requestNotificationPermission.launch(Manifest.permission.POST_NOTIFICATIONS)
            }
        }

        setContent {
            FnoTradingTheme {
                var currentScreen by remember { mutableStateOf(Screen.LIVE) }

                Scaffold(
                    bottomBar = {
                        NavigationBar(
                            containerColor = DarkCardSurface,
                            tonalElevation = 8.dp
                        ) {
                            Screen.values().forEach { screen ->
                                val isSelected = currentScreen == screen
                                NavigationBarItem(
                                    selected = isSelected,
                                    onClick = { currentScreen = screen },
                                    icon = {
                                        Icon(
                                            imageVector = screen.icon,
                                            contentDescription = screen.title,
                                            tint = if (isSelected) EmeraldPrimary else TextMuted
                                        )
                                    },
                                    label = {
                                        Text(
                                            text = screen.title,
                                            fontSize = 11.sp,
                                            color = if (isSelected) EmeraldPrimary else TextMuted
                                        )
                                    },
                                    colors = NavigationBarItemDefaults.colors(
                                        indicatorColor = EmeraldPrimary.copy(alpha = 0.15f)
                                    )
                                )
                            }
                        }
                    }
                ) { innerPadding ->
                    Box(
                        modifier = Modifier
                            .fillMaxSize()
                            .background(AmoledBackground)
                            .padding(innerPadding)
                    ) {
                        when (currentScreen) {
                            Screen.LIVE -> LivePortfolioScreen(viewModel = viewModel)
                            Screen.CHARTS -> ChartScreen()
                            Screen.SETUPS -> OpportunitiesScreen(viewModel = viewModel)
                            Screen.ORDERS -> OrderHistoryScreen(viewModel = viewModel)
                        }
                    }
                }
            }
        }
    }
}
