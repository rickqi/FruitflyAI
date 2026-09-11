import Foundation
import ScreenCaptureKit
import AVFoundation

// Native macOS capture. Only the two selected project windows are included;
// other apps, desktop, menu bar, microphone and system audio are excluded.
final class RecordingDelegate: NSObject, SCRecordingOutputDelegate {
    var finished = false
    var failure: Error?
    func recordingOutputDidStartRecording(_ recordingOutput: SCRecordingOutput) {
        print("Recording started"); fflush(stdout)
    }
    func recordingOutputDidFinishRecording(_ recordingOutput: SCRecordingOutput) {
        finished = true
    }
    func recordingOutput(_ recordingOutput: SCRecordingOutput, didFailWithError error: Error) {
        failure = error; finished = true
    }
}

@main struct Recorder {
    static func main() async throws {
        guard CommandLine.arguments.count == 5,
              let gamePID = Int32(CommandLine.arguments[1]),
              let chromePID = Int32(CommandLine.arguments[2]),
              let seconds = Double(CommandLine.arguments[4]) else {
            fatalError("usage: record-windows GAME_PID DASHBOARD_PID output.mp4 seconds")
        }
        let content = try await SCShareableContent.excludingDesktopWindows(true, onScreenWindowsOnly: false)
        let windows = content.windows.filter {
            (($0.owningApplication?.processID == gamePID && $0.title == "Super Mario 64 EX (OpenGL)") ||
             ($0.owningApplication?.processID == chromePID && $0.title == "Fly64 Neural Observatory")) &&
            $0.frame.width > 200 && $0.frame.height > 200
        }
        guard windows.count == 2, let display = content.displays.first(where: { $0.displayID == CGMainDisplayID() }) else {
            fatalError("Expected exactly two Fly64 windows; found \(windows.map { $0.title ?? "untitled" })")
        }
        let filter = SCContentFilter(display: display, including: windows)
        let config = SCStreamConfiguration()
        config.width = 1470; config.height = 956
        config.minimumFrameInterval = CMTime(value: 1, timescale: 30)
        config.showsCursor = false; config.capturesAudio = false
        let background = CGColor(red: 0.02, green: 0.04, blue: 0.05, alpha: 1)
        config.backgroundColor = background
        let stream = SCStream(filter: filter, configuration: config, delegate: nil)
        let outputConfig = SCRecordingOutputConfiguration()
        outputConfig.outputURL = URL(fileURLWithPath: CommandLine.arguments[3])
        outputConfig.outputFileType = .mp4; outputConfig.videoCodecType = .h264
        let delegate = RecordingDelegate()
        let output = SCRecordingOutput(configuration: outputConfig, delegate: delegate)
        try stream.addRecordingOutput(output)
        print("Selected project windows: \(windows.map { $0.title ?? "game" })"); fflush(stdout)
        try await stream.startCapture()
        try await Task.sleep(nanoseconds: UInt64(seconds * 1_000_000_000))
        try await stream.stopCapture()
        for _ in 0..<100 where !delegate.finished {
            try await Task.sleep(nanoseconds: 100_000_000)
        }
        if let failure = delegate.failure { throw failure }
        guard delegate.finished else { fatalError("Recording finalization timed out") }
        print("Saved \(outputConfig.outputURL.path)")
        withExtendedLifetime(background) {}
    }
}
