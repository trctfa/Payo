package com.payo.imeswitcher

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.os.Build
import androidx.core.app.NotificationCompat
import androidx.core.app.NotificationManagerCompat

object NotificationHelper {
    // New ID so HyperOS users get a visible channel (old LOW channel stayed silent).
    const val CHANNEL_ID = "ime_switcher_channel_v3"
    private val OLD_CHANNEL_IDS = listOf("ime_switcher_channel", "ime_switcher_channel_v2")
    const val NOTIFICATION_ID = 1001

    fun ensureChannel(context: Context) {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O) return

        val manager = context.getSystemService(NotificationManager::class.java) ?: return

        OLD_CHANNEL_IDS.forEach { oldId ->
            if (manager.getNotificationChannel(oldId) != null) {
                manager.deleteNotificationChannel(oldId)
            }
        }

        if (manager.getNotificationChannel(CHANNEL_ID) != null) return

        val channel = NotificationChannel(
            CHANNEL_ID,
            context.getString(R.string.channel_name),
            NotificationManager.IMPORTANCE_HIGH
        ).apply {
            description = context.getString(R.string.channel_description)
            setShowBadge(true)
            enableVibration(false)
            setSound(null, null)
        }
        manager.createNotificationChannel(channel)
    }

    fun areNotificationsEnabled(context: Context): Boolean {
        return NotificationManagerCompat.from(context).areNotificationsEnabled()
    }

    fun buildNotification(context: Context): Notification {
        ensureChannel(context)

        val openPickerIntent = Intent(context, ImePickerActivity::class.java).apply {
            flags = Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP
        }
        val openPickerPending = PendingIntent.getActivity(
            context,
            1,
            openPickerIntent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )

        val openAppPending = PendingIntent.getActivity(
            context,
            2,
            Intent(context, MainActivity::class.java),
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )

        val stopPending = PendingIntent.getBroadcast(
            context,
            3,
            Intent(context, NotificationActionReceiver::class.java).setAction(
                NotificationActionReceiver.ACTION_STOP
            ),
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )

        return NotificationCompat.Builder(context, CHANNEL_ID)
            .setSmallIcon(R.drawable.ic_keyboard)
            .setContentTitle(context.getString(R.string.notification_title))
            .setContentText(context.getString(R.string.notification_text))
            .setContentIntent(openPickerPending)
            .setOngoing(true)
            .setOnlyAlertOnce(true)
            .setPriority(NotificationCompat.PRIORITY_HIGH)
            .setCategory(NotificationCompat.CATEGORY_SERVICE)
            .setVisibility(NotificationCompat.VISIBILITY_PUBLIC)
            .setForegroundServiceBehavior(NotificationCompat.FOREGROUND_SERVICE_IMMEDIATE)
            .addAction(
                R.drawable.ic_keyboard,
                context.getString(R.string.action_switch_ime),
                openPickerPending
            )
            .addAction(
                R.drawable.ic_settings,
                context.getString(R.string.action_open_app),
                openAppPending
            )
            .addAction(
                R.drawable.ic_close,
                context.getString(R.string.action_stop),
                stopPending
            )
            .build()
    }

    /** Post notification directly (works even if foreground service is blocked on HyperOS). */
    fun postOngoing(context: Context) {
        if (!areNotificationsEnabled(context)) return
        NotificationManagerCompat.from(context)
            .notify(NOTIFICATION_ID, buildNotification(context))
    }

    fun cancel(context: Context) {
        NotificationManagerCompat.from(context).cancel(NOTIFICATION_ID)
    }
}
