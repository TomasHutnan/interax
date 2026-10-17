/**
 * Encodes the mono samples (-1 to 1) as a 16-bit PCM WAV, downsampled to `targetRate` if the input rate is higher.
 */
export function encodeWav(chunks: Float32Array[], inputRate: number, targetRate: number = 16000): Blob {
    const length = chunks.reduce((sum, c) => sum + c.length, 0);
    const input = new Float32Array(length);
    let offset = 0;
    for (const chunk of chunks) {
        input.set(chunk, offset);
        offset += chunk.length;
    }

    const rate = Math.min(inputRate, targetRate);
    const ratio = inputRate / rate;
    const count = Math.floor(length / ratio);
    const buffer = new ArrayBuffer(44 + count * 2);
    const view = new DataView(buffer);

    const text = (at: number, value: string) => {
        for (let i = 0; i < value.length; i++)
            view.setUint8(at + i, value.charCodeAt(i));
    };

    text(0, "RIFF");
    view.setUint32(4, 36 + count * 2, true);
    text(8, "WAVE");
    text(12, "fmt ");
    view.setUint32(16, 16, true);
    view.setUint16(20, 1, true); // PCM
    view.setUint16(22, 1, true); // mono
    view.setUint32(24, Math.round(rate), true);
    view.setUint32(28, Math.round(rate) * 2, true);
    view.setUint16(32, 2, true);
    view.setUint16(34, 16, true);
    text(36, "data");
    view.setUint32(40, count * 2, true);

    for (let i = 0; i < count; i++) {
        // average the input samples that fall into this output sample
        const start = Math.floor(i * ratio);
        const end = Math.max(start + 1, Math.min(length, Math.floor((i + 1) * ratio)));
        let sum = 0;
        for (let j = start; j < end; j++)
            sum += input[j];

        const sample = Math.max(-1, Math.min(1, sum / (end - start)));
        view.setInt16(44 + i * 2, sample < 0 ? sample * 0x8000 : sample * 0x7fff, true);
    }

    return new Blob([buffer], { type: "audio/wav" });
}
