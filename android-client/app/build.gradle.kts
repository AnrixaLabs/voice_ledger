import java.util.Properties

plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
    id("org.jetbrains.kotlin.plugin.compose")
}

// Release signing: reads from environment variables first (that's how
// the CI workflow at .github/workflows/android-build.yml passes in
// your keystore), falling back to a local keystore.properties file
// for building a signed release on your own machine. Neither the
// keystore nor these values are ever meant to be committed - see
// keystore.properties.example and android-client/README.md.
val keystorePropsFile = rootProject.file("keystore.properties")
val keystoreProps = Properties().apply {
    if (keystorePropsFile.exists()) load(keystorePropsFile.inputStream())
}
fun signingValue(propKey: String, envKey: String): String? =
    (keystoreProps.getProperty(propKey) ?: System.getenv(envKey))?.takeIf { it.isNotBlank() }

val hasReleaseSigningConfig = signingValue("storePassword", "VOICE_LEDGER_KEYSTORE_PASSWORD") != null

android {
    namespace = "com.anrixa.voiceledger"
    compileSdk = 34

    defaultConfig {
        applicationId = "com.anrixa.voiceledger"
        // minSdk 26: Android Keystore's setUnlockedDeviceRequired and the
        // modern BiometricPrompt CryptoObject flow are reliable from here
        // on. Samsung A-series phones from the last ~5 years all clear
        // this easily, so we don't lose real-world reach by not going lower.
        minSdk = 26
        targetSdk = 34
        versionCode = 1
        versionName = "0.1.0"
    }

    signingConfigs {
        if (hasReleaseSigningConfig) {
            create("release") {
                storeFile = file(
                    signingValue("storeFile", "VOICE_LEDGER_KEYSTORE_PATH") ?: "release.keystore"
                )
                storePassword = signingValue("storePassword", "VOICE_LEDGER_KEYSTORE_PASSWORD")
                keyAlias = signingValue("keyAlias", "VOICE_LEDGER_KEY_ALIAS")
                keyPassword = signingValue("keyPassword", "VOICE_LEDGER_KEY_PASSWORD")
            }
        }
    }

    buildTypes {
        release {
            isMinifyEnabled = false
            if (hasReleaseSigningConfig) {
                signingConfig = signingConfigs.getByName("release")
            }
            // Without a keystore configured, `gradle assembleRelease` still
            // succeeds but produces an UNSIGNED apk you can't install as-is -
            // that's deliberate (see android-client/README.md) rather than
            // falling back to a debug key for a build type meant for
            // distribution.
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions {
        jvmTarget = "17"
    }

    buildFeatures {
        compose = true
    }
}

dependencies {
    implementation("androidx.core:core-ktx:1.13.1")
    implementation("androidx.lifecycle:lifecycle-runtime-ktx:2.8.4")
    implementation("androidx.activity:activity-compose:1.9.1")

    // Deliberately plain Material 3 components, no custom animation
    // libraries or heavy image loaders — keeps the app light on
    // mid-range (A-series, not flagship) hardware.
    val composeBom = platform("androidx.compose:compose-bom:2024.06.00")
    implementation(composeBom)
    implementation("androidx.compose.ui:ui")
    implementation("androidx.compose.material3:material3")
    implementation("androidx.compose.material:material-icons-core")
    implementation("androidx.compose.material:material-icons-extended") // Mic icon used by the recording UI
    implementation("androidx.compose.ui:ui-tooling-preview")
    implementation("androidx.navigation:navigation-compose:2.7.7")
    implementation("androidx.lifecycle:lifecycle-viewmodel-compose:2.8.4")

    // Biometric-gated Keystore signing (the "confirmed by fingerprint" step)
    implementation("androidx.biometric:biometric:1.1.0")

    // Talking to the local server
    implementation("com.squareup.retrofit2:retrofit:2.11.0")
    implementation("com.squareup.retrofit2:converter-gson:2.11.0")
    implementation("com.squareup.okhttp3:okhttp:4.12.0")

    implementation("androidx.datastore:datastore-preferences:1.1.1") // server address, device id

    testImplementation("junit:junit:4.13.2")
    androidTestImplementation("androidx.compose.ui:ui-test-junit4")
}
