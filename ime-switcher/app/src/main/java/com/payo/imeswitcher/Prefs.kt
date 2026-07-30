package com.payo.imeswitcher

import android.content.Context

object Prefs {
    private const val NAME = "ime_switcher_prefs"
    private const val KEY_ENABLED = "service_enabled"

    fun isServiceEnabled(context: Context): Boolean =
        context.getSharedPreferences(NAME, Context.MODE_PRIVATE)
            .getBoolean(KEY_ENABLED, false)

    fun setServiceEnabled(context: Context, enabled: Boolean) {
        context.getSharedPreferences(NAME, Context.MODE_PRIVATE)
            .edit()
            .putBoolean(KEY_ENABLED, enabled)
            .apply()
    }
}
