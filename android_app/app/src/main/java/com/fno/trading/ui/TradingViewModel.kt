package com.fno.trading.ui

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.fno.trading.data.api.FnoApiService
import com.fno.trading.data.model.*
import com.fno.trading.notifications.FnoNotificationHelper
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch

data class TradingUiState(
    val status: LiveStatusResponse? = null,
    val account: LiveAccountResponse? = null,
    val positions: List<PositionItem> = emptyList(),
    val orders: List<OrderItem> = emptyList(),
    val opportunities: List<OpportunityItem> = emptyList(),
    val isLoading: Boolean = false,
    val errorMessage: String? = null,
    val statusMessage: String = "Connected to CoinDCX Live Server."
)

class TradingViewModel(application: Application) : AndroidViewModel(application) {

    private val api = FnoApiService.create()
    private val _uiState = MutableStateFlow(TradingUiState())
    val uiState: StateFlow<TradingUiState> = _uiState.asStateFlow()

    private var previousPositionCount = -1

    init {
        startPolling()
    }

    private fun startPolling() {
        viewModelScope.launch {
            while (isActive) {
                loadData()
                delay(8000)
            }
        }
    }

    fun loadData() {
        viewModelScope.launch {
            try {
                val statusDeferred = api.getStatus()
                val accountDeferred = api.getAccount()
                val positionsDeferred = api.getPositions()
                val ordersDeferred = api.getOrders()
                val oppsDeferred = try { api.getTopOpportunities() } catch (_: Exception) { OpportunitiesResponse() }

                val posList = positionsDeferred.items ?: emptyList()
                val openPositions = posList.filter { it.status == "open" }

                // Trigger local notifications if position count changes
                if (previousPositionCount != -1 && openPositions.size > previousPositionCount) {
                    val latest = openPositions.firstOrNull()
                    if (latest != null) {
                        FnoNotificationHelper.showTradeNotification(
                            getApplication(),
                            "🚀 Trade Active: ${latest.pair}",
                            "Action: ${latest.direction.uppercase()} @ 3x Isolated\nEntry: $${latest.averagePrice}"
                        )
                    }
                }
                previousPositionCount = openPositions.size

                _uiState.value = _uiState.value.copy(
                    status = statusDeferred,
                    account = accountDeferred,
                    positions = posList,
                    orders = ordersDeferred.items ?: emptyList(),
                    opportunities = oppsDeferred.items ?: emptyList(),
                    errorMessage = null
                )
            } catch (e: Exception) {
                _uiState.value = _uiState.value.copy(
                    errorMessage = e.message ?: "Connection error"
                )
            }
        }
    }

    fun punch3xScalp(symbol: String = "B-XRP_USDT", side: String = "buy", qty: Double = 15.0) {
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isLoading = true, statusMessage = "Punched 3x Scalp order on $symbol...")
            try {
                val res = api.punchTestTrade(
                    TestTradeRequest(
                        symbol = symbol,
                        side = side,
                        quantity = qty,
                        leverage = 3
                    )
                )
                _uiState.value = _uiState.value.copy(
                    statusMessage = "Order Submitted! Auto-Close TP/SL attached."
                )
                FnoNotificationHelper.showTradeNotification(
                    getApplication(),
                    "🚀 Scalp Executed: $symbol",
                    "$side.uppercase() @ 3x leverage • TP +1.8% / SL -1.2% attached"
                )
                delay(1500)
                loadData()
            } catch (e: Exception) {
                _uiState.value = _uiState.value.copy(
                    errorMessage = "Trade Error: ${e.message}"
                )
            } finally {
                _uiState.value = _uiState.value.copy(isLoading = false)
            }
        }
    }

    fun exitPosition(positionId: String, pair: String) {
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isLoading = true, statusMessage = "Exiting $pair at market...")
            try {
                api.exitPosition(ExitPositionRequest(positionId = positionId))
                _uiState.value = _uiState.value.copy(
                    statusMessage = "Position closed! Margin returned to free cash."
                )
                FnoNotificationHelper.showTradeNotification(
                    getApplication(),
                    "🎯 Position Closed: $pair",
                    "Market exit executed successfully."
                )
                delay(1500)
                loadData()
            } catch (e: Exception) {
                _uiState.value = _uiState.value.copy(
                    errorMessage = "Exit Error: ${e.message}"
                )
            } finally {
                _uiState.value = _uiState.value.copy(isLoading = false)
            }
        }
    }

    fun toggleAutoTrading() {
        viewModelScope.launch {
            try {
                val res = api.toggleAutoTrading()
                _uiState.value = _uiState.value.copy(
                    statusMessage = "Autonomous Scalp Engine toggled."
                )
                loadData()
            } catch (e: Exception) {
                _uiState.value = _uiState.value.copy(errorMessage = e.message)
            }
        }
    }

    fun sendTestAlert() {
        viewModelScope.launch {
            try {
                api.sendTestNotification()
                FnoNotificationHelper.showTradeNotification(
                    getApplication(),
                    "🔔 S24 Ultra Local Push Test",
                    "✅ Native Android alerts working with sound & vibration!"
                )
                _uiState.value = _uiState.value.copy(statusMessage = "Test alert sent to S24 Ultra!")
            } catch (e: Exception) {
                // If backend unreachable, still trigger local notification on phone!
                FnoNotificationHelper.showTradeNotification(
                    getApplication(),
                    "🔔 S24 Ultra Local Push Test",
                    "✅ Native Android alerts active!"
                )
                _uiState.value = _uiState.value.copy(statusMessage = "Local alert triggered on phone.")
            }
        }
    }

    fun resetCircuit() {
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isLoading = true, statusMessage = "Resetting circuit breaker and reconciling...")
            try {
                api.resetCircuit()
                _uiState.value = _uiState.value.copy(
                    statusMessage = "Engine unblocked and reconciled successfully!"
                )
                delay(1000)
                loadData()
            } catch (e: Exception) {
                _uiState.value = _uiState.value.copy(errorMessage = "Reset Error: ${e.message}")
            } finally {
                _uiState.value = _uiState.value.copy(isLoading = false)
            }
        }
    }
}
