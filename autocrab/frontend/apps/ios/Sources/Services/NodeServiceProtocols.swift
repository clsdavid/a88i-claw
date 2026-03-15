import CoreLocation
import Foundation
import AutoCrabKit
import UIKit

typealias AutoCrabCameraSnapResult = (format: String, base64: String, width: Int, height: Int)
typealias AutoCrabCameraClipResult = (format: String, base64: String, durationMs: Int, hasAudio: Bool)

protocol CameraServicing: Sendable {
    func listDevices() async -> [CameraController.CameraDeviceInfo]
    func snap(params: AutoCrabCameraSnapParams) async throws -> AutoCrabCameraSnapResult
    func clip(params: AutoCrabCameraClipParams) async throws -> AutoCrabCameraClipResult
}

protocol ScreenRecordingServicing: Sendable {
    func record(
        screenIndex: Int?,
        durationMs: Int?,
        fps: Double?,
        includeAudio: Bool?,
        outPath: String?) async throws -> String
}

@MainActor
protocol LocationServicing: Sendable {
    func authorizationStatus() -> CLAuthorizationStatus
    func accuracyAuthorization() -> CLAccuracyAuthorization
    func ensureAuthorization(mode: AutoCrabLocationMode) async -> CLAuthorizationStatus
    func currentLocation(
        params: AutoCrabLocationGetParams,
        desiredAccuracy: AutoCrabLocationAccuracy,
        maxAgeMs: Int?,
        timeoutMs: Int?) async throws -> CLLocation
    func startLocationUpdates(
        desiredAccuracy: AutoCrabLocationAccuracy,
        significantChangesOnly: Bool) -> AsyncStream<CLLocation>
    func stopLocationUpdates()
    func startMonitoringSignificantLocationChanges(onUpdate: @escaping @Sendable (CLLocation) -> Void)
    func stopMonitoringSignificantLocationChanges()
}

@MainActor
protocol DeviceStatusServicing: Sendable {
    func status() async throws -> AutoCrabDeviceStatusPayload
    func info() -> AutoCrabDeviceInfoPayload
}

protocol PhotosServicing: Sendable {
    func latest(params: AutoCrabPhotosLatestParams) async throws -> AutoCrabPhotosLatestPayload
}

protocol ContactsServicing: Sendable {
    func search(params: AutoCrabContactsSearchParams) async throws -> AutoCrabContactsSearchPayload
    func add(params: AutoCrabContactsAddParams) async throws -> AutoCrabContactsAddPayload
}

protocol CalendarServicing: Sendable {
    func events(params: AutoCrabCalendarEventsParams) async throws -> AutoCrabCalendarEventsPayload
    func add(params: AutoCrabCalendarAddParams) async throws -> AutoCrabCalendarAddPayload
}

protocol RemindersServicing: Sendable {
    func list(params: AutoCrabRemindersListParams) async throws -> AutoCrabRemindersListPayload
    func add(params: AutoCrabRemindersAddParams) async throws -> AutoCrabRemindersAddPayload
}

protocol MotionServicing: Sendable {
    func activities(params: AutoCrabMotionActivityParams) async throws -> AutoCrabMotionActivityPayload
    func pedometer(params: AutoCrabPedometerParams) async throws -> AutoCrabPedometerPayload
}

struct WatchMessagingStatus: Sendable, Equatable {
    var supported: Bool
    var paired: Bool
    var appInstalled: Bool
    var reachable: Bool
    var activationState: String
}

struct WatchQuickReplyEvent: Sendable, Equatable {
    var replyId: String
    var promptId: String
    var actionId: String
    var actionLabel: String?
    var sessionKey: String?
    var note: String?
    var sentAtMs: Int?
    var transport: String
}

struct WatchNotificationSendResult: Sendable, Equatable {
    var deliveredImmediately: Bool
    var queuedForDelivery: Bool
    var transport: String
}

protocol WatchMessagingServicing: AnyObject, Sendable {
    func status() async -> WatchMessagingStatus
    func setReplyHandler(_ handler: (@Sendable (WatchQuickReplyEvent) -> Void)?)
    func sendNotification(
        id: String,
        params: AutoCrabWatchNotifyParams) async throws -> WatchNotificationSendResult
}

extension CameraController: CameraServicing {}
extension ScreenRecordService: ScreenRecordingServicing {}
extension LocationService: LocationServicing {}
