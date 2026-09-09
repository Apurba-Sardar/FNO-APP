package com.fno.trading.ui.theme

import android.app.Activity
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Typography
import androidx.compose.material3.darkColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.SideEffect
import androidx.compose.ui.graphics.toArgb
import androidx.compose.ui.platform.LocalView
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.Font
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.sp
import androidx.core.view.WindowCompat

private val DarkColorScheme = darkColorScheme(
    primary          = EmeraldPrimary,
    secondary        = CyanAccent,
    tertiary         = AmberWarning,
    background       = AmoledBackground,
    surface          = DarkCardSurface,
    surfaceVariant   = DarkElevatedSurface,
    onPrimary        = AmoledBackground,
    onSecondary      = AmoledBackground,
    onBackground     = TextPrimary,
    onSurface        = TextPrimary,
    onSurfaceVariant = TextSecondary,
    error            = LossRed,
    onError          = TextPrimary
)

private val AppTypography = Typography(
    displayLarge  = TextStyle(fontWeight = FontWeight.Black,  fontSize = 40.sp, letterSpacing = (-1).sp, color = TextPrimary),
    displayMedium = TextStyle(fontWeight = FontWeight.Black,  fontSize = 32.sp, letterSpacing = (-0.5).sp, color = TextPrimary),
    headlineLarge = TextStyle(fontWeight = FontWeight.ExtraBold, fontSize = 24.sp, color = TextPrimary),
    headlineMedium= TextStyle(fontWeight = FontWeight.Bold,   fontSize = 20.sp, color = TextPrimary),
    titleLarge    = TextStyle(fontWeight = FontWeight.Bold,   fontSize = 18.sp, color = TextPrimary),
    titleMedium   = TextStyle(fontWeight = FontWeight.SemiBold, fontSize = 15.sp, color = TextPrimary),
    bodyLarge     = TextStyle(fontWeight = FontWeight.Normal, fontSize = 14.sp, color = TextSecondary),
    bodyMedium    = TextStyle(fontWeight = FontWeight.Normal, fontSize = 12.sp, color = TextSecondary),
    labelLarge    = TextStyle(fontWeight = FontWeight.Bold,   fontSize = 12.sp, letterSpacing = 0.5.sp),
    labelMedium   = TextStyle(fontWeight = FontWeight.Medium, fontSize = 11.sp, letterSpacing = 0.4.sp),
    labelSmall    = TextStyle(fontWeight = FontWeight.Medium, fontSize = 10.sp, letterSpacing = 0.3.sp, color = TextMuted)
)

@Composable
fun FnoTradingTheme(content: @Composable () -> Unit) {
    val view = LocalView.current
    if (!view.isInEditMode) {
        SideEffect {
            val window = (view.context as Activity).window
            window.statusBarColor = AmoledBackground.toArgb()
            window.navigationBarColor = DarkCardSurface.toArgb()
            WindowCompat.getInsetsController(window, view).isAppearanceLightStatusBars = false
            WindowCompat.getInsetsController(window, view).isAppearanceLightNavigationBars = false
        }
    }

    MaterialTheme(
        colorScheme = DarkColorScheme,
        typography  = AppTypography,
        content     = content
    )
}
