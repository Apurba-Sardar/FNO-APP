package com.fno.trading.notifications

import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import androidx.core.app.NotificationCompat
import com.fno.trading.FnoApplication
import com.fno.trading.MainActivity

object FnoNotificationHelper {

    fun showTradeNotification(
        context: Context,
        title: String,
        message: String,
        notificationId: Int = (System.currentTimeMillis() % 100000).toInt()
    ) {
        val intent = Intent(context, MainActivity::class.java).apply {
            flags = Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TASK
        }
        val pendingIntent = PendingIntent.getActivity(
            context,
            0,
            intent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )

        val builder = NotificationCompat.Builder(context, FnoApplication.CHANNEL_TRADES)
            .setSmallIcon(android.R.drawable.ic_dialog_info)
            .setContentTitle(title)
            .setContentText(message)
            .setStyle(NotificationCompat.BigTextStyle().bigText(message))
            .setPriority(NotificationCompat.PRIORITY_HIGH)
            .setAutoCancel(true)
            .setContentIntent(pendingIntent)

        val notificationManager = context.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        notificationManager.notify(notificationId, builder.build())
    }

    fun showSetupNotification(
        context: Context,
        symbol: String,
        score: Double,
        triggerPrice: Double
    ) {
        val title = "⚡ Breakout Setup: $symbol"
        val message = "Score: ${score.toInt()}/100 • Trigger: $$triggerPrice\nReady for 3x scalp entry."
        showTradeNotification(context, title, message)
    }

    fun showProfitTargetNotification(context: Context, todayProfit: Double) {
        val title = "🏆 Daily Profit Goal Locked: $${String.format("%.2f", todayProfit)}"
        val message = "Today's profit goal reached! Profits secured for the day."
        showTradeNotification(context, title, message)
    }
}
