package com.payo.imeswitcher

import android.Manifest
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.os.PowerManager
import android.provider.Settings
import android.widget.Toast
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AppCompatActivity
import androidx.core.content.ContextCompat
import com.payo.imeswitcher.databinding.ActivityMainBinding

class MainActivity : AppCompatActivity() {

    private lateinit var binding: ActivityMainBinding

    private val notificationPermissionLauncher = registerForActivityResult(
        ActivityResultContracts.RequestPermission()
    ) { granted ->
        if (granted) {
            startNotificationService()
            maybeAskBatteryExemption()
        } else {
            Toast.makeText(this, R.string.permission_denied, Toast.LENGTH_LONG).show()
            updateUi()
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityMainBinding.inflate(layoutInflater)
        setContentView(binding.root)

        binding.btnEnable.setOnClickListener { requestAndStart() }
        binding.btnDisable.setOnClickListener { stopNotificationService() }
        binding.btnTestPicker.setOnClickListener {
            startActivity(Intent(this, ImePickerActivity::class.java))
        }
        binding.btnOpenNotificationSettings.setOnClickListener { openAppNotificationSettings() }
        binding.btnOpenBatterySettings.setOnClickListener { openBatterySettings() }

        updateUi()
    }

    override fun onResume() {
        super.onResume()
        updateUi()
        // If user already enabled it, refresh the foreground notification after returning.
        if (Prefs.isServiceEnabled(this) && NotificationHelper.areNotificationsEnabled(this)) {
            ContextCompat.startForegroundService(
                this,
                Intent(this, ImeNotificationService::class.java)
            )
        }
    }

    private fun requestAndStart() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            val granted = ContextCompat.checkSelfPermission(
                this,
                Manifest.permission.POST_NOTIFICATIONS
            ) == PackageManager.PERMISSION_GRANTED

            if (!granted) {
                notificationPermissionLauncher.launch(Manifest.permission.POST_NOTIFICATIONS)
                return
            }
        }
        startNotificationService()
        maybeAskBatteryExemption()
    }

    private fun startNotificationService() {
        NotificationHelper.ensureChannel(this)
        Prefs.setServiceEnabled(this, true)
        ContextCompat.startForegroundService(
            this,
            Intent(this, ImeNotificationService::class.java)
        )
        updateUi()
        Toast.makeText(this, R.string.notification_enabled, Toast.LENGTH_LONG).show()
    }

    private fun stopNotificationService() {
        Prefs.setServiceEnabled(this, false)
        stopService(Intent(this, ImeNotificationService::class.java))
        updateUi()
        Toast.makeText(this, R.string.notification_disabled, Toast.LENGTH_SHORT).show()
    }

    private fun updateUi() {
        val enabled = Prefs.isServiceEnabled(this)
        val notifOk = NotificationHelper.areNotificationsEnabled(this)

        binding.statusText.setText(
            when {
                enabled && !notifOk -> R.string.status_notif_blocked
                enabled -> R.string.status_on
                else -> R.string.status_off
            }
        )
        binding.btnEnable.isEnabled = !enabled || !notifOk
        binding.btnDisable.isEnabled = enabled
    }

    private fun maybeAskBatteryExemption() {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.M) return
        val pm = getSystemService(PowerManager::class.java) ?: return
        if (pm.isIgnoringBatteryOptimizations(packageName)) return

        try {
            startActivity(
                Intent(Settings.ACTION_REQUEST_IGNORE_BATTERY_OPTIMIZATIONS).apply {
                    data = Uri.parse("package:$packageName")
                }
            )
        } catch (_: Exception) {
            openBatterySettings()
        }
    }

    private fun openAppNotificationSettings() {
        val intent = Intent(Settings.ACTION_APP_NOTIFICATION_SETTINGS).apply {
            putExtra(Settings.EXTRA_APP_PACKAGE, packageName)
        }
        startActivity(intent)
    }

    private fun openBatterySettings() {
        try {
            startActivity(
                Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS).apply {
                    data = Uri.parse("package:$packageName")
                }
            )
        } catch (_: Exception) {
            Toast.makeText(this, R.string.open_settings_failed, Toast.LENGTH_SHORT).show()
        }
    }
}
