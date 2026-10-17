import { useCallback, useEffect, useRef, useState, useSyncExternalStore } from "react";
import { encodeWav } from "@/lib/wav";

const MAX_SECONDS = 60;

const WORKLET = `
class PcmCapture extends AudioWorkletProcessor {
    process(inputs) {
        const channel = inputs[0] && inputs[0][0];
        if (channel) this.port.postMessage(channel.slice(0));
        return true;
    }
}
registerProcessor("pcm-capture", PcmCapture);
`;

type AudioContextCtor = typeof AudioContext;

function audioContextCtor(): AudioContextCtor | undefined {
    return window.AudioContext ?? (window as unknown as { webkitAudioContext?: AudioContextCtor }).webkitAudioContext;
}

function isSupported(): boolean {
    return typeof window !== "undefined"
        && window.isSecureContext
        && !!navigator.mediaDevices?.getUserMedia
        && typeof AudioWorkletNode !== "undefined"
        && !!audioContextCtor();
}

const subscribe = () => () => { };

type Session = {
    stream: MediaStream,
    context: AudioContext,
    source: MediaStreamAudioSourceNode,
    node: AudioWorkletNode,
    gain: GainNode,
    chunks: Float32Array[],
    samples: number
};

export type Recording = {
    wav: Blob,
    durationMs: number
};

function teardown(session: Session) {
    session.node.port.onmessage = null;
    session.stream.getTracks().forEach(t => t.stop());
    try {
        session.source.disconnect();
        session.node.disconnect();
        session.gain.disconnect();
    } catch { }
    session.context.close().catch(() => { });
}

/**
 * Records microphone audio as WAV. `supported` is false where WAV cannot be produced (no secure context, microphone or Web Audio worklets).
 * Only the first minute of a recording is kept.
 */
export function useRecorder() {
    const supported = useSyncExternalStore(subscribe, isSupported, () => false);
    const [recording, setRecording] = useState(false);
    const wanted = useRef(false);
    const session = useRef<Session | null>(null);
    const starting = useRef<Promise<void> | null>(null);
    const generation = useRef(0);

    const run = useCallback(async (id: number) => {
        const alive = () => wanted.current && generation.current === id;

        const stream = await navigator.mediaDevices.getUserMedia({ audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true } });
        if (!alive()) {
            stream.getTracks().forEach(t => t.stop());
            return;
        }

        const context = new (audioContextCtor()!)();
        try {
            await context.resume();
            const url = URL.createObjectURL(new Blob([WORKLET], { type: "text/javascript" }));
            try {
                await context.audioWorklet.addModule(url);
            } finally {
                URL.revokeObjectURL(url);
            }

            const source = context.createMediaStreamSource(stream);
            const node = new AudioWorkletNode(context, "pcm-capture");
            const gain = context.createGain();
            gain.gain.value = 0;
            const created: Session = { stream, context, source, node, gain, chunks: [], samples: 0 };

            node.port.onmessage = (e: MessageEvent<Float32Array>) => {
                if (created.samples >= MAX_SECONDS * context.sampleRate) return;
                created.chunks.push(e.data);
                created.samples += e.data.length;
            };
            source.connect(node);
            node.connect(gain);
            gain.connect(context.destination);

            if (!alive()) {
                teardown(created);
                return;
            }
            session.current = created;
        } catch (e) {
            stream.getTracks().forEach(t => t.stop());
            context.close().catch(() => { });
            throw e;
        }
    }, []);

    const start = useCallback((): Promise<void> => {
        if (wanted.current) return Promise.resolve();

        wanted.current = true;
        setRecording(true);
        const id = ++generation.current;
        const promise = run(id).catch(e => {
            if (generation.current === id) {
                wanted.current = false;
                setRecording(false);
            }
            throw e;
        });
        starting.current = promise;
        return promise;
    }, [run]);

    const stop = useCallback(async (): Promise<Recording | null> => {
        if (!wanted.current) return null;

        wanted.current = false;
        setRecording(false);
        await starting.current?.catch(() => { });

        const current = session.current;
        session.current = null;
        if (!current) return null;

        const { chunks, samples, context } = current;
        const rate = context.sampleRate;
        teardown(current);
        return { wav: encodeWav(chunks, rate), durationMs: samples / rate * 1000 };
    }, []);

    useEffect(() => () => {
        wanted.current = false;
        if (session.current) {
            teardown(session.current);
            session.current = null;
        }
    }, []);

    return { supported, recording, start, stop };
}
