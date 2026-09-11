package com.anrixa.voiceledger.ui

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import androidx.fragment.app.FragmentActivity
import com.anrixa.voiceledger.biometric.BiometricSigner
import com.anrixa.voiceledger.network.ApiClientFactory
import com.anrixa.voiceledger.network.CanonicalJson
import com.anrixa.voiceledger.network.TransactionInBody
import com.anrixa.voiceledger.network.audioFilePart
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import java.io.File
import java.util.UUID

/** One guided-mode field, in prompt order. */
enum class GuidedField(val apiName: String, val promptHy: String) {
    NAME("counterparty_name", "\u0531\u057d\u0578\u0582\u0574\u0568՝ \u056b\u0576\u0578\u057e \u0587 \u056b\u0576\u0579 \u057e\u0573\u0561\u0580\u057e\u0565\u0581"), // "Say the name of who paid or was paid"
    PLACE("place", "\u0531\u057d\u0578\u0582\u0574\u0568 \u057e\u0561\u0575\u0580\u0568"), // "Say the place"
    TRANSACTION_DATE("transaction_date", "\u0531\u057d\u0578\u0582\u0574\u0568 \u0561\u0574\u057d\u0561\u0569\u056b\u057e\u0568"), // "Say the date"
    AMOUNT_PAID("amount_paid", "\u0531\u057d\u0578\u0582\u0574\u0568՝ \u056b\u0576\u0579\u0584\u0561\u0576 \u0567 \u057e\u0573\u0561\u0580\u057e\u0565\u056c"), // "Say how much was paid"
    AMOUNT_DUE("amount_due", "\u0531\u057d\u0578\u0582\u0574\u0568՝ \u056b\u0576\u0579\u0584\u0561\u0576 \u0567 \u0574\u0576\u0561\u0581\u0565\u056c"), // "Say how much is left to pay"
    DUE_DATE("due_date", "\u0531\u057d\u0578\u0582\u0574\u0568՝ \u0574\u056b\u0576\u0579\u0587 \u057a\u0565\u057f\u0584 \u0567 \u057e\u0573\u0561\u0580\u057e\u0565\u056c"), // "Say by when it should be paid"
}

data class GuidedEntryState(
    val values: Map<GuidedField, Map<String, Any?>> = emptyMap(),
) {
    fun with(field: GuidedField, parsed: Map<String, Any?>) = copy(values = values + (field to parsed))
}

sealed class SubmitState {
    object Idle : SubmitState()
    object Signing : SubmitState()
    object Submitting : SubmitState()
    object Success : SubmitState()
    data class Error(val message: String) : SubmitState()
}

class VoiceLedgerViewModel(application: Application) : AndroidViewModel(application) {

    // TODO: load/save via DataStore instead of an in-memory default.
    private val _serverBaseUrl = MutableStateFlow("http://192.168.1.42:8420/")
    val serverBaseUrl: StateFlow<String> = _serverBaseUrl.asStateFlow()

    private val _deviceId = MutableStateFlow<String?>(null)
    val deviceId: StateFlow<String?> = _deviceId.asStateFlow()

    private val _entry = MutableStateFlow(GuidedEntryState())
    val entry: StateFlow<GuidedEntryState> = _entry.asStateFlow()

    private val _submitState = MutableStateFlow<SubmitState>(SubmitState.Idle)
    val submitState: StateFlow<SubmitState> = _submitState.asStateFlow()

    private val signer = BiometricSigner()
    private val cacheDir get() = getApplication<Application>().cacheDir

    private fun api() = ApiClientFactory.create(_serverBaseUrl.value)

    fun setServerBaseUrl(url: String) {
        _serverBaseUrl.value = if (url.endsWith("/")) url else "$url/"
    }

    // Deliberately no "generate a pairing code" action here. The code is
    // only ever shown on the server/PC console (POST /pair/start is
    // called there - see pc-client), so pairing requires someone to be
    // physically at the server. The phone's only job is to type in what
    // it's shown there.

    /** The person types in the code shown on the server console; we
     * generate (or reuse) our Keystore key pair and register the public half. */
    fun completePairing(code: String, deviceLabel: String, onDone: () -> Unit, onError: (String) -> Unit) {
        viewModelScope.launch {
            runCatching {
                val publicKeyPem = signer.ensureKeyPairAndGetPublicKeyPem()
                api().pairComplete(
                    com.anrixa.voiceledger.network.PairCompleteRequest(code, deviceLabel, publicKeyPem)
                )
            }.onSuccess {
                _deviceId.value = it.device_id
                onDone()
            }.onFailure { onError(it.message ?: "Pairing failed.") }
        }
    }

    /** Records+uploads audio for one guided field, parses it server-side,
     * and stores the parsed result. */
    fun captureField(field: GuidedField, wavFile: File, onDone: () -> Unit, onError: (String) -> Unit) {
        viewModelScope.launch {
            runCatching {
                val transcript = api().speechToText(audioFilePart(wavFile)).transcript
                api().guidedField(field.apiName, transcript)
            }.onSuccess {
                _entry.value = _entry.value.with(field, it)
                onDone()
            }.onFailure { onError(it.message ?: "Couldn't process that recording.") }
        }
    }

    /** Builds the payload, shows the fingerprint prompt, signs, submits. */
    fun confirmAndSubmit(activity: FragmentActivity, onDone: () -> Unit) {
        val deviceId = _deviceId.value
        if (deviceId == null) {
            _submitState.value = SubmitState.Error("Pair this device first (see Settings).")
            return
        }
        val payload = buildPayload()
        val payloadJson = CanonicalJson.stringify(payload)

        viewModelScope.launch {
            _submitState.value = SubmitState.Signing
            val signature = try {
                signer.signWithBiometricConfirmation(
                    activity, payloadJson,
                    title = "Confirm ledger entry",
                    subtitle = payload["counterparty_name"] as? String,
                )
            } catch (e: Exception) {
                _submitState.value = SubmitState.Error(e.message ?: "Biometric confirmation was cancelled.")
                return@launch
            }

            _submitState.value = SubmitState.Submitting
            runCatching {
                api().submitTransaction(TransactionInBody(deviceId, payloadJson, signature))
            }.onSuccess {
                _submitState.value = SubmitState.Success
                _entry.value = GuidedEntryState()
                onDone()
            }.onFailure {
                _submitState.value = SubmitState.Error(it.message ?: "Could not reach the server.")
            }
        }
    }

    private fun buildPayload(): Map<String, Any?> {
        val v = _entry.value.values
        fun text(f: GuidedField) = v[f]?.get("text") as? String
        fun date(f: GuidedField) = v[f]?.get("date") as? String
        fun amount(f: GuidedField) = v[f]?.get("amount") as? Double
        fun currency(f: GuidedField) = v[f]?.get("currency") as? String

        return mapOf(
            "id" to UUID.randomUUID().toString(),
            "counterparty_name" to (text(GuidedField.NAME) ?: ""),
            "place" to text(GuidedField.PLACE),
            "amount_paid" to amount(GuidedField.AMOUNT_PAID),
            "amount_paid_currency" to currency(GuidedField.AMOUNT_PAID),
            "amount_due" to amount(GuidedField.AMOUNT_DUE),
            "amount_due_currency" to currency(GuidedField.AMOUNT_DUE),
            "transaction_date" to date(GuidedField.TRANSACTION_DATE),
            "due_date" to date(GuidedField.DUE_DATE),
            "raw_transcript" to GuidedField.entries.joinToString(" | ") { f ->
                (v[f]?.get("raw_transcript") as? String).orEmpty()
            },
        )
    }
}
