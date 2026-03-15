import Foundation

public enum AutoCrabChatTransportEvent: Sendable {
    case health(ok: Bool)
    case tick
    case chat(AutoCrabChatEventPayload)
    case agent(AutoCrabAgentEventPayload)
    case seqGap
}

public protocol AutoCrabChatTransport: Sendable {
    func requestHistory(sessionKey: String) async throws -> AutoCrabChatHistoryPayload
    func sendMessage(
        sessionKey: String,
        message: String,
        thinking: String,
        idempotencyKey: String,
        attachments: [AutoCrabChatAttachmentPayload]) async throws -> AutoCrabChatSendResponse

    func abortRun(sessionKey: String, runId: String) async throws
    func listSessions(limit: Int?) async throws -> AutoCrabChatSessionsListResponse

    func requestHealth(timeoutMs: Int) async throws -> Bool
    func events() -> AsyncStream<AutoCrabChatTransportEvent>

    func setActiveSessionKey(_ sessionKey: String) async throws
}

extension AutoCrabChatTransport {
    public func setActiveSessionKey(_: String) async throws {}

    public func abortRun(sessionKey _: String, runId _: String) async throws {
        throw NSError(
            domain: "AutoCrabChatTransport",
            code: 0,
            userInfo: [NSLocalizedDescriptionKey: "chat.abort not supported by this transport"])
    }

    public func listSessions(limit _: Int?) async throws -> AutoCrabChatSessionsListResponse {
        throw NSError(
            domain: "AutoCrabChatTransport",
            code: 0,
            userInfo: [NSLocalizedDescriptionKey: "sessions.list not supported by this transport"])
    }
}
