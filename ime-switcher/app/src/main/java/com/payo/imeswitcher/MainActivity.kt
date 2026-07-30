package com.payo.imeswitcher

import android.Manifest
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build
import android.os.Bundle
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
        } else {
            Toast.makeText(this, R.string.permission_denied, Toast.LENGTH_LONG).show()
            updateUi(running = false)
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

        updateUi(Prefs.isServiceEnabled(this))
    }

    override fun onResume() {
        super.onResume()
        updateUi(Prefs.isServiceEnabled(this))
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
    }

    private fun startNotificationService() {
        Prefs.setServiceEnabled(this, true)
        ContextCompat.startForegroundService(
            this,
            Intent(this, ImeNotificationService::class.java)
        )
        updateUi(running = true)
        Toast.makeText(this, R.string.notification_enabled, Toast.LENGTH_SHORT).show()
    }

    private fun stopNotificationService() {
        Prefs.setServiceEnabled(this, false)
        stopService(Intent(this, ImeNotificationService::class.java))
        updateUi(running = false)
        Toast.makeText(this, R.string.notification_disabled, Toast.LENGTH_SHORT).show()
    }

    private fun updateUi(running: Boolean) {
        binding.statusText.setText(
            if (running) R.string.status_on else R.string.status_off
        )
        binding.btnEnable.isEnabled = !running
        binding.btnDisable.isEnabled = running
    }
}
