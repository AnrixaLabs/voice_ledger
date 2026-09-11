package com.anrixa.voiceledger.audio

import android.media.AudioFormat
import android.media.AudioRecord
import android.media.MediaRecorder
import java.io.File
import java.io.FileOutputStream
import java.io.RandomAccessFile
import kotlin.concurrent.thread

/**
 * Records raw PCM straight to a WAV file at 16kHz/mono/16-bit — the
 * format both faster-whisper and Azure Speech expect, so the server
 * never has to transcode anything.
 */
class AudioRecorder(private val outputDir: File) {

    private var audioRecord: AudioRecord? = null
    private var recordingThread: Thread? = null
    @Volatile private var isRecording = false

    private val sampleRate = 16_000
    private val channelConfig = AudioFormat.CHANNEL_IN_MONO
    private val audioFormat = AudioFormat.ENCODING_PCM_16BIT

    fun start(): File {
        val pcmFile = File.createTempFile("rec_", ".pcm", outputDir)
        check(audioRecord == null) { "Recording is already in progress." }
        val minBufSize = AudioRecord.getMinBufferSize(sampleRate, channelConfig, audioFormat)
        check(minBufSize > 0) { "This device does not support 16 kHz mono PCM recording." }
        val record = AudioRecord(
            MediaRecorder.AudioSource.MIC, sampleRate, channelConfig, audioFormat, minBufSize * 2
        )
        check(record.state == AudioRecord.STATE_INITIALIZED) { "Could not initialize the microphone." }
        audioRecord = record
        isRecording = true
        record.startRecording()

        recordingThread = thread(start = true) {
            val buffer = ByteArray(minBufSize)
            FileOutputStream(pcmFile).use { out ->
                while (isRecording) {
                    val read = record.read(buffer, 0, buffer.size)
                    if (read > 0) out.write(buffer, 0, read)
                }
            }
        }
        return pcmFile
    }

    /** Stops recording and returns a playable/uploadable .wav file. */
    fun stop(pcmFile: File): File {
        isRecording = false
        // Stop first so a blocking AudioRecord.read() wakes up, then wait for
        // the writer thread to finish before releasing the recorder.
        runCatching { audioRecord?.stop() }
        recordingThread?.join(2_000)
        recordingThread = null
        audioRecord?.release()
        audioRecord = null

        val wavFile = File(outputDir, "entry_${System.currentTimeMillis()}.wav")
        writeWavHeader(pcmFile, wavFile, sampleRate, channels = 1, bitsPerSample = 16)
        pcmFile.delete()
        return wavFile
    }

    private fun writeWavHeader(pcmFile: File, wavFile: File, sampleRate: Int, channels: Int, bitsPerSample: Int) {
        val pcmData = pcmFile.readBytes()
        val byteRate = sampleRate * channels * bitsPerSample / 8
        val blockAlign = channels * bitsPerSample / 8
        val dataSize = pcmData.size
        val chunkSize = 36 + dataSize

        RandomAccessFile(wavFile, "rw").use { raf ->
            raf.setLength(0)
            raf.writeBytes("RIFF")
            raf.write(intToLE(chunkSize))
            raf.writeBytes("WAVE")
            raf.writeBytes("fmt ")
            raf.write(intToLE(16)) // PCM fmt chunk size
            raf.write(shortToLE(1)) // audio format = PCM
            raf.write(shortToLE(channels.toShort()))
            raf.write(intToLE(sampleRate))
            raf.write(intToLE(byteRate))
            raf.write(shortToLE(blockAlign.toShort()))
            raf.write(shortToLE(bitsPerSample.toShort()))
            raf.writeBytes("data")
            raf.write(intToLE(dataSize))
            raf.write(pcmData)
        }
    }

    private fun intToLE(v: Int): ByteArray = byteArrayOf(
        (v and 0xff).toByte(), ((v shr 8) and 0xff).toByte(),
        ((v shr 16) and 0xff).toByte(), ((v shr 24) and 0xff).toByte(),
    )

    private fun shortToLE(v: Short): ByteArray = byteArrayOf(
        (v.toInt() and 0xff).toByte(), ((v.toInt() shr 8) and 0xff).toByte(),
    )
}
