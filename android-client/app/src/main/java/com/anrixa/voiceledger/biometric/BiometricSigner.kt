package com.anrixa.voiceledger.biometric

import android.os.Build
import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyProperties
import android.util.Base64
import androidx.biometric.BiometricPrompt
import androidx.fragment.app.FragmentActivity
import java.security.KeyPairGenerator
import java.security.KeyStore
import java.security.Signature
import java.security.spec.ECGenParameterSpec
import kotlin.coroutines.resume
import kotlin.coroutines.resumeWithException
import kotlin.coroutines.suspendCoroutine

/**
 * Everything about "confirm this ledger entry with your fingerprint"
 * lives here. The private key never leaves the device's secure
 * hardware and the fingerprint image/template never leaves the
 * fingerprint sensor's own secure enclave — this class only ever
 * touches a [BiometricPrompt.CryptoObject], never biometric data
 * itself. What crosses the network is: the transaction JSON, plus a
 * signature over it that only exists because the OS confirmed a live
 * fingerprint match immediately beforehand.
 */
class BiometricSigner(private val keyAlias: String = "voice_ledger_signing_key") {

    private val keyStore = KeyStore.getInstance("AndroidKeyStore").apply { load(null) }

    fun hasKey(): Boolean = keyStore.containsAlias(keyAlias)

    /** Called once, during pairing. Returns the public key as PEM text,
     * ready to hand to POST /pair/complete. */
    fun ensureKeyPairAndGetPublicKeyPem(): String {
        if (!hasKey()) generateKeyPair()
        val cert = keyStore.getCertificate(keyAlias)
        val der = cert.publicKey.encoded // X.509 SubjectPublicKeyInfo — matches what
        // Python's `cryptography.hazmat.primitives.serialization.load_pem_public_key`
        // expects once PEM-wrapped below.
        val b64 = Base64.encodeToString(der, Base64.NO_WRAP)
        val lines = b64.chunked(64).joinToString("\n")
        return "-----BEGIN PUBLIC KEY-----\n$lines\n-----END PUBLIC KEY-----\n"
    }

    private fun generateKeyPair() {
        val purposes = KeyProperties.PURPOSE_SIGN
        val builder = KeyGenParameterSpec.Builder(keyAlias, purposes)
            .setAlgorithmParameterSpec(ECGenParameterSpec("secp256r1"))
            .setDigests(KeyProperties.DIGEST_SHA256)
            .setUserAuthenticationRequired(true)
            // Invalidate this key if the person enrolls a new fingerprint —
            // otherwise someone who adds their own print later could sign
            // as if they were the original owner.
            .setInvalidatedByBiometricEnrollment(true)

        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) {
            // timeout=0 + AUTH_BIOMETRIC_STRONG: a fresh biometric check is
            // required for every single signing operation, no grace window.
            builder.setUserAuthenticationParameters(0, KeyProperties.AUTH_BIOMETRIC_STRONG)
        } else {
            // Pre-API 30 equivalent of "authenticate every time".
            @Suppress("DEPRECATION")
            builder.setUserAuthenticationValidityDurationSeconds(-1)
        }

        val generator = KeyPairGenerator.getInstance(
            KeyProperties.KEY_ALGORITHM_EC, "AndroidKeyStore"
        )
        generator.initialize(builder.build())
        generator.generateKeyPair()
    }

    /**
     * Shows the fingerprint prompt, and if — and only if — it succeeds,
     * signs [canonicalPayloadJson] and returns the base64 signature.
     * Suspends until the person confirms or cancels/fails.
     */
    suspend fun signWithBiometricConfirmation(
        activity: FragmentActivity,
        canonicalPayloadJson: String,
        title: String = "Confirm ledger entry",
        subtitle: String? = null,
    ): String = suspendCoroutine { cont ->
        val signature = Signature.getInstance("SHA256withECDSA").apply {
            initSign(keyStore.getKey(keyAlias, null) as java.security.PrivateKey)
        }
        val cryptoObject = BiometricPrompt.CryptoObject(signature)

        val promptInfo = BiometricPrompt.PromptInfo.Builder()
            .setTitle(title)
            .apply { subtitle?.let { setSubtitle(it) } }
            .setNegativeButtonText("Cancel")
            .setAllowedAuthenticators(androidx.biometric.BiometricManager.Authenticators.BIOMETRIC_STRONG)
            .build()

        val callback = object : BiometricPrompt.AuthenticationCallback() {
            override fun onAuthenticationSucceeded(result: BiometricPrompt.AuthenticationResult) {
                try {
                    val signedBytes = result.cryptoObject!!.signature!!.run {
                        update(canonicalPayloadJson.toByteArray(Charsets.UTF_8))
                        sign()
                    }
                    cont.resume(Base64.encodeToString(signedBytes, Base64.NO_WRAP))
                } catch (e: Exception) {
                    cont.resumeWithException(e)
                }
            }

            override fun onAuthenticationError(errorCode: Int, errString: CharSequence) {
                cont.resumeWithException(
                    BiometricSignException("Biometric confirmation failed: $errString")
                )
            }

            override fun onAuthenticationFailed() {
                // A single non-matching attempt — BiometricPrompt keeps
                // listening, so we don't resume/cancel the coroutine here.
            }
        }

        val prompt = BiometricPrompt(
            activity,
            androidx.core.content.ContextCompat.getMainExecutor(activity),
            callback,
        )
        prompt.authenticate(promptInfo, cryptoObject)
    }
}

class BiometricSignException(message: String) : Exception(message)
