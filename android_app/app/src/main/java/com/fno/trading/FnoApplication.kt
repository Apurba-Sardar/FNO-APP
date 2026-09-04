package com.fno.trading

import android.app.Application
import android.app.NotificationChannel
import android.app.NotificationManager
import android.content.Context
import android.os.Build

class FnoApplication : Application() {

    override fun onCreate() {
        super.onCreate()
        createNotificationChannels()
    }

    private fun createNotificationChannels() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val notificationManager = getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager

            // 1. High Priority Trades Channel (Sound + Vibration + Heads-up banner)
            val tradesChannel = NotificationChannel(
                CHANNEL_TRADES,
                "Live Trades & Exits",
                NotificationManager.IMPORTANCE_HIGH
            ).apply {
                description = "Urgent alerts for trade executions, take-profit hits, and stop losses"
                enableVibration(true)
                vibrationPattern = longArrayOf(0, 250, 150, 250)
            }

            // 2. Breakout Setups Channel
            val setupsChannel = NotificationChannel(
                CHANNEL_SETUPS,
                "Breakout Opportunities",
                NotificationManager.IMPORTANCE_DEFAULT
            ).apply {
                description = "High-probability Tier-A breakout scanner detections"
                enableVibration(true)
            }

            // 3. Milestones Channel (Daily Profit Goal)
            val milestonesChannel = NotificationChannel(
                CHANNEL_MILESTONES,
                "Daily Profit Milestones",
                NotificationManager.IMPORTANCE_HIGH
            ).apply {
                description = "Celebration alerts when daily profit goals are achieved"
                enableVibration(true)
            }

            notificationManager.createNotificationChannels(listOf(tradesChannel, setupsChannel, milestonesChannel))
        }
    }

    companion object {
        const val CHANNEL_TRADES = "fno_trades_channel"
        const val CHANNEL_SETUPS = "fno_setups_channel"
        const val CHANNEL_MILESTONES = "fno_milestones_channel"
    }
}
