package com.payo.imeswitcher

import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.view.inputmethod.InputMethodManager
import androidx.appcompat.app.AppCompatActivity

/**
 * Transparent activity opened from the notification action.
 * Calling [InputMethodManager.showInputMethodPicker] from a receiver is unreliable;
 * an Activity with a window token works across MIUI / HyperOS.
 */
class ImePickerActivity : AppCompatActivity() {

    private val handler = Handler(Looper.getMainLooper())

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        // Let the window attach, then show the system IME picker.
        window.decorView.post {
            val imm = getSystemService(INPUT_METHOD_SERVICE) as InputMethodManager
            imm.showInputMethodPicker()

            // Give the picker time to appear, then leave.
            handler.postDelayed({
                if (!isFinishing) finish()
            }, 400)
        }
    }

    override fun onStop() {
        super.onStop()
        if (!isFinishing) finish()
    }
}
