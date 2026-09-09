package com.fno.trading.ui.screens

import android.annotation.SuppressLint
import android.graphics.Bitmap
import android.view.ViewGroup
import android.webkit.WebChromeClient
import android.webkit.WebResourceError
import android.webkit.WebResourceRequest
import android.webkit.WebSettings
import android.webkit.WebView
import android.webkit.WebViewClient
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material.icons.filled.TrendingUp
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.viewinterop.AndroidView
import com.fno.trading.ui.theme.*

private data class CoinInfo(val symbol: String, val label: String, val emoji: String)

@SuppressLint("SetJavaScriptEnabled")
@Composable
fun ChartScreen(modifier: Modifier = Modifier) {
    var selectedCoin     by remember { mutableStateOf("XRPUSDT") }
    var selectedInterval by remember { mutableStateOf("15") }
    var isLoading        by remember { mutableStateOf(true) }
    var reloadTrigger    by remember { mutableIntStateOf(0) }

    val coins = listOf(
        CoinInfo("XRPUSDT",   "XRP",   "💧"),
        CoinInfo("DOGEUSDT",  "DOGE",  "🐶"),
        CoinInfo("BTCUSDT",   "BTC",   "₿"),
        CoinInfo("ETHUSDT",   "ETH",   "♦"),
        CoinInfo("SOLUSDT",   "SOL",   "☀"),
        CoinInfo("ADAUSDT",   "ADA",   "🔵"),
        CoinInfo("BNBUSDT",   "BNB",   "🟡"),
        CoinInfo("LTCUSDT",   "LTC",   "⚡"),
        CoinInfo("MATICUSDT", "MATIC", "🔺"),
        CoinInfo("TRXUSDT",   "TRX",   "🔴")
    )

    val intervals = listOf(
        "1" to "1m", "5" to "5m", "15" to "15m",
        "60" to "1H", "240" to "4H", "D" to "1D"
    )

    Column(
        modifier = modifier
            .fillMaxSize()
            .background(AmoledBackground)
            .padding(top = 14.dp)
    ) {
        // ── Header ─────────────────────────────────────────────────────
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 14.dp),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically
        ) {
            Column {
                Text(
                    text       = "Live Charts",
                    color      = TextPrimary,
                    fontSize   = 22.sp,
                    fontWeight = FontWeight.Black
                )
                Text(
                    text    = "TradingView • Interactive Candlestick + Indicators",
                    color   = TextSecondary,
                    fontSize = 11.sp
                )
            }

            Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                // Selected coin pill
                Box(
                    modifier = Modifier
                        .clip(RoundedCornerShape(10.dp))
                        .background(
                            Brush.horizontalGradient(listOf(EmeraldPrimary.copy(0.2f), CyanAccent.copy(0.1f)))
                        )
                        .border(1.dp, EmeraldPrimary.copy(0.5f), RoundedCornerShape(10.dp))
                        .padding(horizontal = 10.dp, vertical = 6.dp)
                ) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Icon(Icons.Default.TrendingUp, null, tint = EmeraldPrimary, modifier = Modifier.size(14.dp))
                        Spacer(modifier = Modifier.width(4.dp))
                        Text(
                            text       = selectedCoin.replace("USDT", ""),
                            color      = EmeraldPrimary,
                            fontSize   = 12.sp,
                            fontWeight = FontWeight.Black
                        )
                    }
                }

                IconButton(
                    onClick  = { reloadTrigger++ },
                    modifier = Modifier
                        .size(36.dp)
                        .clip(RoundedCornerShape(10.dp))
                        .background(DarkElevatedSurface)
                        .border(1.dp, BorderColor, RoundedCornerShape(10.dp))
                ) {
                    Icon(
                        imageVector = Icons.Default.Refresh,
                        contentDescription = "Reload",
                        tint     = CyanAccent,
                        modifier = Modifier.size(18.dp)
                    )
                }
            }
        }

        Spacer(modifier = Modifier.height(12.dp))

        // ── Coin Selector Row ──────────────────────────────────────────
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .horizontalScroll(rememberScrollState())
                .padding(horizontal = 14.dp),
            horizontalArrangement = Arrangement.spacedBy(8.dp)
        ) {
            coins.forEach { coin ->
                val isSelected = coin.symbol == selectedCoin
                Button(
                    onClick = { selectedCoin = coin.symbol },
                    colors  = ButtonDefaults.buttonColors(
                        containerColor = if (isSelected) EmeraldPrimary.copy(0.18f) else DarkElevatedSurface
                    ),
                    shape   = RoundedCornerShape(12.dp),
                    modifier = Modifier.border(
                        1.dp,
                        if (isSelected) EmeraldPrimary else BorderColor.copy(0.5f),
                        RoundedCornerShape(12.dp)
                    ),
                    contentPadding = PaddingValues(horizontal = 13.dp, vertical = 8.dp)
                ) {
                    Text(
                        text       = "${coin.emoji} ${coin.label}",
                        color      = if (isSelected) EmeraldPrimary else TextSecondary,
                        fontSize   = 12.sp,
                        fontWeight = if (isSelected) FontWeight.Black else FontWeight.Medium
                    )
                }
            }
        }

        Spacer(modifier = Modifier.height(8.dp))

        // ── Interval Selector ──────────────────────────────────────────
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 14.dp),
            horizontalArrangement = Arrangement.spacedBy(6.dp)
        ) {
            intervals.forEach { (value, label) ->
                val isSelected = value == selectedInterval
                Button(
                    onClick  = { selectedInterval = value },
                    colors   = ButtonDefaults.buttonColors(
                        containerColor = if (isSelected) CyanAccent.copy(0.18f) else DarkElevatedSurface.copy(0.5f)
                    ),
                    shape    = RoundedCornerShape(9.dp),
                    modifier = Modifier
                        .weight(1f)
                        .border(
                            1.dp,
                            if (isSelected) CyanAccent else BorderColor.copy(0.4f),
                            RoundedCornerShape(9.dp)
                        ),
                    contentPadding = PaddingValues(horizontal = 2.dp, vertical = 7.dp)
                ) {
                    Text(
                        text       = label,
                        color      = if (isSelected) CyanAccent else TextMuted,
                        fontSize   = 11.sp,
                        fontWeight = if (isSelected) FontWeight.Black else FontWeight.Normal
                    )
                }
            }
        }

        Spacer(modifier = Modifier.height(10.dp))

        // ── Chart WebView ──────────────────────────────────────────────
        Card(
            modifier  = Modifier
                .fillMaxWidth()
                .weight(1f)
                .padding(horizontal = 14.dp)
                .border(
                    1.dp,
                    Brush.linearGradient(listOf(EmeraldPrimary.copy(0.3f), CyanAccent.copy(0.15f), BorderColor.copy(0.2f))),
                    RoundedCornerShape(18.dp)
                ),
            shape  = RoundedCornerShape(18.dp),
            colors = CardDefaults.cardColors(containerColor = DarkCardSurface)
        ) {
            Box(modifier = Modifier.fillMaxSize()) {
                AndroidView(
                    factory = { context ->
                        WebView(context).apply {
                            layoutParams = ViewGroup.LayoutParams(
                                ViewGroup.LayoutParams.MATCH_PARENT,
                                ViewGroup.LayoutParams.MATCH_PARENT
                            )
                            settings.apply {
                                javaScriptEnabled     = true
                                domStorageEnabled     = true
                                databaseEnabled       = true
                                useWideViewPort       = true
                                loadWithOverviewMode  = true
                                setSupportZoom(true)
                                builtInZoomControls   = true
                                displayZoomControls   = false
                                allowFileAccess       = true
                                allowContentAccess    = true
                                cacheMode             = WebSettings.LOAD_DEFAULT
                            }
                            webChromeClient = WebChromeClient()
                            webViewClient   = object : WebViewClient() {
                                override fun onPageStarted(view: WebView?, url: String?, favicon: Bitmap?) { isLoading = true }
                                override fun onPageFinished(view: WebView?, url: String?)                  { isLoading = false }
                                override fun onReceivedError(view: WebView?, request: WebResourceRequest?, error: WebResourceError?) { isLoading = false }
                            }
                            setBackgroundColor(0xFF020812.toInt())
                        }
                    },
                    update = { webView ->
                        val url      = buildTradingViewUrl(selectedCoin, selectedInterval)
                        val cacheKey = "$url#$reloadTrigger"
                        if (webView.tag != cacheKey) {
                            webView.tag = cacheKey
                            webView.loadUrl(url)
                        }
                    },
                    modifier = Modifier.fillMaxSize()
                )

                // Loading overlay
                if (isLoading) {
                    Box(
                        modifier = Modifier
                            .fillMaxSize()
                            .background(DarkCardSurface.copy(0.85f)),
                        contentAlignment = Alignment.Center
                    ) {
                        Column(horizontalAlignment = Alignment.CenterHorizontally) {
                            CircularProgressIndicator(
                                color       = EmeraldPrimary,
                                strokeWidth = 3.dp,
                                modifier    = Modifier.size(36.dp)
                            )
                            Spacer(modifier = Modifier.height(12.dp))
                            Text(
                                text       = "Loading ${selectedCoin.replace("USDT", "")} Chart...",
                                color      = TextSecondary,
                                fontSize   = 13.sp,
                                fontWeight = FontWeight.Bold
                            )
                            Text("${selectedInterval}m • TradingView Dark", color = TextMuted, fontSize = 10.sp)
                        }
                    }
                }
            }
        }

        // ── Tip Row ────────────────────────────────────────────────────
        Spacer(modifier = Modifier.height(8.dp))
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 14.dp)
                .clip(RoundedCornerShape(10.dp))
                .background(DarkElevatedSurface.copy(0.4f))
                .padding(horizontal = 12.dp, vertical = 8.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            Text(
                text      = "💡 Pinch to zoom • Drag to scroll history • Tap candle for OHLCV data",
                color     = TextMuted,
                fontSize  = 10.sp,
                textAlign = TextAlign.Center,
                modifier  = Modifier.fillMaxWidth()
            )
        }

        Spacer(modifier = Modifier.height(80.dp))
    }
}

private fun buildTradingViewUrl(symbol: String, interval: String): String {
    return "https://s.tradingview.com/widgetembed/?frameElementId=tradingview_widget" +
            "&symbol=BINANCE:${symbol}" +
            "&interval=${interval}" +
            "&hidesidetoolbar=0" +
            "&symboledit=1" +
            "&saveimage=1" +
            "&toolbarbg=020812" +
            "&theme=dark" +
            "&style=1" +
            "&timezone=Asia%2FKolkata" +
            "&studies=RSI%40tv-basicstudies%2CMACD%40tv-basicstudies"
}
