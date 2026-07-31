package com.payo.imeswitcher

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent

class NotificationActionReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent?) {
        when (intent?.action) {
            ACTION_STOP -> {
                Prefs.setServiceEnabled(context, false)
                context.stopService(Intent(context, ImeNotificationService::class.java))
                NotificationHelper.cancel(context)
            }
        }
    }

    companion object {
        const val ACTION_STOP = "com.payo.imeswitcher.ACTION_STOP"
    }
}
