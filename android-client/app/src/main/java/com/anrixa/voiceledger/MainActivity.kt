package com.anrixa.voiceledger

import android.os.Bundle
import androidx.activity.compose.setContent
import androidx.activity.viewModels
import androidx.compose.foundation.layout.padding
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Mic
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.fragment.app.FragmentActivity
import androidx.navigation.NavHostController
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.currentBackStackEntryAsState
import androidx.navigation.compose.rememberNavController
import com.anrixa.voiceledger.ui.ConfirmScreen
import com.anrixa.voiceledger.ui.GuidedCaptureScreen
import com.anrixa.voiceledger.ui.SettingsScreen
import com.anrixa.voiceledger.ui.VoiceLedgerViewModel

/**
 * FragmentActivity (not plain ComponentActivity) because
 * androidx.biometric.BiometricPrompt needs a FragmentActivity to
 * anchor its dialog fragment.
 */
class MainActivity : FragmentActivity() {

    private val vm: VoiceLedgerViewModel by viewModels()

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent {
            MaterialTheme {
                VoiceLedgerNav(vm, this)
            }
        }
    }
}

@Composable
private fun VoiceLedgerNav(vm: VoiceLedgerViewModel, activity: FragmentActivity) {
    val nav = rememberNavController()
    Scaffold(
        bottomBar = { VoiceLedgerBottomBar(nav) }
    ) { padding ->
        NavHost(nav, startDestination = "capture", modifier = Modifier.padding(padding)) {
            composable("capture") {
                GuidedCaptureScreen(vm, activity.cacheDir, onAllFieldsDone = { nav.navigate("confirm") })
            }
            composable("confirm") {
                ConfirmScreen(vm, activity, onSubmitted = { nav.navigate("capture") })
            }
            composable("settings") {
                SettingsScreen(vm)
            }
        }
    }
}

@Composable
private fun VoiceLedgerBottomBar(nav: NavHostController) {
    val backStackEntry by nav.currentBackStackEntryAsState()
    val current = backStackEntry?.destination?.route
    NavigationBar {
        NavigationBarItem(
            selected = current == "capture", onClick = { nav.navigate("capture") },
            icon = { Icon(Icons.Filled.Mic, contentDescription = null) },
            label = { Text("Record") },
        )
        NavigationBarItem(
            selected = current == "settings", onClick = { nav.navigate("settings") },
            icon = { Icon(Icons.Filled.Settings, contentDescription = null) },
            label = { Text("Settings") },
        )
    }
}
