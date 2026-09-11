import Foundation
import AVFoundation
import ImageIO
import UniformTypeIdentifiers

@main struct InspectVideo {
    static func main() async throws {
        let args = CommandLine.arguments
        let asset = AVURLAsset(url: URL(fileURLWithPath: args[1]))
        let duration = try await asset.load(.duration)
        let tracks = try await asset.loadTracks(withMediaType: .video)
        print("duration_seconds=\(duration.seconds), size=\(try await tracks[0].load(.naturalSize))")
        let generator = AVAssetImageGenerator(asset: asset)
        generator.appliesPreferredTrackTransform = true
        generator.requestedTimeToleranceBefore = .zero
        generator.requestedTimeToleranceAfter = .zero
        let sample = try await generator.image(at: CMTime(seconds: Double(args[3])!, preferredTimescale: 600))
        let image = sample.image
        print("sample_time_seconds=\(sample.actualTime.seconds)")
        let destination = CGImageDestinationCreateWithURL(URL(fileURLWithPath: args[2]) as CFURL, UTType.png.identifier as CFString, 1, nil)!
        CGImageDestinationAddImage(destination, image, nil)
        guard CGImageDestinationFinalize(destination) else { fatalError("Could not save video frame") }
    }
}
