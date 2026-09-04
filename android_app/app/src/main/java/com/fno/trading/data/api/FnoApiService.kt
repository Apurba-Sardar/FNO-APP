package com.fno.trading.data.api

import com.fno.trading.data.model.*
import okhttp3.OkHttpClient
import okhttp3.logging.HttpLoggingInterceptor
import retrofit2.Response
import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory
import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.Header
import retrofit2.http.POST
import java.util.concurrent.TimeUnit

interface FnoApiService {

    @GET("live/status")
    suspend fun getStatus(
        @Header("x-live-operator-token") token: String = "LIVE_OPERATOR_TOKEN_2026"
    ): LiveStatusResponse

    @GET("live/account")
    suspend fun getAccount(
        @Header("x-live-operator-token") token: String = "LIVE_OPERATOR_TOKEN_2026"
    ): LiveAccountResponse

    @GET("live/positions")
    suspend fun getPositions(
        @Header("x-live-operator-token") token: String = "LIVE_OPERATOR_TOKEN_2026"
    ): PositionsResponse

    @GET("live/orders")
    suspend fun getOrders(
        @Header("x-live-operator-token") token: String = "LIVE_OPERATOR_TOKEN_2026"
    ): OrdersResponse

    @GET("opportunities/top")
    suspend fun getTopOpportunities(): OpportunitiesResponse

    @POST("live/test-trade")
    suspend fun punchTestTrade(
        @Body request: TestTradeRequest,
        @Header("x-live-operator-token") token: String = "LIVE_OPERATOR_TOKEN_2026"
    ): SimpleActionResponse

    @POST("live/exit-position")
    suspend fun exitPosition(
        @Body request: ExitPositionRequest,
        @Header("x-live-operator-token") token: String = "LIVE_OPERATOR_TOKEN_2026"
    ): SimpleActionResponse

    @POST("live/auto-trading/toggle")
    suspend fun toggleAutoTrading(
        @Header("x-live-operator-token") token: String = "LIVE_OPERATOR_TOKEN_2026"
    ): SimpleActionResponse

    @POST("live/reset-circuit")
    suspend fun resetCircuit(
        @Header("x-live-operator-token") token: String = "LIVE_OPERATOR_TOKEN_2026"
    ): SimpleActionResponse

    @POST("notifications/test")
    suspend fun sendTestNotification(): SimpleActionResponse

    companion object {
        var currentServerUrl = "http://20.244.21.190:8000/api/v1/"

        fun create(baseUrl: String = currentServerUrl): FnoApiService {
            val logging = HttpLoggingInterceptor().apply {
                level = HttpLoggingInterceptor.Level.BASIC
            }

            val client = OkHttpClient.Builder()
                .addInterceptor(logging)
                .connectTimeout(10, TimeUnit.SECONDS)
                .readTimeout(15, TimeUnit.SECONDS)
                .build()

            val effectiveUrl = if (baseUrl.endsWith("/")) baseUrl else "$baseUrl/"

            return Retrofit.Builder()
                .baseUrl(effectiveUrl)
                .client(client)
                .addConverterFactory(GsonConverterFactory.create())
                .build()
                .create(FnoApiService::class.java)
        }
    }
}
