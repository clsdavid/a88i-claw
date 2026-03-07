// swift-tools-version: 6.2

import PackageDescription

let package = Package(
    name: "AutoCrabKit",
    platforms: [
        .iOS(.v18),
        .macOS(.v15),
    ],
    products: [
        .library(name: "AutoCrabProtocol", targets: ["AutoCrabProtocol"]),
        .library(name: "AutoCrabKit", targets: ["AutoCrabKit"]),
        .library(name: "AutoCrabChatUI", targets: ["AutoCrabChatUI"]),
    ],
    dependencies: [
        .package(url: "https://github.com/steipete/ElevenLabsKit", exact: "0.1.0"),
        .package(url: "https://github.com/gonzalezreal/textual", exact: "0.3.1"),
    ],
    targets: [
        .target(
            name: "AutoCrabProtocol",
            path: "Sources/AutoCrabProtocol",
            swiftSettings: [
                .enableUpcomingFeature("StrictConcurrency"),
            ]),
        .target(
            name: "AutoCrabKit",
            dependencies: [
                "AutoCrabProtocol",
                .product(name: "ElevenLabsKit", package: "ElevenLabsKit"),
            ],
            path: "Sources/AutoCrabKit",
            resources: [
                .process("Resources"),
            ],
            swiftSettings: [
                .enableUpcomingFeature("StrictConcurrency"),
            ]),
        .target(
            name: "AutoCrabChatUI",
            dependencies: [
                "AutoCrabKit",
                .product(
                    name: "Textual",
                    package: "textual",
                    condition: .when(platforms: [.macOS, .iOS])),
            ],
            path: "Sources/AutoCrabChatUI",
            swiftSettings: [
                .enableUpcomingFeature("StrictConcurrency"),
            ]),
        .testTarget(
            name: "AutoCrabKitTests",
            dependencies: ["AutoCrabKit", "AutoCrabChatUI"],
            path: "Tests/AutoCrabKitTests",
            swiftSettings: [
                .enableUpcomingFeature("StrictConcurrency"),
                .enableExperimentalFeature("SwiftTesting"),
            ]),
    ])
