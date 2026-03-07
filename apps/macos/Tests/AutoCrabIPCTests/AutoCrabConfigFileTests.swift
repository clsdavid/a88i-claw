import Foundation
import Testing
@testable import AutoCrab

@Suite(.serialized)
struct AutoCrabConfigFileTests {
    private func makeConfigOverridePath() -> String {
        FileManager().temporaryDirectory
            .appendingPathComponent("autocrab-config-\(UUID().uuidString)")
            .appendingPathComponent("autocrab.json")
            .path
    }

    @Test
    func configPathRespectsEnvOverride() async {
        let override = makeConfigOverridePath()

        await TestIsolation.withEnvValues(["AUTOCRAB_CONFIG_PATH": override]) {
            #expect(AutoCrabConfigFile.url().path == override)
        }
    }

    @MainActor
    @Test
    func remoteGatewayPortParsesAndMatchesHost() async {
        let override = makeConfigOverridePath()

        await TestIsolation.withEnvValues(["AUTOCRAB_CONFIG_PATH": override]) {
            AutoCrabConfigFile.saveDict([
                "gateway": [
                    "remote": [
                        "url": "ws://gateway.ts.net:19999",
                    ],
                ],
            ])
            #expect(AutoCrabConfigFile.remoteGatewayPort() == 19999)
            #expect(AutoCrabConfigFile.remoteGatewayPort(matchingHost: "gateway.ts.net") == 19999)
            #expect(AutoCrabConfigFile.remoteGatewayPort(matchingHost: "gateway") == 19999)
            #expect(AutoCrabConfigFile.remoteGatewayPort(matchingHost: "other.ts.net") == nil)
        }
    }

    @MainActor
    @Test
    func setRemoteGatewayUrlPreservesScheme() async {
        let override = makeConfigOverridePath()

        await TestIsolation.withEnvValues(["AUTOCRAB_CONFIG_PATH": override]) {
            AutoCrabConfigFile.saveDict([
                "gateway": [
                    "remote": [
                        "url": "wss://old-host:111",
                    ],
                ],
            ])
            AutoCrabConfigFile.setRemoteGatewayUrl(host: "new-host", port: 2222)
            let root = AutoCrabConfigFile.loadDict()
            let url = ((root["gateway"] as? [String: Any])?["remote"] as? [String: Any])?["url"] as? String
            #expect(url == "wss://new-host:2222")
        }
    }

    @MainActor
    @Test
    func clearRemoteGatewayUrlRemovesOnlyUrlField() async {
        let override = makeConfigOverridePath()

        await TestIsolation.withEnvValues(["AUTOCRAB_CONFIG_PATH": override]) {
            AutoCrabConfigFile.saveDict([
                "gateway": [
                    "remote": [
                        "url": "wss://old-host:111",
                        "token": "tok",
                    ],
                ],
            ])
            AutoCrabConfigFile.clearRemoteGatewayUrl()
            let root = AutoCrabConfigFile.loadDict()
            let remote = ((root["gateway"] as? [String: Any])?["remote"] as? [String: Any]) ?? [:]
            #expect((remote["url"] as? String) == nil)
            #expect((remote["token"] as? String) == "tok")
        }
    }

    @Test
    func stateDirOverrideSetsConfigPath() async {
        let dir = FileManager().temporaryDirectory
            .appendingPathComponent("autocrab-state-\(UUID().uuidString)", isDirectory: true)
            .path

        await TestIsolation.withEnvValues([
            "AUTOCRAB_CONFIG_PATH": nil,
            "AUTOCRAB_STATE_DIR": dir,
        ]) {
            #expect(AutoCrabConfigFile.stateDirURL().path == dir)
            #expect(AutoCrabConfigFile.url().path == "\(dir)/autocrab.json")
        }
    }

    @MainActor
    @Test
    func saveDictAppendsConfigAuditLog() async throws {
        let stateDir = FileManager().temporaryDirectory
            .appendingPathComponent("autocrab-state-\(UUID().uuidString)", isDirectory: true)
        let configPath = stateDir.appendingPathComponent("autocrab.json")
        let auditPath = stateDir.appendingPathComponent("logs/config-audit.jsonl")

        defer { try? FileManager().removeItem(at: stateDir) }

        try await TestIsolation.withEnvValues([
            "AUTOCRAB_STATE_DIR": stateDir.path,
            "AUTOCRAB_CONFIG_PATH": configPath.path,
        ]) {
            AutoCrabConfigFile.saveDict([
                "gateway": ["mode": "local"],
            ])

            let configData = try Data(contentsOf: configPath)
            let configRoot = try JSONSerialization.jsonObject(with: configData) as? [String: Any]
            #expect((configRoot?["meta"] as? [String: Any]) != nil)

            let rawAudit = try String(contentsOf: auditPath, encoding: .utf8)
            let lines = rawAudit
                .split(whereSeparator: \.isNewline)
                .map(String.init)
            #expect(!lines.isEmpty)
            guard let last = lines.last else {
                Issue.record("Missing config audit line")
                return
            }
            let auditRoot = try JSONSerialization.jsonObject(with: Data(last.utf8)) as? [String: Any]
            #expect(auditRoot?["source"] as? String == "macos-autocrab-config-file")
            #expect(auditRoot?["event"] as? String == "config.write")
            #expect(auditRoot?["result"] as? String == "success")
            #expect(auditRoot?["configPath"] as? String == configPath.path)
        }
    }
}
