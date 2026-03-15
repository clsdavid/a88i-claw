package ai.autocrab.android.node

import ai.autocrab.android.protocol.AutoCrabCalendarCommand
import ai.autocrab.android.protocol.AutoCrabCameraCommand
import ai.autocrab.android.protocol.AutoCrabCapability
import ai.autocrab.android.protocol.AutoCrabContactsCommand
import ai.autocrab.android.protocol.AutoCrabDeviceCommand
import ai.autocrab.android.protocol.AutoCrabLocationCommand
import ai.autocrab.android.protocol.AutoCrabMotionCommand
import ai.autocrab.android.protocol.AutoCrabNotificationsCommand
import ai.autocrab.android.protocol.AutoCrabPhotosCommand
import ai.autocrab.android.protocol.AutoCrabSmsCommand
import ai.autocrab.android.protocol.AutoCrabSystemCommand
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class InvokeCommandRegistryTest {
  private val coreCapabilities =
    setOf(
      AutoCrabCapability.Canvas.rawValue,
      AutoCrabCapability.Screen.rawValue,
      AutoCrabCapability.Device.rawValue,
      AutoCrabCapability.Notifications.rawValue,
      AutoCrabCapability.System.rawValue,
      AutoCrabCapability.AppUpdate.rawValue,
      AutoCrabCapability.Photos.rawValue,
      AutoCrabCapability.Contacts.rawValue,
      AutoCrabCapability.Calendar.rawValue,
    )

  private val optionalCapabilities =
    setOf(
      AutoCrabCapability.Camera.rawValue,
      AutoCrabCapability.Location.rawValue,
      AutoCrabCapability.Sms.rawValue,
      AutoCrabCapability.VoiceWake.rawValue,
      AutoCrabCapability.Motion.rawValue,
    )

  private val coreCommands =
    setOf(
      AutoCrabDeviceCommand.Status.rawValue,
      AutoCrabDeviceCommand.Info.rawValue,
      AutoCrabDeviceCommand.Permissions.rawValue,
      AutoCrabDeviceCommand.Health.rawValue,
      AutoCrabNotificationsCommand.List.rawValue,
      AutoCrabNotificationsCommand.Actions.rawValue,
      AutoCrabSystemCommand.Notify.rawValue,
      AutoCrabPhotosCommand.Latest.rawValue,
      AutoCrabContactsCommand.Search.rawValue,
      AutoCrabContactsCommand.Add.rawValue,
      AutoCrabCalendarCommand.Events.rawValue,
      AutoCrabCalendarCommand.Add.rawValue,
      "app.update",
    )

  private val optionalCommands =
    setOf(
      AutoCrabCameraCommand.Snap.rawValue,
      AutoCrabCameraCommand.Clip.rawValue,
      AutoCrabCameraCommand.List.rawValue,
      AutoCrabLocationCommand.Get.rawValue,
      AutoCrabMotionCommand.Activity.rawValue,
      AutoCrabMotionCommand.Pedometer.rawValue,
      AutoCrabSmsCommand.Send.rawValue,
    )

  private val debugCommands = setOf("debug.logs", "debug.ed25519")

  @Test
  fun advertisedCapabilities_respectsFeatureAvailability() {
    val capabilities = InvokeCommandRegistry.advertisedCapabilities(defaultFlags())

    assertContainsAll(capabilities, coreCapabilities)
    assertMissingAll(capabilities, optionalCapabilities)
  }

  @Test
  fun advertisedCapabilities_includesFeatureCapabilitiesWhenEnabled() {
    val capabilities =
      InvokeCommandRegistry.advertisedCapabilities(
        defaultFlags(
          cameraEnabled = true,
          locationEnabled = true,
          smsAvailable = true,
          voiceWakeEnabled = true,
          motionActivityAvailable = true,
          motionPedometerAvailable = true,
        ),
      )

    assertContainsAll(capabilities, coreCapabilities + optionalCapabilities)
  }

  @Test
  fun advertisedCommands_respectsFeatureAvailability() {
    val commands = InvokeCommandRegistry.advertisedCommands(defaultFlags())

    assertContainsAll(commands, coreCommands)
    assertMissingAll(commands, optionalCommands + debugCommands)
  }

  @Test
  fun advertisedCommands_includesFeatureCommandsWhenEnabled() {
    val commands =
      InvokeCommandRegistry.advertisedCommands(
        defaultFlags(
          cameraEnabled = true,
          locationEnabled = true,
          smsAvailable = true,
          motionActivityAvailable = true,
          motionPedometerAvailable = true,
          debugBuild = true,
        ),
      )

    assertContainsAll(commands, coreCommands + optionalCommands + debugCommands)
  }

  @Test
  fun advertisedCommands_onlyIncludesSupportedMotionCommands() {
    val commands =
      InvokeCommandRegistry.advertisedCommands(
        NodeRuntimeFlags(
          cameraEnabled = false,
          locationEnabled = false,
          smsAvailable = false,
          voiceWakeEnabled = false,
          motionActivityAvailable = true,
          motionPedometerAvailable = false,
          debugBuild = false,
        ),
      )

    assertTrue(commands.contains(AutoCrabMotionCommand.Activity.rawValue))
    assertFalse(commands.contains(AutoCrabMotionCommand.Pedometer.rawValue))
  }

  private fun defaultFlags(
    cameraEnabled: Boolean = false,
    locationEnabled: Boolean = false,
    smsAvailable: Boolean = false,
    voiceWakeEnabled: Boolean = false,
    motionActivityAvailable: Boolean = false,
    motionPedometerAvailable: Boolean = false,
    debugBuild: Boolean = false,
  ): NodeRuntimeFlags =
    NodeRuntimeFlags(
      cameraEnabled = cameraEnabled,
      locationEnabled = locationEnabled,
      smsAvailable = smsAvailable,
      voiceWakeEnabled = voiceWakeEnabled,
      motionActivityAvailable = motionActivityAvailable,
      motionPedometerAvailable = motionPedometerAvailable,
      debugBuild = debugBuild,
    )

  private fun assertContainsAll(actual: List<String>, expected: Set<String>) {
    expected.forEach { value -> assertTrue(actual.contains(value)) }
  }

  private fun assertMissingAll(actual: List<String>, forbidden: Set<String>) {
    forbidden.forEach { value -> assertFalse(actual.contains(value)) }
  }
}
