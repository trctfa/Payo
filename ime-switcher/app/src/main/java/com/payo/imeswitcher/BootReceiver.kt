package com.payo.imeswitcher

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import androidx.core.content.ContextCompat

class BootReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent?) {
        if (intent?.action != Intent.ACTION_BOOT_COMPLETED) return
        if (!Prefs.isServiceEnabled(context)) return

        NotificationHelper.postOngoing(context)
        try {
            ContextCompat.startForegroundService(
                context,
                Intent(context, ImeNotificationService::class.java)
            )
        } catch (_: Exception) {
            // Plain notification is enough as fallback.
        }
    }
}
