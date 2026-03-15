import Foundation

// Stable identifier used for both the macOS LaunchAgent label and Nix-managed defaults suite.
// nix-autocrab writes app defaults into this suite to survive app bundle identifier churn.
let launchdLabel = "ai.autocrab.mac"
let gatewayLaunchdLabel = "ai.autocrab.gateway"
let onboardingVersionKey = "autocrab.onboardingVersion"
let onboardingSeenKey = "autocrab.onboardingSeen"
let currentOnboardingVersion = 7
let pauseDefaultsKey = "autocrab.pauseEnabled"
let iconAnimationsEnabledKey = "autocrab.iconAnimationsEnabled"
let swabbleEnabledKey = "autocrab.swabbleEnabled"
let swabbleTriggersKey = "autocrab.swabbleTriggers"
let voiceWakeTriggerChimeKey = "autocrab.voiceWakeTriggerChime"
let voiceWakeSendChimeKey = "autocrab.voiceWakeSendChime"
let showDockIconKey = "autocrab.showDockIcon"
let defaultVoiceWakeTriggers = ["autocrab"]
let voiceWakeMaxWords = 32
let voiceWakeMaxWordLength = 64
let voiceWakeMicKey = "autocrab.voiceWakeMicID"
let voiceWakeMicNameKey = "autocrab.voiceWakeMicName"
let voiceWakeLocaleKey = "autocrab.voiceWakeLocaleID"
let voiceWakeAdditionalLocalesKey = "autocrab.voiceWakeAdditionalLocaleIDs"
let voicePushToTalkEnabledKey = "autocrab.voicePushToTalkEnabled"
let talkEnabledKey = "autocrab.talkEnabled"
let iconOverrideKey = "autocrab.iconOverride"
let connectionModeKey = "autocrab.connectionMode"
let remoteTargetKey = "autocrab.remoteTarget"
let remoteIdentityKey = "autocrab.remoteIdentity"
let remoteProjectRootKey = "autocrab.remoteProjectRoot"
let remoteCliPathKey = "autocrab.remoteCliPath"
let canvasEnabledKey = "autocrab.canvasEnabled"
let cameraEnabledKey = "autocrab.cameraEnabled"
let systemRunPolicyKey = "autocrab.systemRunPolicy"
let systemRunAllowlistKey = "autocrab.systemRunAllowlist"
let systemRunEnabledKey = "autocrab.systemRunEnabled"
let locationModeKey = "autocrab.locationMode"
let locationPreciseKey = "autocrab.locationPreciseEnabled"
let peekabooBridgeEnabledKey = "autocrab.peekabooBridgeEnabled"
let deepLinkKeyKey = "autocrab.deepLinkKey"
let modelCatalogPathKey = "autocrab.modelCatalogPath"
let modelCatalogReloadKey = "autocrab.modelCatalogReload"
let cliInstallPromptedVersionKey = "autocrab.cliInstallPromptedVersion"
let heartbeatsEnabledKey = "autocrab.heartbeatsEnabled"
let debugPaneEnabledKey = "autocrab.debugPaneEnabled"
let debugFileLogEnabledKey = "autocrab.debug.fileLogEnabled"
let appLogLevelKey = "autocrab.debug.appLogLevel"
let voiceWakeSupported: Bool = ProcessInfo.processInfo.operatingSystemVersion.majorVersion >= 26
