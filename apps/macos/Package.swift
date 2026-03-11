// swift-tools-version: 6.2
// Package manifest for the AutoCrab macOS companion (menu bar app + IPC library).

import PackageDescription

let package = Package(
    name: "AutoCrab",
    platforms: [
        .macOS(.v15),
    ],
    products: [
        .library(name: "AutoCrabIPC", targets: ["AutoCrabIPC"]),
        .library(name: "AutoCrabDiscovery", targets: ["AutoCrabDiscovery"]),
        .executable(name: "AutoCrab", targets: ["AutoCrab"]),
        .executable(name: "autocrab-mac", targets: ["AutoCrabMacCLI"]),
    ],
    dependencies: [
        .package(url: "https://github.com/orchetect/MenuBarExtraAccess", exact: "1.3.0"),
        .package(url: "https://github.com/swiftlang/swift-subprocess.git", from: "0.1.0"),
        .package(url: "https://github.com/apple/swift-log.git", from: "1.8.0"),
        .package(url: "https://github.com/sparkle-project/Sparkle", from: "2.8.1"),
        .package(url: "https://github.com/steipete/Peekaboo.git", branch: "main"),
        .package(path: "../shared/AutoCrabKit"),
        .package(path: "../../Swabble"),
    ],
    targets: [
        .target(
            name: "AutoCrabIPC",
            dependencies: [],
            swiftSettings: [
                .enableUpcomingFeature("StrictConcurrency"),
            ]),
        .target(
            name: "AutoCrabDiscovery",
            dependencies: [
                .product(name: "AutoCrabKit", package: "AutoCrabKit"),
            ],
            path: "Sources/AutoCrabDiscovery",
            swiftSettings: [
                .enableUpcomingFeature("StrictConcurrency"),
            ]),
        .executableTarget(
            name: "AutoCrab",
            dependencies: [
                "AutoCrabIPC",
                "AutoCrabDiscovery",
                .product(name: "AutoCrabKit", package: "AutoCrabKit"),
                .product(name: "AutoCrabChatUI", package: "AutoCrabKit"),
                .product(name: "AutoCrabProtocol", package: "AutoCrabKit"),
                .product(name: "SwabbleKit", package: "swabble"),
                .product(name: "MenuBarExtraAccess", package: "MenuBarExtraAccess"),
                .product(name: "Subprocess", package: "swift-subprocess"),
                .product(name: "Logging", package: "swift-log"),
                .product(name: "Sparkle", package: "Sparkle"),
                .product(name: "PeekabooBridge", package: "Peekaboo"),
                .product(name: "PeekabooAutomationKit", package: "Peekaboo"),
            ],
            exclude: [
                "Resources/Info.plist",
            ],
            resources: [
                .copy("Resources/AutoCrab.icns"),
                .copy("Resources/DeviceModels"),
            ],
            swiftSettings: [
                .enableUpcomingFeature("StrictConcurrency"),
            ]),
        .executableTarget(
            name: "AutoCrabMacCLI",
            dependencies: [
                "AutoCrabDiscovery",
                .product(name: "AutoCrabKit", package: "AutoCrabKit"),
                .product(name: "AutoCrabProtocol", package: "AutoCrabKit"),
            ],
            path: "Sources/AutoCrabMacCLI",
            swiftSettings: [
                .enableUpcomingFeature("StrictConcurrency"),
            ]),
        .testTarget(
            name: "AutoCrabIPCTests",
            dependencies: [
                "AutoCrabIPC",
                "AutoCrab",
                "AutoCrabDiscovery",
                .product(name: "AutoCrabProtocol", package: "AutoCrabKit"),
                .product(name: "SwabbleKit", package: "swabble"),
            ],
            swiftSettings: [
                .enableUpcomingFeature("StrictConcurrency"),
                .enableExperimentalFeature("SwiftTesting"),
            ]),
    ])
