package com.anrixa.voiceledger.network

import okhttp3.MediaType.Companion.toMediaType
import okhttp3.MultipartBody
import okhttp3.OkHttpClient
import okhttp3.RequestBody.Companion.toRequestBody
import okhttp3.ResponseBody
import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory
import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.Multipart
import retrofit2.http.POST
import retrofit2.http.Part
import retrofit2.http.Query
import retrofit2.http.Streaming
import java.io.File
import java.util.concurrent.TimeUnit

// ---- request/response bodies (mirrors app/models.py on the server) ----

data class PairStartResponse(val pairing_code: String, val expires_in: Int)
data class PairCompleteRequest(val pairing_code: String, val label: String, val public_key_pem: String)
data class PairCompleteResponse(val device_id: String)

data class SttResponse(val transcript: String)

data class TransactionInBody(
    val device_id: String,
    val payload_json: String,
    val signature_b64: String,
)

data class TransactionOut(
    val id: String,
    val counterparty_name: String,
    val place: String?,
    val amount_paid: Double?,
    val amount_paid_currency: String?,
    val amount_due: Double?,
    val amount_due_currency: String?,
    val due_date: String?,
    val transaction_date: String?,
    val created_at: String,
)

interface VoiceLedgerApi {
    @POST("pair/start")
    suspend fun pairStart(): PairStartResponse

    @POST("pair/complete")
    suspend fun pairComplete(@Body req: PairCompleteRequest): PairCompleteResponse

    @Multipart
    @POST("stt")
    suspend fun speechToText(@Part audio: MultipartBody.Part): SttResponse

    @POST("nlu/guided-field")
    suspend fun guidedField(
        @Query("field") field: String,
        @Query("transcript") transcript: String,
    ): Map<String, Any?>

    @Streaming
    @GET("tts")
    suspend fun textToSpeech(@Query("text") text: String): ResponseBody

    @POST("transactions")
    suspend fun submitTransaction(@Body body: TransactionInBody): TransactionOut

    @GET("transactions")
    suspend fun listTransactions(): List<TransactionOut>
}

/**
 * `baseUrl` is the LAN address entered (or discovered) in Settings —
 * e.g. "http://192.168.1.42:8420/". Rebuild this whenever that
 * address changes; there's no DNS to fall back on, it's just an IP.
 */
object ApiClientFactory {
    fun create(baseUrl: String): VoiceLedgerApi {
        val client = OkHttpClient.Builder()
            .connectTimeout(5, TimeUnit.SECONDS)
            .readTimeout(30, TimeUnit.SECONDS) // STT can take a few seconds on CPU
            .build()

        return Retrofit.Builder()
            .baseUrl(baseUrl)
            .client(client)
            .addConverterFactory(GsonConverterFactory.create())
            .build()
            .create(VoiceLedgerApi::class.java)
    }
}

fun audioFilePart(file: File): MultipartBody.Part {
    val body = file.asRequestBody("audio/wav".toMediaType())
    return MultipartBody.Part.createFormData("audio", file.name, body)
}

private fun File.asRequestBody(mediaType: okhttp3.MediaType) =
    this.readBytes().toRequestBody(mediaType)
