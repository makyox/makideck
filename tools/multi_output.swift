// Create a Multi-Output Device "Deck Output" (speakers + BlackHole 2ch) and make
// it the default output, so makideck's audio analyzer hears what's playing.
//   swift tools/multi_output.swift ["MacBook Pro Speakers"]
// Undo: pick your speakers in Sound settings and delete "Deck Output" in
// Audio MIDI Setup.
import CoreAudio
import Foundation

func prop(_ sel: AudioObjectPropertySelector, _ scope: AudioObjectPropertyScope = kAudioObjectPropertyScopeGlobal) -> AudioObjectPropertyAddress {
    AudioObjectPropertyAddress(mSelector: sel, mScope: scope, mElement: kAudioObjectPropertyElementMain)
}

func devices() -> [AudioDeviceID] {
    var addr = prop(kAudioHardwarePropertyDevices)
    var size: UInt32 = 0
    AudioObjectGetPropertyDataSize(AudioObjectID(kAudioObjectSystemObject), &addr, 0, nil, &size)
    var ids = [AudioDeviceID](repeating: 0, count: Int(size) / MemoryLayout<AudioDeviceID>.size)
    AudioObjectGetPropertyData(AudioObjectID(kAudioObjectSystemObject), &addr, 0, nil, &size, &ids)
    return ids
}

func string(_ id: AudioDeviceID, _ sel: AudioObjectPropertySelector) -> String {
    var addr = prop(sel)
    var value: Unmanaged<CFString>?
    var size = UInt32(MemoryLayout<Unmanaged<CFString>?>.size)
    guard AudioObjectGetPropertyData(id, &addr, 0, nil, &size, &value) == noErr, let v = value else { return "" }
    return v.takeRetainedValue() as String
}

let speakersName = CommandLine.arguments.count > 1 ? CommandLine.arguments[1] : "MacBook Pro Speakers"
let all = devices()
if let existing = all.first(where: { string($0, kAudioObjectPropertyName) == "Deck Output" }) {
    print("Deck Output already exists (id \(existing)) — setting as default")
    var id = existing
    var addr = prop(kAudioHardwarePropertyDefaultOutputDevice)
    AudioObjectSetPropertyData(AudioObjectID(kAudioObjectSystemObject), &addr, 0, nil, UInt32(MemoryLayout<AudioDeviceID>.size), &id)
    exit(0)
}
guard let speakers = all.first(where: { string($0, kAudioObjectPropertyName) == speakersName }),
      let blackhole = all.first(where: { string($0, kAudioObjectPropertyName).hasPrefix("BlackHole") }) else {
    print("speakers '\(speakersName)' or BlackHole not found"); exit(1)
}
let spkUID = string(speakers, kAudioDevicePropertyDeviceUID)
let bhUID = string(blackhole, kAudioDevicePropertyDeviceUID)

let desc: [String: Any] = [
    kAudioAggregateDeviceNameKey: "Deck Output",
    kAudioAggregateDeviceUIDKey: "io.github.makyox.makideck.multi-output",
    kAudioAggregateDeviceIsStackedKey: 1,               // multi-output, not aggregate
    kAudioAggregateDeviceMainSubDeviceKey: spkUID,      // clock source = speakers
    kAudioAggregateDeviceSubDeviceListKey: [
        [kAudioSubDeviceUIDKey: spkUID],
        [kAudioSubDeviceUIDKey: bhUID, kAudioSubDeviceDriftCompensationKey: 1],
    ],
]
var agg: AudioDeviceID = 0
let err = AudioHardwareCreateAggregateDevice(desc as CFDictionary, &agg)
guard err == noErr else { print("create failed: \(err)"); exit(1) }
Thread.sleep(forTimeInterval: 0.5)
var addr = prop(kAudioHardwarePropertyDefaultOutputDevice)
let set = AudioObjectSetPropertyData(AudioObjectID(kAudioObjectSystemObject), &addr, 0, nil, UInt32(MemoryLayout<AudioDeviceID>.size), &agg)
print("created Deck Output (id \(agg)): \(speakersName) + BlackHole; default output set: \(set == noErr)")
