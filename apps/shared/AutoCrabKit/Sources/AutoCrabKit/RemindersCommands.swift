import Foundation

public enum AutoCrabRemindersCommand: String, Codable, Sendable {
    case list = "reminders.list"
    case add = "reminders.add"
}

public enum AutoCrabReminderStatusFilter: String, Codable, Sendable {
    case incomplete
    case completed
    case all
}

public struct AutoCrabRemindersListParams: Codable, Sendable, Equatable {
    public var status: AutoCrabReminderStatusFilter?
    public var limit: Int?

    public init(status: AutoCrabReminderStatusFilter? = nil, limit: Int? = nil) {
        self.status = status
        self.limit = limit
    }
}

public struct AutoCrabRemindersAddParams: Codable, Sendable, Equatable {
    public var title: String
    public var dueISO: String?
    public var notes: String?
    public var listId: String?
    public var listName: String?

    public init(
        title: String,
        dueISO: String? = nil,
        notes: String? = nil,
        listId: String? = nil,
        listName: String? = nil)
    {
        self.title = title
        self.dueISO = dueISO
        self.notes = notes
        self.listId = listId
        self.listName = listName
    }
}

public struct AutoCrabReminderPayload: Codable, Sendable, Equatable {
    public var identifier: String
    public var title: String
    public var dueISO: String?
    public var completed: Bool
    public var listName: String?

    public init(
        identifier: String,
        title: String,
        dueISO: String? = nil,
        completed: Bool,
        listName: String? = nil)
    {
        self.identifier = identifier
        self.title = title
        self.dueISO = dueISO
        self.completed = completed
        self.listName = listName
    }
}

public struct AutoCrabRemindersListPayload: Codable, Sendable, Equatable {
    public var reminders: [AutoCrabReminderPayload]

    public init(reminders: [AutoCrabReminderPayload]) {
        self.reminders = reminders
    }
}

public struct AutoCrabRemindersAddPayload: Codable, Sendable, Equatable {
    public var reminder: AutoCrabReminderPayload

    public init(reminder: AutoCrabReminderPayload) {
        self.reminder = reminder
    }
}
