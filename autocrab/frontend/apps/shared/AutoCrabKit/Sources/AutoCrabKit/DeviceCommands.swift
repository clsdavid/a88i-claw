import Foundation

public enum AutoCrabDeviceCommand: String, Codable, Sendable {
    case status = "device.status"
    case info = "device.info"
}

public enum AutoCrabBatteryState: String, Codable, Sendable {
    case unknown
    case unplugged
    case charging
    case full
}

public enum AutoCrabThermalState: String, Codable, Sendable {
    case nominal
    case fair
    case serious
    case critical
}

public enum AutoCrabNetworkPathStatus: String, Codable, Sendable {
    case satisfied
    case unsatisfied
    case requiresConnection
}

public enum AutoCrabNetworkInterfaceType: String, Codable, Sendable {
    case wifi
    case cellular
    case wired
    case other
}

public struct AutoCrabBatteryStatusPayload: Codable, Sendable, Equatable {
    public var level: Double?
    public var state: AutoCrabBatteryState
    public var lowPowerModeEnabled: Bool

    public init(level: Double?, state: AutoCrabBatteryState, lowPowerModeEnabled: Bool) {
        self.level = level
        self.state = state
        self.lowPowerModeEnabled = lowPowerModeEnabled
    }
}

public struct AutoCrabThermalStatusPayload: Codable, Sendable, Equatable {
    public var state: AutoCrabThermalState

    public init(state: AutoCrabThermalState) {
        self.state = state
    }
}

public struct AutoCrabStorageStatusPayload: Codable, Sendable, Equatable {
    public var totalBytes: Int64
    public var freeBytes: Int64
    public var usedBytes: Int64

    public init(totalBytes: Int64, freeBytes: Int64, usedBytes: Int64) {
        self.totalBytes = totalBytes
        self.freeBytes = freeBytes
        self.usedBytes = usedBytes
    }
}

public struct AutoCrabNetworkStatusPayload: Codable, Sendable, Equatable {
    public var status: AutoCrabNetworkPathStatus
    public var isExpensive: Bool
    public var isConstrained: Bool
    public var interfaces: [AutoCrabNetworkInterfaceType]

    public init(
        status: AutoCrabNetworkPathStatus,
        isExpensive: Bool,
        isConstrained: Bool,
        interfaces: [AutoCrabNetworkInterfaceType])
    {
        self.status = status
        self.isExpensive = isExpensive
        self.isConstrained = isConstrained
        self.interfaces = interfaces
    }
}

public struct AutoCrabDeviceStatusPayload: Codable, Sendable, Equatable {
    public var battery: AutoCrabBatteryStatusPayload
    public var thermal: AutoCrabThermalStatusPayload
    public var storage: AutoCrabStorageStatusPayload
    public var network: AutoCrabNetworkStatusPayload
    public var uptimeSeconds: Double

    public init(
        battery: AutoCrabBatteryStatusPayload,
        thermal: AutoCrabThermalStatusPayload,
        storage: AutoCrabStorageStatusPayload,
        network: AutoCrabNetworkStatusPayload,
        uptimeSeconds: Double)
    {
        self.battery = battery
        self.thermal = thermal
        self.storage = storage
        self.network = network
        self.uptimeSeconds = uptimeSeconds
    }
}

public struct AutoCrabDeviceInfoPayload: Codable, Sendable, Equatable {
    public var deviceName: String
    public var modelIdentifier: String
    public var systemName: String
    public var systemVersion: String
    public var appVersion: String
    public var appBuild: String
    public var locale: String

    public init(
        deviceName: String,
        modelIdentifier: String,
        systemName: String,
        systemVersion: String,
        appVersion: String,
        appBuild: String,
        locale: String)
    {
        self.deviceName = deviceName
        self.modelIdentifier = modelIdentifier
        self.systemName = systemName
        self.systemVersion = systemVersion
        self.appVersion = appVersion
        self.appBuild = appBuild
        self.locale = locale
    }
}
