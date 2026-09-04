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
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.viewinterop.AndroidView
import com.fno.trading.ui.theme.*

@SuppressLint("SetJavaScriptEnabled")
@Composable
fun ChartScreen(
    modifier: Modifier = Modifier
) {
    var selectedSymbol by remember { mutableStateOf("XRPUSDT") }
    var selectedInterval by remember { mutableStateOf("15") }
    var isLoading by remember { mutableStateOf(true) }
    var reloadTrigger by remember { mutableIntStateOf(0) }

    val symbols = listOf("XRPUSDT", "DOGEUSDT", "BTCUSDT", "SOLUSDT", "ETHUSDT")
    val intervals = listOf(
        "5" to "5m",
        "15" to "15m",
        "60" to "1h",
        "240" to "4h",
        "D" to "1D"
    )

    Column(
        modifier = modifier
            .fillMaxSize()
            .background(AmoledBackground)
            .padding(16.dp)
    ) {
        // Top Header
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically
        ) {
            Column {
                Text(
                    text = "Live TradingView Chart",
                    color = TextPrimary,
                    fontSize = 18.sp,
                    fontWeight = FontWeight.Bold
                )
                Text(
                    text = "Interactive Candlesticks, RSI & Technicals",
                    color = TextSecondary,
                    fontSize = 11.sp
                )
            }

            IconButton(
                onClick = { reloadTrigger++ },
                modifier = Modifier
                    .size(36.dp)
                    .clip(RoundedCornerShape(8.dp))
                    .background(DarkElevatedSurface)
            ) {
                Icon(
                    imageVector = Icons.Default.Refresh,
                    contentDescription = "Reload Chart",
                    tint = CyanAccent,
                    modifier = Modifier.size(18.dp)
                )
            }
        }

        Spacer(modifier = Modifier.height(10.dp))

        // Symbol Selector Chips
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .horizontalScroll(rememberScrollState()),
            horizontalArrangement = Arrangement.spacedBy(8.dp)
        ) {
            symbols.forEach { sym ->
                val isSelected = sym == selectedSymbol
                Button(
                    onClick = { selectedSymbol = sym },
                    colors = ButtonDefaults.buttonColors(
                        containerColor = if (isSelected) CyanAccent.copy(alpha = 0.2f) else DarkElevatedSurface
                    ),
                    shape = RoundedCornerShape(10.dp),
                    modifier = Modifier
                        .border(
                            1.dp,
                            if (isSelected) CyanAccent else BorderColor,
                            RoundedCornerShape(10.dp)
                        ),
                    contentPadding = PaddingValues(horizontal = 14.dp, vertical = 6.dp)
                ) {
                    Text(
                        text = sym.replace("USDT", ""),
                        color = if (isSelected) CyanAccent else TextSecondary,
                        fontSize = 12.sp,
                        fontWeight = FontWeight.Bold
                    )
                }
            }
        }

        Spacer(modifier = Modifier.height(8.dp))

        // Timeframe Selector Chips
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.spacedBy(6.dp)
        ) {
            intervals.forEach { (intVal, label) ->
                val isSelected = intVal == selectedInterval
                Button(
                    onClick = { selectedInterval = intVal },
                    colors = ButtonDefaults.buttonColors(
                        containerColor = if (isSelected) EmeraldPrimary.copy(alpha = 0.25f) else DarkElevatedSurface.copy(alpha = 0.6f)
                    ),
                    shape = RoundedCornerShape(8.dp),
                    modifier = Modifier
                        .weight(1f)
                        .border(
                            1.dp,
                            if (isSelected) EmeraldPrimary else BorderColor.copy(alpha = 0.5f),
                            RoundedCornerShape(8.dp)
                        ),
                    contentPadding = PaddingValues(horizontal = 4.dp, vertical = 4.dp)
                ) {
                    Text(
                        text = label,
                        color = if (isSelected) EmeraldPrimary else TextMuted,
                        fontSize = 11.sp,
                        fontWeight = FontWeight.SemiBold
                    )
                }
            }
        }

        Spacer(modifier = Modifier.height(10.dp))

        // TradingView Embedded WebView Container
        Card(
            modifier = Modifier
                .fillMaxWidth()
                .weight(1f)
                .border(1.dp, BorderColor, RoundedCornerShape(16.dp)),
            shape = RoundedCornerShape(16.dp),
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
                                javaScriptEnabled = true
                                domStorageEnabled = true
                                databaseEnabled = true
                                useWideViewPort = true
                                loadWithOverviewMode = true
                                setSupportZoom(true)
                                builtInZoomControls = true
                                displayZoomControls = false
                                allowFileAccess = true
                                allowContentAccess = true
                                cacheMode = WebSettings.LOAD_DEFAULT
                            }
                            webChromeClient = WebChromeClient()
                            webViewClient = object : WebViewClient() {
                                override fun onPageStarted(view: WebView?, url: String?, favicon: Bitmap?) {
                                    isLoading = true
                                }
                                override fun onPageFinished(view: WebView?, url: String?) {
                                    isLoading = false
                                }
                                override fun onReceivedError(view: WebView?, request: WebResourceRequest?, error: WebResourceError?) {
                                    isLoading = false
                                }
                            }
                            setBackgroundColor(0xFF030712.toInt())
                        }
                    },
                    update = { webView ->
                        val targetUrl = buildTradingViewUrl(selectedSymbol, selectedInterval)
                        val cacheKey = "$targetUrl#$reloadTrigger"
                        if (webView.tag != cacheKey) {
                            webView.tag = cacheKey
                            webView.loadUrl(targetUrl)
                        }
                    },
                    modifier = Modifier.fillMaxSize()
                )

                // Loading Overlay Indicator
                if (isLoading) {
                    Column(
                        horizontalAlignment = Alignment.CenterHorizontally,
                        modifier = Modifier
                            .align(Alignment.Center)
                            .clip(RoundedCornerShape(12.dp))
                            .background(DarkCardSurface.copy(alpha = 0.9f))
                            .padding(16.dp)
                    ) {
                        CircularProgressIndicator(
                            color = CyanAccent,
                            strokeWidth = 3.dp,
                            modifier = Modifier.size(28.dp)
                        )
                        Spacer(modifier = Modifier.height(8.dp))
                        Text(
                            text = "Loading Candlesticks...",
                            color = TextSecondary,
                            fontSize = 11.sp
                        )
                    }
                }
            }
        }

        Spacer(modifier = Modifier.height(8.dp))

        // Touch Zoom & Pan Guide
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .clip(RoundedCornerShape(8.dp))
                .background(DarkElevatedSurface.copy(alpha = 0.5f))
                .padding(horizontal = 10.dp, vertical = 6.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            Text(
                text = "💡 Tip: 2-finger pinch to zoom • drag horizontally to view past candles • tap candle for OHLC data",
                color = TextMuted,
                fontSize = 10.sp
            )
        }

        Spacer(modifier = Modifier.height(60.dp))
    }
}

private fun buildTradingViewUrl(symbol: String, interval: String): String {
    return "https://s.tradingview.com/widgetembed/?frameElementId=tradingview_widget" +
            "&symbol=BINANCE:${symbol}" +
            "&interval=${interval}" +
            "&hidesidetoolbar=0" +
            "&symboledit=1" +
            "&saveimage=1" +
            "&toolbarbg=030712" +
            "&theme=dark" +
            "&style=1" +
            "&timezone=Asia%2FKolkata"
}
