import Foundation

public enum AutoCrabCameraCommand: String, Codable, Sendable {
    case list = "camera.list"
    case snap = "camera.snap"
    case clip = "camera.clip"
}

public enum AutoCrabCameraFacing: String, Codable, Sendable {
    case back
    case front
}

public enum AutoCrabCameraImageFormat: String, Codable, Sendable {
    case jpg
    case jpeg
}

public enum AutoCrabCameraVideoFormat: String, Codable, Sendable {
    case mp4
}

public struct AutoCrabCameraSnapParams: Codable, Sendable, Equatable {
    public var facing: AutoCrabCameraFacing?
    public var maxWidth: Int?
    public var quality: Double?
    public var format: AutoCrabCameraImageFormat?
    public var deviceId: String?
    public var delayMs: Int?

    public init(
        facing: AutoCrabCameraFacing? = nil,
        maxWidth: Int? = nil,
        quality: Double? = nil,
        format: AutoCrabCameraImageFormat? = nil,
        deviceId: String? = nil,
        delayMs: Int? = nil)
    {
        self.facing = facing
        self.maxWidth = maxWidth
        self.quality = quality
        self.format = format
        self.deviceId = deviceId
        self.delayMs = delayMs
    }
}

public struct AutoCrabCameraClipParams: Codable, Sendable, Equatable {
    public var facing: AutoCrabCameraFacing?
    public var durationMs: Int?
    public var includeAudio: Bool?
    public var format: AutoCrabCameraVideoFormat?
    public var deviceId: String?

    public init(
        facing: AutoCrabCameraFacing? = nil,
        durationMs: Int? = nil,
        includeAudio: Bool? = nil,
        format: AutoCrabCameraVideoFormat? = nil,
        deviceId: String? = nil)
    {
        self.facing = facing
        self.durationMs = durationMs
        self.includeAudio = includeAudio
        self.format = format
        self.deviceId = deviceId
    }
}
