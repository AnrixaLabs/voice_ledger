package com.anrixa.voiceledger.ui

import android.Manifest
import android.content.pm.PackageManager
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Check
import androidx.compose.material.icons.filled.Mic
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.fragment.app.FragmentActivity
import java.io.File

/**
 * Design intent: plain Material 3 components, no custom shadows/
 * gradients/animation libraries. This is the whole UI budget for a
 * mid-range (A-series, not flagship) phone to stay snappy.
 */

@Composable
fun SettingsScreen(vm: VoiceLedgerViewModel) {
    val serverUrl by vm.serverBaseUrl.collectAsState()
    val deviceId by vm.deviceId.collectAsState()
    var urlField by remember { mutableStateOf(serverUrl) }
    var codeField by remember { mutableStateOf("") }
    var labelField by remember { mutableStateOf("My phone") }
    var status by remember { mutableStateOf<String?>(null) }

    Column(Modifier.fillMaxSize().padding(24.dp), verticalArrangement = Arrangement.spacedBy(16.dp)) {
        Text("Server", style = MaterialTheme.typography.titleMedium)
        OutlinedTextField(
            value = urlField, onValueChange = { urlField = it; vm.setServerBaseUrl(it) },
            label = { Text("Server address (e.g. http://192.168.1.42:8420/)") },
            modifier = Modifier.fillMaxWidth(),
        )

        Divider()

        Text("Pairing", style = MaterialTheme.typography.titleMedium)
        if (deviceId != null) {
            Text("This device is paired.")
        } else {
            Text("Ask the person at the server to show you a pairing code, then enter it below.")
            OutlinedTextField(
                value = codeField, onValueChange = { codeField = it.uppercase() },
                label = { Text("Pairing code") }, modifier = Modifier.fillMaxWidth(),
            )
            OutlinedTextField(
                value = labelField, onValueChange = { labelField = it },
                label = { Text("Label for this device") }, modifier = Modifier.fillMaxWidth(),
            )
            Button(onClick = {
                vm.completePairing(
                    codeField.trim(), labelField.trim(),
                    onDone = { status = "Paired." },
                    onError = { status = it },
                )
            }) { Text("Complete pairing") }
        }
        status?.let { Text(it, color = MaterialTheme.colorScheme.secondary) }
    }
}

@Composable
fun GuidedCaptureScreen(vm: VoiceLedgerViewModel, cacheDir: File, onAllFieldsDone: () -> Unit) {
    val entry by vm.entry.collectAsState()
    var fieldIndex by remember { mutableStateOf(0) }
    var isRecording by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf<String?>(null) }
    val context = LocalContext.current
    val recorder = remember { com.anrixa.voiceledger.audio.AudioRecorder(cacheDir) }
    var pcmFile by remember { mutableStateOf<File?>(null) }

    fun startRecording() {
        runCatching { recorder.start() }
            .onSuccess { file ->
                pcmFile = file
                isRecording = true
                error = null
            }
            .onFailure { error = it.message ?: "Could not start recording." }
    }

    val micPermissionLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.RequestPermission()
    ) { granted ->
        if (granted) startRecording()
        else error = "Microphone permission is required to record a ledger entry."
    }

    val field = GuidedField.entries.getOrNull(fieldIndex)

    Column(
        Modifier.fillMaxSize().padding(24.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.Center,
    ) {
        if (field == null) {
            Text("All fields captured.", style = MaterialTheme.typography.titleMedium)
            Spacer(Modifier.height(16.dp))
            Button(onClick = onAllFieldsDone) { Text("Review and confirm") }
            return@Column
        }

        LinearProgressIndicator(
            progress = fieldIndex / GuidedField.entries.size.toFloat(),
            modifier = Modifier.fillMaxWidth(),
        )
        Spacer(Modifier.height(32.dp))
        Text(field.promptHy, style = MaterialTheme.typography.headlineSmall, textAlign = androidx.compose.ui.text.style.TextAlign.Center)
        Spacer(Modifier.height(8.dp))
        entry.values[field]?.let {
            val summary = (it["text"] ?: it["date"] ?: it["amount"])?.toString()
            if (summary != null) Text("Heard: $summary", style = MaterialTheme.typography.bodyMedium)
        }
        Spacer(Modifier.height(32.dp))

        FilledIconButton(
            onClick = {
                if (!isRecording) {
                    if (androidx.core.content.ContextCompat.checkSelfPermission(
                            context, Manifest.permission.RECORD_AUDIO
                        ) == PackageManager.PERMISSION_GRANTED
                    ) {
                        startRecording()
                    } else {
                        micPermissionLauncher.launch(Manifest.permission.RECORD_AUDIO)
                    }
                } else {
                    isRecording = false
                    val wav = recorder.stop(pcmFile!!)
                    vm.captureField(
                        field, wav,
                        onDone = { fieldIndex++ },
                        onError = { error = it },
                    )
                }
            },
            modifier = Modifier.size(80.dp),
        ) {
            Icon(
                imageVector = if (isRecording) Icons.Filled.Check else Icons.Filled.Mic,
                contentDescription = if (isRecording) "Stop recording" else "Start recording",
            )
        }
        Spacer(Modifier.height(8.dp))
        Text(if (isRecording) "Recording - tap to stop" else "Tap to record")

        error?.let { Text(it, color = MaterialTheme.colorScheme.error, modifier = Modifier.padding(top = 16.dp)) }

        TextButton(onClick = { fieldIndex++ }, modifier = Modifier.padding(top = 24.dp)) {
            Text("Skip this field")
        }
    }
}

@Composable
fun ConfirmScreen(vm: VoiceLedgerViewModel, activity: FragmentActivity, onSubmitted: () -> Unit) {
    val entry by vm.entry.collectAsState()
    val submitState by vm.submitState.collectAsState()

    Column(Modifier.fillMaxSize().padding(24.dp)) {
        Text("Review before signing", style = MaterialTheme.typography.titleMedium)
        Spacer(Modifier.height(16.dp))

        LazyColumn(Modifier.weight(1f)) {
            items(GuidedField.entries.toList()) { field ->
                val v = entry.values[field]
                val display = v?.get("text") ?: v?.get("date")
                    ?: v?.let { "${it["amount"]} ${it["currency"]}" }
                ListItem(
                    headlineContent = { Text(fieldLabel(field)) },
                    supportingContent = { Text(display?.toString() ?: "-") },
                )
            }
        }

        when (val s = submitState) {
            is SubmitState.Error -> Text(s.message, color = MaterialTheme.colorScheme.error)
            SubmitState.Success -> Text("Saved.", color = MaterialTheme.colorScheme.primary)
            else -> {}
        }

        Button(
            onClick = { vm.confirmAndSubmit(activity, onDone = onSubmitted) },
            enabled = submitState !is SubmitState.Signing && submitState !is SubmitState.Submitting,
            modifier = Modifier.fillMaxWidth().padding(top = 16.dp),
        ) {
            Text(
                when (submitState) {
                    SubmitState.Signing -> "Waiting for fingerprint..."
                    SubmitState.Submitting -> "Saving..."
                    else -> "Confirm with fingerprint"
                }
            )
        }
    }
}

private fun fieldLabel(field: GuidedField) = when (field) {
    GuidedField.NAME -> "Name"
    GuidedField.PLACE -> "Place"
    GuidedField.TRANSACTION_DATE -> "Date"
    GuidedField.AMOUNT_PAID -> "Amount paid"
    GuidedField.AMOUNT_DUE -> "Amount still due"
    GuidedField.DUE_DATE -> "Due by"
}
